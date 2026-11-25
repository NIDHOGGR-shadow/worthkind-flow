BEGIN;
CREATE OR REPLACE FUNCTION worthkind_flow.create_supplier(p_subject text,p_slug text,p_name text,p_ref text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','procurement') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 INSERT INTO worthkind_flow.suppliers(property_id,name,external_reference) VALUES(a.property_id,p_name,p_ref) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.procurement_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'supplier_registered');
 RETURN v_id;
END $$;

CREATE OR REPLACE FUNCTION worthkind_flow.request_purchase(p_subject text,p_slug text,p_supplier uuid,p_item uuid,p_qty numeric,p_unit_price bigint,p_currency text,p_key text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; po worthkind_flow.purchase_orders%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','kitchen','procurement') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
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

CREATE OR REPLACE FUNCTION worthkind_flow.move_stock(p_subject text,p_slug text,p_item uuid,p_order uuid,p_delta numeric,p_reason text,p_key text)
RETURNS TABLE(movement_id uuid,balance numeric,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; i worthkind_flow.stock_items%ROWTYPE; po worthkind_flow.purchase_orders%ROWTYPE; mv worthkind_flow.stock_movements%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','kitchen','procurement') OR
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

CREATE OR REPLACE FUNCTION worthkind_flow.procurement_overview(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance','kitchen','procurement') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN jsonb_build_object(
 'items',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,sku,name,unit,balance,reorder_level,active FROM worthkind_flow.stock_items WHERE property_id=a.property_id ORDER BY sku LIMIT 500)x),'[]'::jsonb),
 'suppliers',CASE WHEN a.member_role='kitchen' THEN '[]'::jsonb ELSE COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,name,external_reference,state FROM worthkind_flow.suppliers WHERE property_id=a.property_id ORDER BY name LIMIT 500)x),'[]'::jsonb) END,
 'orders',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,supplier_id,item_id,quantity,received_quantity,unit_price_minor,currency,state,created_at FROM worthkind_flow.purchase_orders WHERE property_id=a.property_id AND (a.member_role<>'kitchen' OR requested_by=a.member_id) ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb));
END $$;


CREATE FUNCTION worthkind_flow.ticket_detail(p_subject text,p_slug text,p_ticket uuid)
RETURNS TABLE(id uuid,request_key text,category text,priority text,status text,assignee uuid,due_at timestamptz,encrypted_payload bytea,origin_case_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT t.id,t.request_key,t.category,t.priority,t.status,t.assignee,t.due_at,t.encrypted_payload,t.origin_case_id
 FROM worthkind_flow.service_tickets t WHERE t.id=p_ticket AND t.property_id=a.property_id
 AND (worthkind_flow.ops_category_allowed(a.member_role,t.category) OR EXISTS(
 SELECT 1 FROM worthkind_flow.ticket_events e WHERE e.ticket_id=t.id AND e.property_id=t.property_id AND e.actor=a.member_id AND e.action='created'));
 IF NOT FOUND THEN RAISE EXCEPTION 'Ticket unavailable' USING ERRCODE='P0002'; END IF;
END $$;
CREATE FUNCTION worthkind_flow.ticket_history(p_subject text,p_slug text,p_ticket uuid)
RETURNS TABLE(actor uuid,action text,encrypted_note bytea,created_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 PERFORM 1 FROM worthkind_flow.ticket_detail(p_subject,p_slug,p_ticket);
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 RETURN QUERY SELECT e.actor,e.action,e.encrypted_note,e.created_at FROM worthkind_flow.ticket_events e
 WHERE e.property_id=a.property_id AND e.ticket_id=p_ticket ORDER BY e.created_at,e.id LIMIT 500;
END $$;
CREATE FUNCTION worthkind_flow.guest_reservation_intents(p_slug text,p_case uuid,p_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,room_type_id,arrival,departure,adults,children,room_count,state,created_at
 FROM worthkind_flow.reservation_intents WHERE property_id=v_property AND case_id=p_case ORDER BY created_at DESC LIMIT 100)x),'[]'::jsonb);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.ticket_detail(text,text,uuid),worthkind_flow.ticket_history(text,text,uuid),worthkind_flow.guest_reservation_intents(text,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.ticket_detail(text,text,uuid),worthkind_flow.ticket_history(text,text,uuid) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.guest_reservation_intents(text,uuid,text) TO wf_guest_api;
COMMIT;
