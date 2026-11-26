BEGIN;
CREATE TABLE worthkind_flow.reception_handovers(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 sender_id uuid NOT NULL, recipient_id uuid NOT NULL, case_id uuid,
 request_key uuid NOT NULL, payload_hash text NOT NULL CHECK(payload_hash ~ '^[a-f0-9]{64}$'),
 encrypted_note bytea NOT NULL CHECK(octet_length(encrypted_note) BETWEEN 29 AND 12000),
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','acknowledged','cancelled')),
 created_at timestamptz NOT NULL DEFAULT now(), decided_at timestamptz, decided_by uuid,
 CHECK(sender_id<>recipient_id),
 CHECK((state='pending' AND decided_at IS NULL AND decided_by IS NULL) OR
 (state<>'pending' AND decided_at IS NOT NULL AND decided_by IS NOT NULL)),
 UNIQUE(property_id,request_key),
 FOREIGN KEY(sender_id,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(recipient_id,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(decided_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id)
);
CREATE INDEX wf_handover_property_cursor ON worthkind_flow.reception_handovers(property_id,id);
CREATE INDEX wf_handover_recipient ON worthkind_flow.reception_handovers(property_id,recipient_id,state,id);
ALTER TABLE worthkind_flow.reception_handovers ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.reception_handovers FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.reception_handovers FROM PUBLIC;
CREATE FUNCTION worthkind_flow.handover_recipients(p_subject text,p_slug text,p_after uuid,p_limit integer)
RETURNS TABLE(member_id uuid,role text,display_name text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT m.id,m.role,p.display_name FROM worthkind_flow.staff_memberships m
 JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id
 LEFT JOIN worthkind_flow.staff_profiles p ON p.membership_id=m.id AND p.property_id=m.property_id
 WHERE m.property_id=a.property_id AND m.id<>a.member_id AND m.state='active' AND i.state='active'
 AND m.role IN ('owner','manager','reception') AND (p_after IS NULL OR m.id>p_after)
 ORDER BY m.id LIMIT p_limit;
END $$;
CREATE FUNCTION worthkind_flow.create_reception_handover(p_subject text,p_slug text,p_target uuid,p_case uuid,p_key uuid,p_hash text,p_note bytea)
RETURNS TABLE(handover_id uuid,handover_state text,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; h worthkind_flow.reception_handovers%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_target IS NULL OR p_target=a.member_id OR p_key IS NULL THEN RAISE EXCEPTION 'Invalid handover' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO h FROM worthkind_flow.reception_handovers WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
  IF h.sender_id<>a.member_id OR h.payload_hash IS DISTINCT FROM p_hash OR h.recipient_id<>p_target OR h.case_id IS DISTINCT FROM p_case THEN
   RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
  RETURN QUERY SELECT h.id,h.state,true; RETURN;
 END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.staff_memberships m JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id
 WHERE m.id=p_target AND m.property_id=a.property_id AND m.state='active' AND i.state='active' AND m.role IN ('owner','manager','reception')) THEN
 RAISE EXCEPTION 'Recipient unavailable' USING ERRCODE='P0002'; END IF;
 IF p_case IS NOT NULL AND NOT EXISTS(SELECT 1 FROM worthkind_flow.guest_cases c WHERE c.id=p_case AND c.property_id=a.property_id
 AND c.state IN ('queued','claimed','responded','escalated') AND (a.member_role IN ('owner','manager') OR c.assigned_membership_id=a.member_id)) THEN
 RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.reception_handovers(property_id,sender_id,recipient_id,case_id,request_key,payload_hash,encrypted_note)
 VALUES(a.property_id,a.member_id,p_target,p_case,p_key,p_hash,p_note) RETURNING * INTO h;
 INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,h.id,'handover_created');
 RETURN QUERY SELECT h.id,h.state,false;
END $$;
CREATE FUNCTION worthkind_flow.list_reception_handovers(p_subject text,p_slug text,p_after uuid,p_limit integer,p_pending boolean)
RETURNS TABLE(handover_id uuid,sender_id uuid,recipient_id uuid,case_id uuid,request_key uuid,encrypted_note bytea,handover_state text,created_at timestamptz,decided_at timestamptz,decided_by uuid)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 OR p_pending IS NULL THEN RAISE EXCEPTION 'Invalid list request' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT h.id,h.sender_id,h.recipient_id,h.case_id,h.request_key,h.encrypted_note,h.state,h.created_at,h.decided_at,h.decided_by
 FROM worthkind_flow.reception_handovers h WHERE h.property_id=a.property_id
 AND (a.member_role IN ('owner','manager') OR a.member_id IN (h.sender_id,h.recipient_id))
 AND (NOT p_pending OR h.state='pending') AND (p_after IS NULL OR h.id>p_after)
 ORDER BY h.id LIMIT p_limit;
END $$;
CREATE FUNCTION worthkind_flow.decide_reception_handover(p_subject text,p_slug text,p_id uuid,p_action text)
RETURNS TABLE(handover_state text,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; h worthkind_flow.reception_handovers%ROWTYPE; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action IS NULL OR p_action NOT IN ('acknowledge','cancel') THEN RAISE EXCEPTION 'Invalid action' USING ERRCODE='22023'; END IF;
 SELECT * INTO h FROM worthkind_flow.reception_handovers WHERE property_id=a.property_id AND id=p_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Handover unavailable' USING ERRCODE='P0002'; END IF;
 IF (p_action='acknowledge' AND a.member_id<>h.recipient_id) OR
 (p_action='cancel' AND a.member_id<>h.sender_id AND a.member_role NOT IN ('owner','manager')) THEN
 RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 v_state:=CASE WHEN p_action='acknowledge' THEN 'acknowledged' ELSE 'cancelled' END;
 IF h.state=v_state THEN RETURN QUERY SELECT h.state,true; RETURN; END IF;
 IF h.state<>'pending' THEN RAISE EXCEPTION 'Handover already decided' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.reception_handovers SET state=v_state,decided_at=now(),decided_by=a.member_id WHERE id=h.id;
 INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,h.id,'handover_'||v_state);
 RETURN QUERY SELECT v_state,false;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.handover_recipients(text,text,uuid,integer),worthkind_flow.create_reception_handover(text,text,uuid,uuid,uuid,text,bytea),worthkind_flow.list_reception_handovers(text,text,uuid,integer,boolean),worthkind_flow.decide_reception_handover(text,text,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.handover_recipients(text,text,uuid,integer),worthkind_flow.create_reception_handover(text,text,uuid,uuid,uuid,text,bytea),worthkind_flow.list_reception_handovers(text,text,uuid,integer,boolean),worthkind_flow.decide_reception_handover(text,text,uuid,text) TO wf_operations;
COMMIT;
