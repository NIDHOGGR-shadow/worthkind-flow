BEGIN;
CREATE TABLE worthkind_flow.menu_items(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 code text NOT NULL CHECK(code ~ '^[A-Za-z0-9_-]{2,60}$'),name text NOT NULL CHECK(length(btrim(name)) BETWEEN 2 AND 160),
 description text NOT NULL CHECK(length(description)<=1000),price_minor bigint NOT NULL CHECK(price_minor BETWEEN 0 AND 1000000000000),
 currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),available boolean NOT NULL DEFAULT false,
 revision bigint NOT NULL DEFAULT 1, UNIQUE(property_id,code),UNIQUE(id,property_id)
);
CREATE TABLE worthkind_flow.dining_orders(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 room_id uuid,request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 request_payload jsonb NOT NULL,created_by uuid NOT NULL,
 state text NOT NULL DEFAULT 'submitted' CHECK(state IN ('submitted','accepted','preparing','ready','served','rejected','cancelled')),
 currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),total_minor bigint NOT NULL CHECK(total_minor>=0),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),UNIQUE(id,property_id),
 FOREIGN KEY(room_id,property_id) REFERENCES worthkind_flow.hotel_rooms(id,property_id),
 FOREIGN KEY(created_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.dining_order_lines(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,order_id uuid NOT NULL,menu_item_id uuid NOT NULL,
 item_name text NOT NULL,quantity integer NOT NULL CHECK(quantity BETWEEN 1 AND 100),unit_price_minor bigint NOT NULL CHECK(unit_price_minor>=0),
 UNIQUE(order_id,menu_item_id),
 FOREIGN KEY(order_id,property_id) REFERENCES worthkind_flow.dining_orders(id,property_id),
 FOREIGN KEY(menu_item_id,property_id) REFERENCES worthkind_flow.menu_items(id,property_id)
);
CREATE TABLE worthkind_flow.dining_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,order_id uuid NOT NULL,actor uuid NOT NULL,
 action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(order_id,property_id) REFERENCES worthkind_flow.dining_orders(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.menu_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.menu_items FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.dining_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.dining_orders FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.dining_order_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.dining_order_lines FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.dining_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.dining_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.menu_items,worthkind_flow.dining_orders,worthkind_flow.dining_order_lines,worthkind_flow.dining_events FROM PUBLIC;

CREATE FUNCTION worthkind_flow.save_menu_item(p_subject text,p_slug text,p_code text,p_name text,p_description text,p_price bigint,p_currency text,p_available boolean,p_revision bigint)
RETURNS TABLE(id uuid,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; m worthkind_flow.menu_items%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 IF p_revision=0 THEN
 INSERT INTO worthkind_flow.menu_items(property_id,code,name,description,price_minor,currency,available)
 VALUES(a.property_id,p_code,p_name,p_description,p_price,p_currency,p_available) RETURNING * INTO m;
 ELSE
 UPDATE worthkind_flow.menu_items x SET name=p_name,description=p_description,price_minor=p_price,currency=p_currency,available=p_available,revision=x.revision+1
 WHERE x.property_id=a.property_id AND x.code=p_code AND x.revision=p_revision RETURNING * INTO m;
 IF NOT FOUND THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
 END IF;
 RETURN QUERY SELECT m.id,m.revision;
END $$;
CREATE FUNCTION worthkind_flow.list_menu(p_slug text)
RETURNS TABLE(id uuid,code text,name text,description text,price_minor bigint,currency text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT m.id,m.code,m.name,m.description,m.price_minor,m.currency FROM worthkind_flow.menu_items m
 JOIN worthkind_flow.properties p ON p.id=m.property_id JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' AND m.available ORDER BY m.code LIMIT 500
$$;
CREATE FUNCTION worthkind_flow.create_dining_order(p_subject text,p_slug text,p_key text,p_room uuid,p_lines jsonb)
RETURNS TABLE(id uuid,state text,total_minor bigint,currency text,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; o worthkind_flow.dining_orders%ROWTYPE; v_total bigint; v_currency text; v_count int; v_found int; v_distinct int; v_payload jsonb;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_lines IS NULL OR jsonb_typeof(p_lines)<>'array' THEN RAISE EXCEPTION 'Invalid lines' USING ERRCODE='22023'; END IF;
 v_count=jsonb_array_length(p_lines);
 IF v_count NOT BETWEEN 1 AND 50 THEN RAISE EXCEPTION 'Invalid line count' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer) WHERE x.item_id IS NULL OR x.quantity IS NULL OR x.quantity NOT BETWEEN 1 AND 100) THEN
 RAISE EXCEPTION 'Invalid line' USING ERRCODE='22023'; END IF;
 SELECT count(DISTINCT x.item_id) INTO v_distinct FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer);
 IF v_distinct<>v_count THEN RAISE EXCEPTION 'Duplicate line' USING ERRCODE='22023'; END IF;
 SELECT jsonb_build_object('room',p_room,'lines',jsonb_agg(to_jsonb(x) ORDER BY x.item_id)) INTO v_payload FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer);
 PERFORM 1 FROM worthkind_flow.properties WHERE worthkind_flow.properties.id=a.property_id FOR UPDATE;
 SELECT * INTO o FROM worthkind_flow.dining_orders d WHERE d.property_id=a.property_id AND d.request_key=p_key;
 IF FOUND THEN
 IF o.request_payload<>v_payload THEN RAISE EXCEPTION 'Idempotency conflict' USING ERRCODE='23505'; END IF;
 RETURN QUERY SELECT o.id,o.state,o.total_minor,o.currency,true; RETURN; END IF;
 IF p_room IS NOT NULL AND NOT EXISTS(SELECT 1 FROM worthkind_flow.hotel_rooms r WHERE r.property_id=a.property_id AND r.id=p_room AND r.operational_state<>'out_of_service') THEN
 RAISE EXCEPTION 'Room unavailable' USING ERRCODE='P0002'; END IF;
 SELECT count(*),sum(m.price_minor*x.quantity),min(m.currency),count(DISTINCT m.currency)
 INTO v_found,v_total,v_currency,v_distinct FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer)
 JOIN worthkind_flow.menu_items m ON m.id=x.item_id AND m.property_id=a.property_id AND m.available;
 IF v_found<>v_count OR v_distinct<>1 THEN RAISE EXCEPTION 'Menu item unavailable or mixed currency' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.dining_orders(property_id,room_id,request_key,request_payload,created_by,currency,total_minor)
 VALUES(a.property_id,p_room,p_key,v_payload,a.member_id,v_currency,v_total) RETURNING * INTO o;
 INSERT INTO worthkind_flow.dining_order_lines(property_id,order_id,menu_item_id,item_name,quantity,unit_price_minor)
 SELECT a.property_id,o.id,m.id,m.name,x.quantity,m.price_minor FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer)
 JOIN worthkind_flow.menu_items m ON m.id=x.item_id AND m.property_id=a.property_id;
 INSERT INTO worthkind_flow.dining_events(property_id,order_id,actor,action) VALUES(a.property_id,o.id,a.member_id,'submitted');
 RETURN QUERY SELECT o.id,o.state,o.total_minor,o.currency,false;
END $$;
CREATE FUNCTION worthkind_flow.transition_dining_order(p_subject text,p_slug text,p_order uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; o worthkind_flow.dining_orders%ROWTYPE; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO o FROM worthkind_flow.dining_orders WHERE id=p_order AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Order unavailable' USING ERRCODE='P0002'; END IF;
 IF p_action IN ('accept','prepare','ready','reject') AND a.member_role NOT IN ('owner','manager','kitchen') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action IN ('serve','cancel') AND a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action='accept' AND o.state='submitted' THEN v_state='accepted';
 ELSIF p_action='prepare' AND o.state='accepted' THEN v_state='preparing';
 ELSIF p_action='ready' AND o.state='preparing' THEN v_state='ready';
 ELSIF p_action='serve' AND o.state='ready' THEN v_state='served';
 ELSIF p_action='reject' AND o.state='submitted' THEN v_state='rejected';
 ELSIF p_action='cancel' AND o.state='submitted' THEN v_state='cancelled';
 ELSE RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.dining_orders SET state=v_state,updated_at=now() WHERE id=o.id;
 INSERT INTO worthkind_flow.dining_events(property_id,order_id,actor,action) VALUES(a.property_id,o.id,a.member_id,p_action);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.dining_queue(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception','kitchen','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (
 SELECT d.id,d.room_id,d.state,d.currency,d.total_minor,d.created_at,
 (SELECT jsonb_agg(jsonb_build_object('name',l.item_name,'quantity',l.quantity,'unit_price_minor',l.unit_price_minor) ORDER BY l.id)
 FROM worthkind_flow.dining_order_lines l WHERE l.order_id=d.id AND l.property_id=d.property_id) AS lines
 FROM worthkind_flow.dining_orders d WHERE d.property_id=a.property_id ORDER BY d.created_at DESC LIMIT 200)x),'[]'::jsonb);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.save_menu_item(text,text,text,text,text,bigint,text,boolean,bigint),worthkind_flow.list_menu(text),
 worthkind_flow.create_dining_order(text,text,text,uuid,jsonb),worthkind_flow.transition_dining_order(text,text,uuid,text),worthkind_flow.dining_queue(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.save_menu_item(text,text,text,text,text,bigint,text,boolean,bigint),worthkind_flow.create_dining_order(text,text,text,uuid,jsonb),
 worthkind_flow.transition_dining_order(text,text,uuid,text),worthkind_flow.dining_queue(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.list_menu(text) TO wf_public_content;
COMMIT;
