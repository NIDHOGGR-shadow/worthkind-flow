BEGIN;
CREATE TABLE worthkind_flow.staff_profiles(
 membership_id uuid PRIMARY KEY,property_id uuid NOT NULL,
 display_name text NOT NULL CHECK(length(btrim(display_name)) BETWEEN 2 AND 120),
 job_title text NOT NULL CHECK(length(btrim(job_title)) BETWEEN 2 AND 100),
 employee_reference text NOT NULL CHECK(length(btrim(employee_reference)) BETWEEN 2 AND 80),
 updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,employee_reference),
 FOREIGN KEY(membership_id,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.staff_shifts(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,membership_id uuid NOT NULL,
 starts_at timestamptz NOT NULL,ends_at timestamptz NOT NULL CHECK(ends_at>starts_at AND ends_at-starts_at<=interval '24 hours'),
 state text NOT NULL DEFAULT 'scheduled' CHECK(state IN ('scheduled','cancelled')),
 created_by uuid NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(membership_id,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(created_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE INDEX wf_shift_staff_time ON worthkind_flow.staff_shifts(property_id,membership_id,starts_at,ends_at) WHERE state='scheduled';
CREATE TABLE worthkind_flow.staff_operation_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor uuid NOT NULL,resource_id uuid NOT NULL,action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.staff_profiles ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_profiles FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_shifts ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_shifts FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_operation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_operation_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.staff_profiles,worthkind_flow.staff_shifts,worthkind_flow.staff_operation_events FROM PUBLIC;
CREATE FUNCTION worthkind_flow.save_staff_profile(p_subject text,p_slug text,p_member uuid,p_name text,p_title text,p_ref text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','hr') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.staff_memberships m WHERE m.id=p_member AND m.property_id=a.property_id AND m.state='active'
 AND (m.role NOT IN ('owner','manager') OR a.member_role='owner' OR m.id=a.member_id)) THEN RAISE EXCEPTION 'Membership unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.staff_profiles(membership_id,property_id,display_name,job_title,employee_reference)
 VALUES(p_member,a.property_id,p_name,p_title,p_ref)
 ON CONFLICT(membership_id) DO UPDATE SET display_name=EXCLUDED.display_name,job_title=EXCLUDED.job_title,employee_reference=EXCLUDED.employee_reference,updated_at=now();
 INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,p_member,'profile_saved');
 RETURN p_member;
END $$;
CREATE FUNCTION worthkind_flow.schedule_staff_shift(p_subject text,p_slug text,p_member uuid,p_start timestamptz,p_end timestamptz)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','hr') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_end<=p_start OR p_end-p_start>interval '24 hours' THEN RAISE EXCEPTION 'Invalid shift' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM worthkind_flow.staff_memberships m WHERE m.id=p_member AND m.property_id=a.property_id AND m.state='active'
 AND (m.role NOT IN ('owner','manager') OR a.member_role='owner' OR m.id=a.member_id) FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Membership unavailable' USING ERRCODE='P0002'; END IF;
 IF EXISTS(SELECT 1 FROM worthkind_flow.staff_shifts s WHERE s.membership_id=p_member AND s.property_id=a.property_id AND s.state='scheduled'
 AND s.starts_at<p_end AND s.ends_at>p_start) THEN RAISE EXCEPTION 'Overlapping shift' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.staff_shifts(property_id,membership_id,starts_at,ends_at,created_by)
 VALUES(a.property_id,p_member,p_start,p_end,a.member_id) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'shift_scheduled');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.cancel_staff_shift(p_subject text,p_slug text,p_shift uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','hr') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 UPDATE worthkind_flow.staff_shifts s SET state='cancelled'
 WHERE s.id=p_shift AND s.property_id=a.property_id AND s.state='scheduled' AND EXISTS(
 SELECT 1 FROM worthkind_flow.staff_memberships m WHERE m.id=s.membership_id AND (m.role NOT IN ('owner','manager') OR a.member_role='owner' OR m.id=a.member_id))
 RETURNING s.id INTO v_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Shift unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.staff_operation_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'shift_cancelled');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.staff_schedule(p_subject text,p_slug text,p_start timestamptz,p_end timestamptz)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_start IS NULL OR p_end IS NULL OR p_end<=p_start OR p_end-p_start>interval '93 days' THEN RAISE EXCEPTION 'Invalid schedule range' USING ERRCODE='22023'; END IF;
 RETURN jsonb_build_object(
 'members',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (
 SELECT m.id AS membership_id,m.role,m.state,p.display_name,p.job_title,p.employee_reference
 FROM worthkind_flow.staff_memberships m LEFT JOIN worthkind_flow.staff_profiles p ON p.membership_id=m.id
 WHERE m.property_id=a.property_id AND (a.member_role IN ('owner','manager','hr') OR m.id=a.member_id)
 ORDER BY m.id LIMIT 500)x),'[]'::jsonb),
 'shifts',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (
 SELECT s.id,s.membership_id,s.starts_at,s.ends_at,s.state
 FROM worthkind_flow.staff_shifts s WHERE s.property_id=a.property_id AND s.starts_at<p_end AND s.ends_at>p_start
 AND (a.member_role IN ('owner','manager','hr') OR s.membership_id=a.member_id)
 ORDER BY s.starts_at,s.id LIMIT 1000)x),'[]'::jsonb));
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.save_staff_profile(text,text,uuid,text,text,text),worthkind_flow.schedule_staff_shift(text,text,uuid,timestamptz,timestamptz),
 worthkind_flow.cancel_staff_shift(text,text,uuid),worthkind_flow.staff_schedule(text,text,timestamptz,timestamptz) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.save_staff_profile(text,text,uuid,text,text,text),worthkind_flow.schedule_staff_shift(text,text,uuid,timestamptz,timestamptz),
 worthkind_flow.cancel_staff_shift(text,text,uuid),worthkind_flow.staff_schedule(text,text,timestamptz,timestamptz) TO wf_operations;
COMMIT;
