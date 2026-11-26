BEGIN;
ALTER TABLE worthkind_flow.dining_orders ALTER COLUMN created_by DROP NOT NULL;
ALTER TABLE worthkind_flow.dining_orders ADD COLUMN guest_case_id uuid;
ALTER TABLE worthkind_flow.dining_orders ADD FOREIGN KEY(guest_case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id);
ALTER TABLE worthkind_flow.dining_orders ADD CONSTRAINT wf_dining_order_actor CHECK((created_by IS NULL)<>(guest_case_id IS NULL));
ALTER TABLE worthkind_flow.dining_events ALTER COLUMN actor DROP NOT NULL;
ALTER TABLE worthkind_flow.dining_events ADD COLUMN guest_case_id uuid;
ALTER TABLE worthkind_flow.dining_events ADD FOREIGN KEY(guest_case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id);
ALTER TABLE worthkind_flow.dining_events ADD CONSTRAINT wf_dining_event_actor CHECK((actor IS NULL)<>(guest_case_id IS NULL));
CREATE INDEX wf_dining_guest_case ON worthkind_flow.dining_orders(property_id,guest_case_id,id);
CREATE FUNCTION worthkind_flow.create_guest_dining_order(p_slug text,p_case uuid,p_hash text,p_key text,p_room uuid,p_lines jsonb)
RETURNS TABLE(id uuid,state text,total_minor bigint,currency text,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; o worthkind_flow.dining_orders%ROWTYPE; v_total bigint; v_currency text; v_count int; v_found int; v_distinct int; v_payload jsonb;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 IF p_lines IS NULL OR jsonb_typeof(p_lines)<>'array' THEN RAISE EXCEPTION 'Invalid lines' USING ERRCODE='22023'; END IF;
 v_count=jsonb_array_length(p_lines);
 IF v_count NOT BETWEEN 1 AND 50 THEN RAISE EXCEPTION 'Invalid line count' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer) WHERE x.item_id IS NULL OR x.quantity IS NULL OR x.quantity NOT BETWEEN 1 AND 100) THEN
 RAISE EXCEPTION 'Invalid line' USING ERRCODE='22023'; END IF;
 SELECT count(DISTINCT x.item_id) INTO v_distinct FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer);
 IF v_distinct<>v_count THEN RAISE EXCEPTION 'Duplicate line' USING ERRCODE='22023'; END IF;
 SELECT jsonb_build_object('guest_case',p_case,'room',p_room,'lines',jsonb_agg(to_jsonb(x) ORDER BY x.item_id)) INTO v_payload FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer);
 PERFORM 1 FROM worthkind_flow.properties WHERE worthkind_flow.properties.id=v_property FOR UPDATE;
 SELECT * INTO o FROM worthkind_flow.dining_orders d WHERE d.property_id=v_property AND d.request_key=p_key;
 IF FOUND THEN
 IF o.guest_case_id IS DISTINCT FROM p_case OR o.request_payload<>v_payload THEN RAISE EXCEPTION 'Idempotency conflict' USING ERRCODE='23505'; END IF;
 RETURN QUERY SELECT o.id,o.state,o.total_minor,o.currency,true; RETURN; END IF;
 PERFORM 1 FROM worthkind_flow.guest_cases c WHERE c.id=p_case AND c.property_id=v_property AND c.kind IN ('food','booking') AND c.state NOT IN ('cancelled','resolved') FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 IF p_room IS NOT NULL AND NOT EXISTS(
 SELECT 1 FROM worthkind_flow.occupied_rooms o2 JOIN worthkind_flow.native_bookings b ON b.id=o2.booking_id AND b.property_id=o2.property_id
 JOIN worthkind_flow.reservation_intents ri ON ri.id=b.intent_id AND ri.property_id=b.property_id
 JOIN worthkind_flow.native_stays s ON s.booking_id=b.id AND s.property_id=b.property_id
 JOIN worthkind_flow.hotel_rooms r ON r.id=o2.room_id AND r.property_id=o2.property_id
 WHERE o2.property_id=v_property AND o2.room_id=p_room AND ri.case_id=p_case AND s.state='checked_in' AND r.operational_state<>'out_of_service') THEN
 RAISE EXCEPTION 'Room unavailable' USING ERRCODE='P0002'; END IF;
 SELECT count(*),sum(m.price_minor*x.quantity),min(m.currency),count(DISTINCT m.currency)
 INTO v_found,v_total,v_currency,v_distinct FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer)
 JOIN worthkind_flow.menu_items m ON m.id=x.item_id AND m.property_id=v_property AND m.available;
 IF v_found<>v_count OR v_distinct<>1 THEN RAISE EXCEPTION 'Menu item unavailable or mixed currency' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.dining_orders(property_id,room_id,request_key,request_payload,guest_case_id,currency,total_minor)
 VALUES(v_property,p_room,p_key,v_payload,p_case,v_currency,v_total) RETURNING * INTO o;
 INSERT INTO worthkind_flow.dining_order_lines(property_id,order_id,menu_item_id,item_name,quantity,unit_price_minor)
 SELECT v_property,o.id,m.id,m.name,x.quantity,m.price_minor FROM jsonb_to_recordset(p_lines) AS x(item_id uuid,quantity integer)
 JOIN worthkind_flow.menu_items m ON m.id=x.item_id AND m.property_id=v_property;
 INSERT INTO worthkind_flow.dining_events(property_id,order_id,guest_case_id,action) VALUES(v_property,o.id,p_case,'submitted');
 RETURN QUERY SELECT o.id,o.state,o.total_minor,o.currency,false;
END $$;

CREATE FUNCTION worthkind_flow.guest_dining_orders(p_slug text,p_case uuid,p_hash text,p_after uuid,p_limit integer)
RETURNS TABLE(order_id uuid,room_id uuid,state text,currency text,total_minor bigint,created_at timestamptz,lines jsonb)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT d.id,d.room_id,d.state,d.currency,d.total_minor,d.created_at,
 (SELECT jsonb_agg(jsonb_build_object('name',l.item_name,'quantity',l.quantity,'unit_price_minor',l.unit_price_minor) ORDER BY l.id) FROM worthkind_flow.dining_order_lines l WHERE l.property_id=d.property_id AND l.order_id=d.id)
 FROM worthkind_flow.dining_orders d WHERE d.property_id=v_property AND d.guest_case_id=p_case AND (p_after IS NULL OR d.id>p_after) ORDER BY d.id LIMIT p_limit;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.create_guest_dining_order(text,uuid,text,text,uuid,jsonb),worthkind_flow.guest_dining_orders(text,uuid,text,uuid,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.create_guest_dining_order(text,uuid,text,text,uuid,jsonb),worthkind_flow.guest_dining_orders(text,uuid,text,uuid,integer) TO wf_guest_api;
COMMIT;
