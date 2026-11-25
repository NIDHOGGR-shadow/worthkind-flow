BEGIN;
CREATE TABLE worthkind_flow.case_control_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,case_id uuid NOT NULL,actor uuid NOT NULL,
 action text NOT NULL,encrypted_reason bytea NOT NULL CHECK(octet_length(encrypted_reason) BETWEEN 29 AND 16000),
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.case_control_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.case_control_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.case_control_events FROM PUBLIC;
CREATE FUNCTION worthkind_flow.control_reception_case(p_subject text,p_slug text,p_case uuid,p_action text,p_target uuid,p_reason bytea)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; c worthkind_flow.guest_cases%ROWTYPE; v_state text; v_assignee uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO c FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 IF a.member_role='reception' AND c.assigned_membership_id IS DISTINCT FROM a.member_id THEN RAISE EXCEPTION 'Case ownership required' USING ERRCODE='42501'; END IF;
 v_assignee=c.assigned_membership_id;
 IF p_action='transfer' AND c.state IN ('claimed','responded','escalated') AND p_target IS NOT NULL THEN
  IF NOT EXISTS(SELECT 1 FROM worthkind_flow.staff_memberships m JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id
   WHERE m.id=p_target AND m.property_id=a.property_id AND m.state='active' AND i.state='active' AND m.role IN ('owner','manager','reception')) THEN
   RAISE EXCEPTION 'Target unavailable' USING ERRCODE='P0002'; END IF;
  v_state='claimed';v_assignee=p_target;
 ELSIF p_action='escalate' AND c.state IN ('claimed','responded') AND p_target IS NULL THEN v_state='escalated';
 ELSIF p_action='resolve' AND c.state IN ('responded','escalated') AND p_target IS NULL THEN v_state='resolved';
 ELSE RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.guest_cases SET state=v_state,assigned_membership_id=v_assignee,updated_at=now() WHERE id=c.id;
 INSERT INTO worthkind_flow.case_control_events(property_id,case_id,actor,action,encrypted_reason) VALUES(a.property_id,c.id,a.member_id,p_action,p_reason);
 INSERT INTO worthkind_flow.case_audit_events(property_id,case_id,actor_membership_id,action) VALUES(a.property_id,c.id,a.member_id,'case_'||p_action);
 INSERT INTO worthkind_flow.event_outbox(property_id,case_id,event_type) VALUES(a.property_id,c.id,'case_'||p_action);
 RETURN v_state;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.control_reception_case(text,text,uuid,text,uuid,bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.control_reception_case(text,text,uuid,text,uuid,bytea) TO wf_operations;
COMMIT;
