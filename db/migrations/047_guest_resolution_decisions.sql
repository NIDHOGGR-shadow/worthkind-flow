BEGIN;
-- A guest decision refers to one specific staff resolution, never a later one.
ALTER TABLE worthkind_flow.case_control_events
 ADD CONSTRAINT wf_case_control_scope_unique UNIQUE(id,property_id,case_id);
CREATE INDEX wf_case_resolution_history ON worthkind_flow.case_control_events(property_id,case_id,created_at DESC,id DESC) WHERE action='resolve';

CREATE TABLE worthkind_flow.guest_resolution_decisions(
 resolution_id uuid PRIMARY KEY,
 property_id uuid NOT NULL,
 case_id uuid NOT NULL,
 decision text NOT NULL CHECK(decision IN ('confirm','reopen')),
 created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
 FOREIGN KEY(resolution_id,property_id,case_id) REFERENCES worthkind_flow.case_control_events(id,property_id,case_id),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id)
);
ALTER TABLE worthkind_flow.guest_resolution_decisions ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_resolution_decisions FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.guest_resolution_decisions FROM PUBLIC;

-- Internal helper. Only the receipt-authorized and staff-authorized wrappers
-- may call this; no runtime role receives direct EXECUTE or table access.
CREATE FUNCTION worthkind_flow.case_resolution_snapshot(p_property uuid,p_case uuid)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE c worthkind_flow.guest_cases%ROWTYPE; v_resolution uuid; v_decision text;
BEGIN
 SELECT * INTO c FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=p_property;
 IF NOT FOUND THEN RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 SELECT e.id,d.decision INTO v_resolution,v_decision
 FROM worthkind_flow.case_control_events e LEFT JOIN worthkind_flow.guest_resolution_decisions d ON d.resolution_id=e.id
 WHERE e.property_id=p_property AND e.case_id=p_case AND e.action='resolve'
 ORDER BY e.created_at DESC,e.id DESC LIMIT 1;
 RETURN jsonb_build_object('case_id',p_case,'case_status',c.state,'resolution_id',v_resolution,
 'guest_decision',v_decision,'guest_confirmed',COALESCE(c.state='resolved' AND v_decision='confirm',false),
 'awaiting_guest_confirmation',c.state='resolved' AND v_resolution IS NOT NULL AND v_decision IS NULL);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.case_resolution_snapshot(uuid,uuid) FROM PUBLIC;

CREATE FUNCTION worthkind_flow.read_guest_resolution(p_slug text,p_case uuid,p_hash text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 RETURN worthkind_flow.case_resolution_snapshot(worthkind_flow.verified_guest_case(p_slug,p_case,p_hash),p_case);
END $$;
CREATE FUNCTION worthkind_flow.read_staff_resolution(p_subject text,p_slug text,p_case uuid)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN worthkind_flow.case_resolution_snapshot(a.property_id,p_case);
END $$;

CREATE FUNCTION worthkind_flow.decide_guest_resolution(p_slug text,p_case uuid,p_hash text,p_resolution uuid,p_decision text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; c worthkind_flow.guest_cases%ROWTYPE; v_latest uuid; v_previous text; v_event text;
BEGIN
 IF p_resolution IS NULL OR p_decision IS NULL OR p_decision NOT IN ('confirm','reopen') THEN
 RAISE EXCEPTION 'Invalid guest decision' USING ERRCODE='22023'; END IF;
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 SELECT * INTO c FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=v_property FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 SELECT decision INTO v_previous FROM worthkind_flow.guest_resolution_decisions
 WHERE resolution_id=p_resolution AND property_id=v_property AND case_id=p_case;
 IF FOUND THEN
  IF v_previous<>p_decision THEN RAISE EXCEPTION 'Resolution already decided' USING ERRCODE='23514'; END IF;
  RETURN jsonb_build_object('resolution_id',p_resolution,'decision',v_previous,'duplicate',true,'current_case_status',c.state);
 END IF;
 SELECT id INTO v_latest FROM worthkind_flow.case_control_events
 WHERE property_id=v_property AND case_id=p_case AND action='resolve' ORDER BY created_at DESC,id DESC LIMIT 1;
 IF c.state<>'resolved' OR v_latest IS DISTINCT FROM p_resolution THEN
 RAISE EXCEPTION 'Resolution no longer available' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.guest_resolution_decisions(resolution_id,property_id,case_id,decision)
 VALUES(p_resolution,v_property,p_case,p_decision);
 IF p_decision='reopen' THEN
  -- Return to the accountable reception queue; an old assignee may be revoked.
  UPDATE worthkind_flow.guest_cases SET state='queued',assigned_membership_id=NULL,updated_at=now()
  WHERE id=p_case AND property_id=v_property RETURNING * INTO c;
  v_event:='guest_case_reopened';
 ELSE
  v_event:='guest_resolution_confirmed';
 END IF;
 INSERT INTO worthkind_flow.case_audit_events(property_id,case_id,action) VALUES(v_property,p_case,v_event);
 INSERT INTO worthkind_flow.event_outbox(property_id,case_id,event_type) VALUES(v_property,p_case,v_event);
 RETURN jsonb_build_object('resolution_id',p_resolution,'decision',p_decision,'duplicate',false,'current_case_status',c.state);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.read_guest_resolution(text,uuid,text),worthkind_flow.read_staff_resolution(text,text,uuid),worthkind_flow.decide_guest_resolution(text,uuid,text,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.read_guest_resolution(text,uuid,text),worthkind_flow.decide_guest_resolution(text,uuid,text,uuid,text) TO wf_guest_api;
GRANT EXECUTE ON FUNCTION worthkind_flow.read_staff_resolution(text,text,uuid) TO wf_operations;
COMMIT;
