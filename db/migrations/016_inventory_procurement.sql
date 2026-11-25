BEGIN;
CREATE TABLE worthkind_flow.stock_items(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 sku text NOT NULL CHECK(sku ~ '^[A-Za-z0-9_-]{2,60}$'),name text NOT NULL CHECK(length(btrim(name)) BETWEEN 2 AND 160),
 unit text NOT NULL CHECK(length(btrim(unit)) BETWEEN 1 AND 24),
 balance numeric(18,3) NOT NULL DEFAULT 0 CHECK(balance>=0),
 reorder_level numeric(18,3) NOT NULL DEFAULT 0 CHECK(reorder_level>=0),
 active boolean NOT NULL DEFAULT true,
 UNIQUE(property_id,sku),UNIQUE(id,property_id)
);
CREATE TABLE worthkind_flow.suppliers(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 name text NOT NULL CHECK(length(btrim(name)) BETWEEN 2 AND 160),
 external_reference text NOT NULL CHECK(length(btrim(external_reference)) BETWEEN 2 AND 100),
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','approved','suspended')),
 UNIQUE(property_id,external_reference),UNIQUE(id,property_id)
);
CREATE TABLE worthkind_flow.purchase_orders(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 supplier_id uuid NOT NULL,item_id uuid NOT NULL,
 quantity numeric(18,3) NOT NULL CHECK(quantity>0), received_quantity numeric(18,3) NOT NULL DEFAULT 0 CHECK(received_quantity>=0 AND received_quantity<=quantity),
 unit_price_minor bigint NOT NULL CHECK(unit_price_minor>=0 AND unit_price_minor<=1000000000000),currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
 state text NOT NULL DEFAULT 'requested' CHECK(state IN ('requested','approved','part_received','received','cancelled')),
 request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 requested_by uuid NOT NULL,approved_by uuid,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),UNIQUE(id,property_id),
 FOREIGN KEY(supplier_id,property_id) REFERENCES worthkind_flow.suppliers(id,property_id),
 FOREIGN KEY(item_id,property_id) REFERENCES worthkind_flow.stock_items(id,property_id),
 FOREIGN KEY(requested_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(approved_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.stock_movements(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,item_id uuid NOT NULL,order_id uuid,
 actor uuid NOT NULL,request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 quantity_delta numeric(18,3) NOT NULL CHECK(quantity_delta<>0),
 reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 4 AND 240),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),
 FOREIGN KEY(item_id,property_id) REFERENCES worthkind_flow.stock_items(id,property_id),
 FOREIGN KEY(order_id,property_id) REFERENCES worthkind_flow.purchase_orders(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.procurement_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor uuid NOT NULL,resource_id uuid NOT NULL,action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.stock_items ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.stock_items FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.suppliers ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.suppliers FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.purchase_orders ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.purchase_orders FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.stock_movements ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.stock_movements FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.procurement_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.procurement_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.stock_items,worthkind_flow.suppliers,worthkind_flow.purchase_orders,worthkind_flow.stock_movements,worthkind_flow.procurement_events FROM PUBLIC;

CREATE FUNCTION worthkind_flow.create_stock_item(p_subject text,p_slug text,p_sku text,p_name text,p_unit text,p_reorder numeric)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 INSERT INTO worthkind_flow.stock_items(property_id,sku,name,unit,reorder_level) VALUES(a.property_id,p_sku,p_name,p_unit,p_reorder) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'stock_item_created');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.create_supplier(p_subject text,p_slug text,p_name text,p_ref text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 INSERT INTO worthkind_flow.suppliers(property_id,name,external_reference) VALUES(a.property_id,p_name,p_ref) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'supplier_registered');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.change_supplier(p_subject text,p_slug text,p_supplier uuid,p_state text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_state NOT IN ('approved','suspended') THEN RAISE EXCEPTION 'Invalid state' USING ERRCODE='22023'; END IF;
 UPDATE worthkind_flow.suppliers SET state=p_state WHERE id=p_supplier AND property_id=a.property_id RETURNING state INTO v_state;
 IF NOT FOUND THEN RAISE EXCEPTION 'Supplier unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,p_supplier,'supplier_'||v_state);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.request_purchase(p_subject text,p_slug text,p_supplier uuid,p_item uuid,p_qty numeric,p_unit_price bigint,p_currency text,p_key text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; po worthkind_flow.purchase_orders%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','kitchen') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO po FROM worthkind_flow.purchase_orders WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
 IF po.supplier_id<>p_supplier OR po.item_id<>p_item OR po.quantity<>p_qty OR po.unit_price_minor<>p_unit_price OR po.currency<>p_currency THEN RAISE EXCEPTION 'Idempotency conflict' USING ERRCODE='23505'; END IF;
 RETURN po.id; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.suppliers WHERE id=p_supplier AND property_id=a.property_id AND state='approved')
 OR NOT EXISTS(SELECT 1 FROM worthkind_flow.stock_items WHERE id=p_item AND property_id=a.property_id AND active) THEN
 RAISE EXCEPTION 'Supplier or item unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.purchase_orders(property_id,supplier_id,item_id,quantity,unit_price_minor,currency,request_key,requested_by)
 VALUES(a.property_id,p_supplier,p_item,p_qty,p_unit_price,p_currency,p_key,a.member_id) RETURNING * INTO po;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,po.id,'purchase_requested');
 RETURN po.id;
END $$;
CREATE FUNCTION worthkind_flow.decide_purchase(p_subject text,p_slug text,p_order uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; po worthkind_flow.purchase_orders%ROWTYPE; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO po FROM worthkind_flow.purchase_orders WHERE id=p_order AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Order unavailable' USING ERRCODE='P0002'; END IF;
 IF p_action='approve' AND po.state='requested' AND EXISTS(SELECT 1 FROM worthkind_flow.suppliers WHERE id=po.supplier_id AND state='approved') THEN v_state='approved';
 ELSIF p_action='cancel' AND po.state IN ('requested','approved') THEN v_state='cancelled';
 ELSE RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.purchase_orders SET state=v_state,approved_by=CASE WHEN v_state='approved' THEN a.member_id ELSE approved_by END WHERE id=po.id;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,p_order,'purchase_'||v_state);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.move_stock(p_subject text,p_slug text,p_item uuid,p_order uuid,p_delta numeric,p_reason text,p_key text)
RETURNS TABLE(movement_id uuid,balance numeric,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; i worthkind_flow.stock_items%ROWTYPE; po worthkind_flow.purchase_orders%ROWTYPE; mv worthkind_flow.stock_movements%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','kitchen') OR
 (a.member_role='kitchen' AND (p_order IS NOT NULL OR p_delta>=0)) THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO i FROM worthkind_flow.stock_items WHERE id=p_item AND property_id=a.property_id AND active FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Item unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO mv FROM worthkind_flow.stock_movements WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
  IF mv.item_id<>p_item OR mv.order_id IS DISTINCT FROM p_order OR mv.quantity_delta<>p_delta OR mv.reason<>p_reason THEN RAISE EXCEPTION 'Idempotency conflict' USING ERRCODE='23505'; END IF;
  RETURN QUERY SELECT mv.id,i.balance,true; RETURN;
 END IF;
 IF p_order IS NOT NULL THEN
  SELECT * INTO po FROM worthkind_flow.purchase_orders WHERE id=p_order AND property_id=a.property_id AND item_id=p_item FOR UPDATE;
  IF NOT FOUND OR po.state NOT IN ('approved','part_received') OR p_delta<=0 OR po.received_quantity+p_delta>po.quantity THEN RAISE EXCEPTION 'Invalid receipt' USING ERRCODE='23514'; END IF;
  UPDATE worthkind_flow.purchase_orders SET received_quantity=received_quantity+p_delta,
    state=CASE WHEN received_quantity+p_delta=quantity THEN 'received' ELSE 'part_received' END WHERE id=p_order;
 ELSIF p_delta>0 AND a.member_role NOT IN ('owner','manager') THEN
  RAISE EXCEPTION 'Adjustment access denied' USING ERRCODE='42501';
 END IF;
 IF i.balance+p_delta<0 OR p_delta=0 THEN RAISE EXCEPTION 'Invalid stock movement' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.stock_items s SET balance=s.balance+p_delta WHERE s.id=i.id RETURNING * INTO i;
 INSERT INTO worthkind_flow.stock_movements(property_id,item_id,order_id,actor,request_key,quantity_delta,reason)
 VALUES(a.property_id,p_item,p_order,a.member_id,p_key,p_delta,p_reason) RETURNING * INTO mv;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,mv.id,'stock_moved');
 RETURN QUERY SELECT mv.id,i.balance,false;
END $$;
CREATE FUNCTION worthkind_flow.procurement_overview(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','kitchen') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN jsonb_build_object(
 'items',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,sku,name,unit,balance,reorder_level,active FROM worthkind_flow.stock_items WHERE property_id=a.property_id ORDER BY sku LIMIT 500)x),'[]'::jsonb),
 'suppliers',CASE WHEN a.member_role='kitchen' THEN '[]'::jsonb ELSE COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,name,external_reference,state FROM worthkind_flow.suppliers WHERE property_id=a.property_id ORDER BY name LIMIT 500)x),'[]'::jsonb) END,
 'orders',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,supplier_id,item_id,quantity,received_quantity,unit_price_minor,currency,state,created_at FROM worthkind_flow.purchase_orders WHERE property_id=a.property_id AND (a.member_role<>'kitchen' OR requested_by=a.member_id) ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb));
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.create_stock_item(text,text,text,text,text,numeric),worthkind_flow.create_supplier(text,text,text,text),
 worthkind_flow.change_supplier(text,text,uuid,text),worthkind_flow.request_purchase(text,text,uuid,uuid,numeric,bigint,text,text),
 worthkind_flow.decide_purchase(text,text,uuid,text),worthkind_flow.move_stock(text,text,uuid,uuid,numeric,text,text),
 worthkind_flow.procurement_overview(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.create_stock_item(text,text,text,text,text,numeric),worthkind_flow.create_supplier(text,text,text,text),
 worthkind_flow.change_supplier(text,text,uuid,text),worthkind_flow.request_purchase(text,text,uuid,uuid,numeric,bigint,text,text),
 worthkind_flow.decide_purchase(text,text,uuid,text),worthkind_flow.move_stock(text,text,uuid,uuid,numeric,text,text),
 worthkind_flow.procurement_overview(text,text) TO wf_operations;
COMMIT;
