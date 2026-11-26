BEGIN;
CREATE TABLE worthkind_flow.reservation_intents(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,case_id uuid NOT NULL,
 room_type_id uuid,arrival date NOT NULL,departure date NOT NULL CHECK(departure>arrival AND departure-arrival<=90),
 adults integer NOT NULL CHECK(adults BETWEEN 1 AND 30),children integer NOT NULL CHECK(children BETWEEN 0 AND 30),
 room_count integer NOT NULL CHECK(room_count BETWEEN 1 AND 10),
 request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 state text NOT NULL DEFAULT 'requested' CHECK(state IN ('requested','under_review','declined','withdrawn')),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),UNIQUE(id,property_id),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id),
 FOREIGN KEY(room_type_id,property_id) REFERENCES worthkind_flow.room_types(id,property_id)
);
CREATE TABLE worthkind_flow.reservation_intent_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,intent_id uuid NOT NULL,
 actor uuid,action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(intent_id,property_id) REFERENCES worthkind_flow.reservation_intents(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.reservation_intents ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.reservation_intents FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.reservation_intent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.reservation_intent_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.reservation_intents,worthkind_flow.reservation_intent_events FROM PUBLIC;
CREATE FUNCTION worthkind_flow.request_reservation(p_slug text,p_case uuid,p_hash text,p_type uuid,p_arrival date,p_departure date,p_adults integer,p_children integer,p_rooms integer,p_key text)
RETURNS TABLE(id uuid,state text,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; r worthkind_flow.reservation_intents%ROWTYPE;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 PERFORM 1 FROM worthkind_flow.guest_cases c WHERE c.id=p_case AND c.property_id=v_property AND c.kind='booking' AND c.state NOT IN ('cancelled','resolved') FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Booking case unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO r FROM worthkind_flow.reservation_intents x WHERE x.property_id=v_property AND x.request_key=p_key;
 IF FOUND THEN
 IF r.case_id<>p_case OR r.room_type_id IS DISTINCT FROM p_type OR r.arrival<>p_arrival OR r.departure<>p_departure OR r.adults<>p_adults OR r.children<>p_children OR r.room_count<>p_rooms THEN
 RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN QUERY SELECT r.id,r.state,true; RETURN; END IF;
 IF p_arrival<(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=v_property) THEN RAISE EXCEPTION 'Past arrival' USING ERRCODE='22023'; END IF;
 IF p_type IS NOT NULL AND NOT EXISTS(SELECT 1 FROM worthkind_flow.room_types t WHERE t.id=p_type AND t.property_id=v_property AND t.published AND t.max_guests*p_rooms>=p_adults+p_children) THEN
 RAISE EXCEPTION 'Room type unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.reservation_intents(property_id,case_id,room_type_id,arrival,departure,adults,children,room_count,request_key)
 VALUES(v_property,p_case,p_type,p_arrival,p_departure,p_adults,p_children,p_rooms,p_key) RETURNING * INTO r;
 INSERT INTO worthkind_flow.reservation_intent_events(property_id,intent_id,action) VALUES(v_property,r.id,'requested');
 RETURN QUERY SELECT r.id,r.state,false;
END $$;
CREATE FUNCTION worthkind_flow.withdraw_reservation(p_slug text,p_case uuid,p_hash text,p_intent uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 UPDATE worthkind_flow.reservation_intents SET state='withdrawn',updated_at=now()
 WHERE id=p_intent AND property_id=v_property AND case_id=p_case AND state IN ('requested','under_review');
 IF NOT FOUND THEN RAISE EXCEPTION 'Intent unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.reservation_intent_events(property_id,intent_id,action) VALUES(v_property,p_intent,'withdrawn');
 RETURN 'withdrawn';
END $$;
CREATE FUNCTION worthkind_flow.reservation_queue(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (
 SELECT r.id,r.case_id,r.room_type_id,r.arrival,r.departure,r.adults,r.children,r.room_count,r.state,r.created_at
 FROM worthkind_flow.reservation_intents r WHERE r.property_id=a.property_id ORDER BY r.created_at DESC LIMIT 200)x),'[]'::jsonb);
END $$;
CREATE FUNCTION worthkind_flow.review_reservation_intent(p_subject text,p_slug text,p_intent uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 UPDATE worthkind_flow.reservation_intents r SET state=CASE p_action WHEN 'review' THEN 'under_review' WHEN 'decline' THEN 'declined' END,updated_at=now()
 WHERE r.id=p_intent AND r.property_id=a.property_id AND ((p_action='review' AND r.state='requested') OR (p_action='decline' AND r.state IN ('requested','under_review')))
 RETURNING state INTO v_state;
 IF NOT FOUND THEN RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.reservation_intent_events(property_id,intent_id,actor,action) VALUES(a.property_id,p_intent,a.member_id,p_action);
 RETURN v_state;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.request_reservation(text,uuid,text,uuid,date,date,integer,integer,integer,text),
 worthkind_flow.withdraw_reservation(text,uuid,text,uuid),worthkind_flow.reservation_queue(text,text),
 worthkind_flow.review_reservation_intent(text,text,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.request_reservation(text,uuid,text,uuid,date,date,integer,integer,integer,text),
 worthkind_flow.withdraw_reservation(text,uuid,text,uuid) TO wf_guest_api;
GRANT EXECUTE ON FUNCTION worthkind_flow.reservation_queue(text,text),worthkind_flow.review_reservation_intent(text,text,uuid,text) TO wf_operations;
COMMIT;
