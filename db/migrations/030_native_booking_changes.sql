BEGIN;
CREATE FUNCTION worthkind_flow.native_availability(p_slug text,p_arrival date,p_departure date)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 JOIN worthkind_flow.native_booking_accounts a ON a.property_id=p.id AND a.enabled
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified';
 IF NOT FOUND THEN RAISE EXCEPTION 'Native inventory unavailable' USING ERRCODE='P0002'; END IF;
 IF p_arrival IS NULL OR p_departure IS NULL OR p_departure-p_arrival NOT BETWEEN 1 AND 90
 OR p_arrival<(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=v_property) THEN RAISE EXCEPTION 'Invalid dates' USING ERRCODE='22023'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (
 SELECT t.id AS room_type_id,t.name,t.max_guests,
 (SELECT count(*) FROM worthkind_flow.hotel_rooms h WHERE h.property_id=v_property AND h.room_type_id=t.id AND h.operational_state IN ('clean','dirty','inspecting')
 AND NOT EXISTS(SELECT 1 FROM worthkind_flow.booking_room_nights n JOIN worthkind_flow.native_bookings b ON b.id=n.booking_id AND b.property_id=n.property_id
 WHERE n.property_id=v_property AND n.room_id=h.id AND n.night>=p_arrival AND n.night<p_departure
 AND (b.state='confirmed' OR b.state='held' AND b.expires_at>now()))) AS rooms_available,
 COALESCE((SELECT jsonb_agg(jsonb_build_object('id',r.id,'code',r.code,'currency',r.currency,'nightly_total_minor',r.nightly_total_minor,'policy_reference',r.policy_reference) ORDER BY r.code)
 FROM worthkind_flow.bookable_rates r WHERE r.property_id=v_property AND r.room_type_id=t.id AND r.active AND r.start_date<=p_arrival AND r.end_date>=p_departure),'[]'::jsonb) AS rates
 FROM worthkind_flow.room_types t WHERE t.property_id=v_property AND t.published ORDER BY t.code LIMIT 500)x),'[]'::jsonb);
END $$;

CREATE FUNCTION worthkind_flow.change_native_booking(p_slug text,p_case uuid,p_hash text,p_booking uuid,p_revision bigint,p_arrival date,p_departure date,p_rate uuid,p_expected_total bigint,p_expected_currency text,p_policy text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; b worthkind_flow.native_bookings%ROWTYPE; rate worthkind_flow.bookable_rates%ROWTYPE; picked uuid[]; room uuid; v_total bigint; old_values jsonb;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 PERFORM 1 FROM worthkind_flow.properties WHERE id=v_property FOR UPDATE;
 PERFORM worthkind_flow.expire_native_holds(v_property);
 SELECT x.* INTO b FROM worthkind_flow.native_bookings x JOIN worthkind_flow.reservation_intents r ON r.id=x.intent_id AND r.property_id=x.property_id
 WHERE x.id=p_booking AND x.property_id=v_property AND r.case_id=p_case FOR UPDATE OF x,r;
 IF NOT FOUND THEN RAISE EXCEPTION 'Booking unavailable' USING ERRCODE='P0002'; END IF;
 IF b.state<>'confirmed' OR b.revision<>p_revision OR b.arrival<=(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=v_property)
 OR NOT EXISTS(SELECT 1 FROM worthkind_flow.native_booking_accounts WHERE property_id=v_property AND enabled) THEN
 RAISE EXCEPTION 'Booking cannot be changed' USING ERRCODE='23514'; END IF;
 IF p_arrival IS NULL OR p_departure IS NULL OR p_departure-p_arrival NOT BETWEEN 1 AND 90
 OR p_arrival<(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=v_property) THEN RAISE EXCEPTION 'Invalid dates' USING ERRCODE='22023'; END IF;
 SELECT * INTO rate FROM worthkind_flow.bookable_rates r WHERE r.id=p_rate AND r.property_id=v_property AND r.room_type_id=b.room_type_id AND r.active AND r.start_date<=p_arrival AND r.end_date>=p_departure;
 IF NOT FOUND THEN RAISE EXCEPTION 'Rate unavailable' USING ERRCODE='P0002'; END IF;
 v_total:=rate.nightly_total_minor*b.room_count*(p_departure-p_arrival);
 IF v_total IS DISTINCT FROM p_expected_total OR rate.currency IS DISTINCT FROM p_expected_currency OR rate.policy_reference IS DISTINCT FROM p_policy OR rate.currency<>b.currency THEN RAISE EXCEPTION 'Quote changed' USING ERRCODE='23514'; END IF;
 SELECT array_agg(x.id) INTO picked FROM (SELECT h.id FROM worthkind_flow.hotel_rooms h
 WHERE h.property_id=v_property AND h.room_type_id=b.room_type_id AND h.operational_state IN ('clean','dirty','inspecting')
 AND NOT EXISTS(SELECT 1 FROM worthkind_flow.booking_room_nights n WHERE n.property_id=v_property AND n.room_id=h.id AND n.booking_id<>b.id AND n.night>=p_arrival AND n.night<p_departure)
 ORDER BY h.label,h.id LIMIT b.room_count FOR UPDATE)x;
 IF COALESCE(cardinality(picked),0)<>b.room_count THEN RAISE EXCEPTION 'Insufficient inventory; existing reservation preserved' USING ERRCODE='23514'; END IF;
 old_values:=jsonb_build_object('arrival',b.arrival,'departure',b.departure,'total_minor',b.total_minor,'rate_id',b.rate_id,'revision',b.revision);
 DELETE FROM worthkind_flow.booking_room_nights WHERE booking_id=b.id AND property_id=v_property;
 UPDATE worthkind_flow.native_bookings SET arrival=p_arrival,departure=p_departure,rate_id=p_rate,nightly_total_minor=rate.nightly_total_minor,
 total_minor=v_total,policy_reference=rate.policy_reference,revision=revision+1 WHERE id=b.id RETURNING * INTO b;
 FOREACH room IN ARRAY picked LOOP
 INSERT INTO worthkind_flow.booking_room_nights(property_id,booking_id,room_id,night)
 SELECT v_property,b.id,room,p_arrival+d FROM generate_series(0,p_departure-p_arrival-1)d;
 END LOOP;
 INSERT INTO worthkind_flow.native_booking_events(property_id,booking_id,action,details)
 VALUES(v_property,b.id,'guest_changed_dates',jsonb_build_object('previous',old_values,'arrival',p_arrival,'departure',p_departure,'total_minor',v_total));
 RETURN to_jsonb(b)-'created_by'-'property_id';
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.native_availability(text,date,date),worthkind_flow.change_native_booking(text,uuid,text,uuid,bigint,date,date,uuid,bigint,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.native_availability(text,date,date) TO wf_public_content;
GRANT EXECUTE ON FUNCTION worthkind_flow.change_native_booking(text,uuid,text,uuid,bigint,date,date,uuid,bigint,text,text) TO wf_guest_api;
COMMIT;
