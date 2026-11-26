BEGIN;
CREATE TABLE worthkind_flow.staff_attendance(
 shift_id uuid PRIMARY KEY REFERENCES worthkind_flow.staff_shifts(id),
 property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 membership_id uuid NOT NULL,
 checked_in_at timestamptz NOT NULL,
 checked_out_at timestamptz CHECK(checked_out_at>=checked_in_at),
 FOREIGN KEY(membership_id,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE INDEX wf_attendance_member ON worthkind_flow.staff_attendance(property_id,membership_id,checked_in_at);
ALTER TABLE worthkind_flow.staff_attendance ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_attendance FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.staff_attendance FROM PUBLIC;
CREATE FUNCTION worthkind_flow.guard_attended_shift()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF NEW.state='cancelled' AND OLD.state<>'cancelled' AND EXISTS(SELECT 1 FROM worthkind_flow.staff_attendance a WHERE a.shift_id=OLD.id) THEN
  RAISE EXCEPTION 'Attended shift cannot be cancelled' USING ERRCODE='23514';
 END IF;
 RETURN NEW;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.guard_attended_shift() FROM PUBLIC;
CREATE TRIGGER wf_attended_shift_guard BEFORE UPDATE OF state ON worthkind_flow.staff_shifts FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_attended_shift();
CREATE FUNCTION worthkind_flow.record_staff_attendance(p_subject text,p_slug text,p_shift uuid,p_action text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; s worthkind_flow.staff_shifts%ROWTYPE; t worthkind_flow.staff_attendance%ROWTYPE; duplicate boolean:=false; v_now timestamptz;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action IS NULL OR p_action NOT IN ('check_in','check_out') THEN RAISE EXCEPTION 'Invalid action' USING ERRCODE='22023'; END IF;
 SELECT * INTO s FROM worthkind_flow.staff_shifts WHERE id=p_shift AND property_id=a.property_id AND membership_id=a.member_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Shift unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO t FROM worthkind_flow.staff_attendance WHERE shift_id=s.id;
 v_now:=clock_timestamp();
 IF p_action='check_in' THEN
  IF t.shift_id IS NOT NULL THEN duplicate:=true;
  ELSE
   IF s.state<>'scheduled' OR v_now<s.starts_at OR v_now>=s.ends_at THEN RAISE EXCEPTION 'Shift not in check-in window' USING ERRCODE='23514'; END IF;
   INSERT INTO worthkind_flow.staff_attendance(shift_id,property_id,membership_id,checked_in_at)
   VALUES(s.id,a.property_id,a.member_id,v_now) RETURNING * INTO t;
  END IF;
 ELSE
  IF t.shift_id IS NULL THEN RAISE EXCEPTION 'Check in first' USING ERRCODE='23514'; END IF;
  IF t.checked_out_at IS NOT NULL THEN duplicate:=true;
  ELSE UPDATE worthkind_flow.staff_attendance SET checked_out_at=v_now WHERE shift_id=s.id RETURNING * INTO t; END IF;
 END IF;
 IF NOT duplicate THEN
  INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,s.id,'attendance_'||p_action);
 END IF;
 RETURN jsonb_build_object('shift_id',s.id,'checked_in_at',t.checked_in_at,'checked_out_at',t.checked_out_at,'duplicate',duplicate);
END $$;
CREATE FUNCTION worthkind_flow.list_staff_attendance(p_subject text,p_slug text,p_start timestamptz,p_end timestamptz,p_after uuid,p_limit integer)
RETURNS TABLE(shift_id uuid,membership_id uuid,starts_at timestamptz,ends_at timestamptz,checked_in_at timestamptz,checked_out_at timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_end<=p_start OR p_end-p_start>interval '93 days' OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 THEN
 RAISE EXCEPTION 'Invalid report range' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT s.id,s.membership_id,s.starts_at,s.ends_at,t.checked_in_at,t.checked_out_at
 FROM worthkind_flow.staff_shifts s LEFT JOIN worthkind_flow.staff_attendance t ON t.shift_id=s.id
 WHERE s.property_id=a.property_id AND s.state='scheduled' AND s.starts_at<p_end AND s.ends_at>p_start
 AND (a.member_role IN ('owner','manager','hr') OR s.membership_id=a.member_id) AND (p_after IS NULL OR s.id>p_after)
 ORDER BY s.id LIMIT p_limit;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.record_staff_attendance(text,text,uuid,text),worthkind_flow.list_staff_attendance(text,text,timestamptz,timestamptz,uuid,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.record_staff_attendance(text,text,uuid,text),worthkind_flow.list_staff_attendance(text,text,timestamptz,timestamptz,uuid,integer) TO wf_operations;
COMMIT;
