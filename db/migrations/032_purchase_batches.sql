BEGIN;
CREATE TABLE worthkind_flow.purchase_batches(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 supplier_id uuid NOT NULL,currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
 request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 payload jsonb NOT NULL,requested_by uuid NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),UNIQUE(id,property_id),
 FOREIGN KEY(supplier_id,property_id) REFERENCES worthkind_flow.suppliers(id,property_id),
 FOREIGN KEY(requested_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.purchase_batch_lines(
 property_id uuid NOT NULL,batch_id uuid NOT NULL,order_id uuid NOT NULL UNIQUE,position integer NOT NULL CHECK(position BETWEEN 1 AND 50),
 PRIMARY KEY(batch_id,position),
 FOREIGN KEY(batch_id,property_id) REFERENCES worthkind_flow.purchase_batches(id,property_id),
 FOREIGN KEY(order_id,property_id) REFERENCES worthkind_flow.purchase_orders(id,property_id)
);
ALTER TABLE worthkind_flow.purchase_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.purchase_batches FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.purchase_batch_lines ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.purchase_batch_lines FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.purchase_batches,worthkind_flow.purchase_batch_lines FROM PUBLIC;

CREATE FUNCTION worthkind_flow.request_purchase_batch(p_subject text,p_slug text,p_supplier uuid,p_currency text,p_key text,p_lines jsonb)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; b worthkind_flow.purchase_batches%ROWTYPE; line record; v_position int:=0; v_order uuid; canonical jsonb;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','procurement','kitchen') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_lines IS NULL OR jsonb_typeof(p_lines)<>'array' THEN RAISE EXCEPTION 'Invalid lines' USING ERRCODE='22023'; END IF;
 IF jsonb_array_length(p_lines) NOT BETWEEN 1 AND 50 THEN RAISE EXCEPTION 'Invalid line count' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity numeric,unit_price_minor bigint)
 WHERE x.item_id IS NULL OR x.quantity IS NULL OR x.quantity<=0 OR x.quantity<>round(x.quantity,3) OR x.quantity>=1000000000000000 OR
 x.unit_price_minor IS NULL OR x.unit_price_minor NOT BETWEEN 0 AND 1000000000000) THEN RAISE EXCEPTION 'Invalid line' USING ERRCODE='22023'; END IF;
 IF (SELECT count(DISTINCT x.item_id) FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity numeric,unit_price_minor bigint))<>jsonb_array_length(p_lines) THEN
 RAISE EXCEPTION 'Duplicate item' USING ERRCODE='22023'; END IF;
 SELECT jsonb_agg(to_jsonb(x) ORDER BY x.item_id) INTO canonical FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity numeric,unit_price_minor bigint);
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO b FROM worthkind_flow.purchase_batches WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
 IF b.payload<>canonical OR b.supplier_id<>p_supplier OR b.currency<>p_currency THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN b.id; END IF;
 INSERT INTO worthkind_flow.purchase_batches(property_id,supplier_id,currency,request_key,payload,requested_by)
 VALUES(a.property_id,p_supplier,p_currency,p_key,canonical,a.member_id) RETURNING * INTO b;
 FOR line IN SELECT * FROM jsonb_to_recordset(canonical) AS x(item_id uuid,quantity numeric,unit_price_minor bigint) ORDER BY x.item_id LOOP
 v_position:=v_position+1;
 v_order:=worthkind_flow.request_purchase(p_subject,p_slug,p_supplier,line.item_id,line.quantity,line.unit_price_minor,p_currency,'batch-'||b.id::text||'-'||v_position);
 INSERT INTO worthkind_flow.purchase_batch_lines(property_id,batch_id,order_id,position) VALUES(a.property_id,b.id,v_order,v_position);
 END LOOP;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,b.id,'purchase_batch_requested');
 RETURN b.id;
END $$;

CREATE FUNCTION worthkind_flow.decide_purchase_batch(p_subject text,p_slug text,p_batch uuid,p_action text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; line record; v_count int:=0;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action NOT IN ('approve','cancel') THEN RAISE EXCEPTION 'Invalid action' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 PERFORM 1 FROM worthkind_flow.purchase_batches WHERE id=p_batch AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Batch unavailable' USING ERRCODE='P0002'; END IF;
 FOR line IN SELECT l.order_id FROM worthkind_flow.purchase_batch_lines l WHERE l.batch_id=p_batch AND l.property_id=a.property_id ORDER BY l.order_id LOOP
 PERFORM worthkind_flow.decide_purchase(p_subject,p_slug,line.order_id,p_action);
 v_count:=v_count+1;
 END LOOP;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,p_batch,'purchase_batch_'||p_action);
 RETURN jsonb_build_object('id',p_batch,'action',p_action,'line_count',v_count);
END $$;
CREATE FUNCTION worthkind_flow.purchase_batch_overview(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','procurement','kitchen') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (
 SELECT b.id,b.supplier_id,b.currency,b.created_at,
 (SELECT jsonb_agg(jsonb_build_object('order_id',o.id,'item_id',o.item_id,'quantity',o.quantity,'unit_price_minor',o.unit_price_minor,
 'received_quantity',o.received_quantity,'state',o.state) ORDER BY l.position)
 FROM worthkind_flow.purchase_batch_lines l JOIN worthkind_flow.purchase_orders o ON o.id=l.order_id AND o.property_id=l.property_id
 WHERE l.batch_id=b.id AND l.property_id=b.property_id) AS lines
 FROM worthkind_flow.purchase_batches b WHERE b.property_id=a.property_id AND (a.member_role<>'kitchen' OR b.requested_by=a.member_id)
 ORDER BY b.created_at DESC LIMIT 200)x),'[]'::jsonb);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.request_purchase_batch(text,text,uuid,text,text,jsonb),worthkind_flow.decide_purchase_batch(text,text,uuid,text),worthkind_flow.purchase_batch_overview(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.request_purchase_batch(text,text,uuid,text,text,jsonb),worthkind_flow.decide_purchase_batch(text,text,uuid,text),worthkind_flow.purchase_batch_overview(text,text) TO wf_operations;
COMMIT;
