BEGIN;
CREATE TABLE worthkind_flow.staff_leave_requests(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 membership_id uuid NOT NULL,request_key uuid NOT NULL,
 starts_at timestamptz NOT NULL,ends_at timestamptz NOT NULL CHECK(ends_at>starts_at AND ends_at-starts_at<=interval '93 days'),
 leave_kind text NOT NULL CHECK(leave_kind IN ('annual','sick','personal','other')),
 state text NOT NULL DEFAULT 'requested' CHECK(state IN ('requested','approved','declined','withdrawn','cancelled')),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),
 FOREIGN KEY(membership_id,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE INDEX wf_leave_member ON worthkind_flow.staff_leave_requests(property_id,membership_id,starts_at,ends_at);
ALTER TABLE worthkind_flow.staff_leave_requests ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_leave_requests FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.staff_leave_requests FROM PUBLIC;
CREATE FUNCTION worthkind_flow.request_staff_leave(p_subject text,p_slug text,p_key uuid,p_start timestamptz,p_end timestamptz,p_kind text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; q worthkind_flow.staff_leave_requests%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_key IS NULL OR p_start IS NULL OR p_end IS NULL OR p_end<=p_start OR p_end-p_start>interval '93 days' OR p_kind IS NULL OR p_kind NOT IN ('annual','sick','personal','other') THEN
 RAISE EXCEPTION 'Invalid leave request' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM worthkind_flow.staff_memberships WHERE id=a.member_id FOR UPDATE;
 SELECT * INTO q FROM worthkind_flow.staff_leave_requests WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
 IF q.membership_id<>a.member_id OR q.starts_at<>p_start OR q.ends_at<>p_end OR q.leave_kind<>p_kind THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN jsonb_build_object('id',q.id,'state',q.state,'duplicate',true); END IF;
 IF p_end<=now() THEN RAISE EXCEPTION 'Leave must end in the future' USING ERRCODE='22023'; END IF;
 IF EXISTS(SELECT 1 FROM worthkind_flow.staff_leave_requests x WHERE x.property_id=a.property_id AND x.membership_id=a.member_id AND x.state IN ('requested','approved') AND x.starts_at<p_end AND x.ends_at>p_start) THEN RAISE EXCEPTION 'Overlapping leave' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.staff_leave_requests(property_id,membership_id,request_key,starts_at,ends_at,leave_kind)
 VALUES(a.property_id,a.member_id,p_key,p_start,p_end,p_kind) RETURNING * INTO q;
 INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,q.id,'leave_requested');
 RETURN jsonb_build_object('id',q.id,'state',q.state,'duplicate',false);
END $$;
CREATE FUNCTION worthkind_flow.decide_staff_leave(p_subject text,p_slug text,p_id uuid,p_action text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; q worthkind_flow.staff_leave_requests%ROWTYPE; target_role text; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action IS NULL OR p_action NOT IN ('approve','decline','withdraw','cancel') THEN RAISE EXCEPTION 'Invalid action' USING ERRCODE='22023'; END IF;
 SELECT * INTO q FROM worthkind_flow.staff_leave_requests WHERE id=p_id AND property_id=a.property_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Leave unavailable' USING ERRCODE='P0002'; END IF;
 SELECT m.role INTO target_role FROM worthkind_flow.staff_memberships m WHERE m.id=q.membership_id AND m.property_id=a.property_id FOR UPDATE;
 SELECT * INTO q FROM worthkind_flow.staff_leave_requests WHERE id=p_id AND property_id=a.property_id FOR UPDATE;
 IF p_action='withdraw' THEN
 IF a.member_id<>q.membership_id THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 ELSE
 IF a.member_id=q.membership_id OR a.member_role NOT IN ('owner','manager','hr') OR (target_role IN ('owner','manager') AND a.member_role<>'owner') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 END IF;
 v_state:=CASE p_action WHEN 'approve' THEN 'approved' WHEN 'decline' THEN 'declined' WHEN 'withdraw' THEN 'withdrawn' ELSE 'cancelled' END;
 IF q.state=v_state THEN RETURN jsonb_build_object('id',q.id,'state',q.state,'duplicate',true); END IF;
 IF (p_action='cancel' AND (q.state<>'approved' OR q.starts_at<=now())) OR (p_action<>'cancel' AND q.state<>'requested') THEN RAISE EXCEPTION 'Invalid leave transition' USING ERRCODE='23514'; END IF;
 IF p_action='approve' THEN
 IF q.ends_at<=now() OR EXISTS(SELECT 1 FROM worthkind_flow.staff_shifts s WHERE s.property_id=q.property_id AND s.membership_id=q.membership_id AND s.state='scheduled' AND s.starts_at<q.ends_at AND s.ends_at>q.starts_at) THEN RAISE EXCEPTION 'Resolve overlapping shifts before approval' USING ERRCODE='23514'; END IF;
 END IF;
 UPDATE worthkind_flow.staff_leave_requests SET state=v_state,updated_at=now() WHERE id=q.id;
 INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,q.id,'leave_'||v_state);
 RETURN jsonb_build_object('id',q.id,'state',v_state,'duplicate',false);
END $$;
CREATE FUNCTION worthkind_flow.guard_leave_shift()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF NEW.state='scheduled' THEN
 PERFORM 1 FROM worthkind_flow.staff_memberships WHERE id=NEW.membership_id FOR UPDATE;
 IF EXISTS(SELECT 1 FROM worthkind_flow.staff_leave_requests q WHERE q.property_id=NEW.property_id AND q.membership_id=NEW.membership_id AND q.state='approved' AND q.starts_at<NEW.ends_at AND q.ends_at>NEW.starts_at) THEN RAISE EXCEPTION 'Shift overlaps approved leave' USING ERRCODE='23514'; END IF;
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.guard_leave_shift() FROM PUBLIC;
CREATE TRIGGER wf_leave_shift_guard BEFORE INSERT OR UPDATE OF starts_at,ends_at,state,membership_id ON worthkind_flow.staff_shifts FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_leave_shift();
CREATE FUNCTION worthkind_flow.list_staff_leave(p_subject text,p_slug text,p_after uuid,p_limit integer)
RETURNS TABLE(id uuid,membership_id uuid,starts_at timestamptz,ends_at timestamptz,leave_kind text,state text,created_at timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT q.id,q.membership_id,q.starts_at,q.ends_at,q.leave_kind,q.state,q.created_at FROM worthkind_flow.staff_leave_requests q
 WHERE q.property_id=a.property_id AND (a.member_role IN ('owner','manager','hr') OR q.membership_id=a.member_id)
 AND (p_after IS NULL OR q.id>p_after) ORDER BY q.id LIMIT p_limit;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.request_staff_leave(text,text,uuid,timestamptz,timestamptz,text),worthkind_flow.decide_staff_leave(text,text,uuid,text),worthkind_flow.list_staff_leave(text,text,uuid,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.request_staff_leave(text,text,uuid,timestamptz,timestamptz,text),worthkind_flow.decide_staff_leave(text,text,uuid,text),worthkind_flow.list_staff_leave(text,text,uuid,integer) TO wf_operations;
COMMIT;
