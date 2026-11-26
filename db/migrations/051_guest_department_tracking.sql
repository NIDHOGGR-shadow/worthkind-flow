BEGIN;
CREATE FUNCTION worthkind_flow.guest_venue_requests(p_slug text,p_case uuid,p_hash text,p_after uuid,p_limit integer)
RETURNS TABLE(request_id uuid,venue_id uuid,venue_name text,starts_at timestamptz,ends_at timestamptz,attendance integer,state text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT r.id,r.venue_id,v.name,r.starts_at,r.ends_at,r.attendance,r.state FROM worthkind_flow.venue_requests r
 JOIN worthkind_flow.event_venues v ON v.id=r.venue_id AND v.property_id=r.property_id
 WHERE r.property_id=v_property AND r.case_id=p_case AND (p_after IS NULL OR r.id>p_after) ORDER BY r.id LIMIT p_limit;
END $$;
CREATE FUNCTION worthkind_flow.guest_applications(p_slug text,p_case uuid,p_hash text,p_after uuid,p_limit integer)
RETURNS TABLE(application_id uuid,vacancy_id uuid,title text,state text,created_at timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT j.id,j.vacancy_id,v.title,j.state,j.created_at FROM worthkind_flow.job_applications j
 JOIN worthkind_flow.vacancies v ON v.id=j.vacancy_id AND v.property_id=j.property_id
 WHERE j.property_id=v_property AND j.case_id=p_case AND (p_after IS NULL OR j.id>p_after) ORDER BY j.id LIMIT p_limit;
END $$;
CREATE FUNCTION worthkind_flow.request_venue_with_state(p_slug text,p_case uuid,p_hash text,p_venue uuid,p_start timestamptz,p_end timestamptz,p_attendance integer,p_key text)
RETURNS TABLE(request_id uuid,state text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_id uuid;
BEGIN
 v_id:=worthkind_flow.request_venue(p_slug,p_case,p_hash,p_venue,p_start,p_end,p_attendance,p_key);
 RETURN QUERY SELECT r.id,r.state FROM worthkind_flow.venue_requests r
 WHERE r.id=v_id AND r.case_id=p_case AND r.property_id=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
END $$;
CREATE FUNCTION worthkind_flow.withdraw_guest_application(p_slug text,p_case uuid,p_hash text,p_id uuid)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; j worthkind_flow.job_applications%ROWTYPE;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 SELECT * INTO j FROM worthkind_flow.job_applications WHERE id=p_id AND property_id=v_property AND case_id=p_case FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Application unavailable' USING ERRCODE='P0002'; END IF;
 IF j.state='withdrawn' THEN RETURN 'withdrawn'; END IF;
 IF j.state NOT IN ('submitted','reviewing','shortlisted') THEN RAISE EXCEPTION 'Application cannot be withdrawn' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.job_applications SET state='withdrawn' WHERE id=j.id;
 INSERT INTO worthkind_flow.department_events(property_id,resource_id,domain,action) VALUES(v_property,j.id,'recruitment','application_withdrawn');
 RETURN 'withdrawn';
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.guest_venue_requests(text,uuid,text,uuid,integer),worthkind_flow.guest_applications(text,uuid,text,uuid,integer),worthkind_flow.request_venue_with_state(text,uuid,text,uuid,timestamptz,timestamptz,integer,text),worthkind_flow.withdraw_guest_application(text,uuid,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.guest_venue_requests(text,uuid,text,uuid,integer),worthkind_flow.guest_applications(text,uuid,text,uuid,integer),worthkind_flow.request_venue_with_state(text,uuid,text,uuid,timestamptz,timestamptz,integer,text),worthkind_flow.withdraw_guest_application(text,uuid,text,uuid) TO wf_guest_api;
COMMIT;
