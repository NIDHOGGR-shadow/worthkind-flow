BEGIN;
CREATE TABLE worthkind_flow.event_venues(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 name text NOT NULL CHECK(length(btrim(name)) BETWEEN 2 AND 120),capacity integer NOT NULL CHECK(capacity BETWEEN 1 AND 100000),
 active boolean NOT NULL DEFAULT true,UNIQUE(property_id,name),UNIQUE(id,property_id)
);
CREATE TABLE worthkind_flow.venue_requests(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,case_id uuid NOT NULL,
 venue_id uuid NOT NULL,starts_at timestamptz NOT NULL,ends_at timestamptz NOT NULL CHECK(ends_at>starts_at AND ends_at-starts_at<=interval '7 days'),
 attendance integer NOT NULL CHECK(attendance>0),state text NOT NULL DEFAULT 'requested' CHECK(state IN ('requested','reviewed','accepted','declined','cancelled')),
 request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(property_id,request_key),UNIQUE(id,property_id),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id),
 FOREIGN KEY(venue_id,property_id) REFERENCES worthkind_flow.event_venues(id,property_id)
);
CREATE INDEX wf_venue_bookings ON worthkind_flow.venue_requests(property_id,venue_id,starts_at,ends_at) WHERE state='accepted';
CREATE TABLE worthkind_flow.vacancies(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 title text NOT NULL CHECK(length(btrim(title)) BETWEEN 2 AND 160),description text NOT NULL CHECK(length(btrim(description)) BETWEEN 8 AND 4000),
 deadline date NOT NULL,state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','published','closed')),UNIQUE(id,property_id)
);
CREATE TABLE worthkind_flow.job_applications(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,vacancy_id uuid NOT NULL,case_id uuid NOT NULL,
 encrypted_application bytea NOT NULL CHECK(octet_length(encrypted_application) BETWEEN 29 AND 32000),
 state text NOT NULL DEFAULT 'submitted' CHECK(state IN ('submitted','reviewing','shortlisted','rejected','selected','withdrawn')),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(vacancy_id,case_id),UNIQUE(id,property_id),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id),
 FOREIGN KEY(vacancy_id,property_id) REFERENCES worthkind_flow.vacancies(id,property_id)
);
CREATE TABLE worthkind_flow.department_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor uuid,resource_id uuid NOT NULL,domain text NOT NULL CHECK(domain IN ('events','recruitment')),
 action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['event_venues','venue_requests','vacancies','job_applications','department_events'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
CREATE FUNCTION worthkind_flow.create_venue(p_subject text,p_slug text,p_name text,p_capacity integer)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','events') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 INSERT INTO worthkind_flow.event_venues(property_id,name,capacity) VALUES(a.property_id,p_name,p_capacity) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.department_events(property_id,actor,resource_id,domain,action) VALUES(a.property_id,a.member_id,v_id,'events','venue_created');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.public_venues(p_slug text)
RETURNS TABLE(id uuid,name text,capacity integer)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT v.id,v.name,v.capacity FROM worthkind_flow.event_venues v JOIN worthkind_flow.properties p ON p.id=v.property_id
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' AND v.active ORDER BY v.name
$$;
CREATE FUNCTION worthkind_flow.request_venue(p_slug text,p_case uuid,p_hash text,p_venue uuid,p_start timestamptz,p_end timestamptz,p_attendance integer,p_key text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; r worthkind_flow.venue_requests%ROWTYPE;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 PERFORM 1 FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=v_property AND kind='events' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO r FROM worthkind_flow.venue_requests WHERE property_id=v_property AND request_key=p_key;
 IF FOUND THEN
 IF r.case_id<>p_case OR r.venue_id<>p_venue OR r.starts_at<>p_start OR r.ends_at<>p_end OR r.attendance<>p_attendance THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN r.id; END IF;
 IF p_start<now() OR NOT EXISTS(SELECT 1 FROM worthkind_flow.event_venues WHERE id=p_venue AND property_id=v_property AND active AND capacity>=p_attendance) THEN RAISE EXCEPTION 'Venue unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.venue_requests(property_id,case_id,venue_id,starts_at,ends_at,attendance,request_key)
 VALUES(v_property,p_case,p_venue,p_start,p_end,p_attendance,p_key) RETURNING * INTO r;
 INSERT INTO worthkind_flow.department_events(property_id,resource_id,domain,action) VALUES(v_property,r.id,'events','requested');
 RETURN r.id;
END $$;
CREATE FUNCTION worthkind_flow.decide_venue(p_subject text,p_slug text,p_request uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; r worthkind_flow.venue_requests%ROWTYPE; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','events') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO r FROM worthkind_flow.venue_requests WHERE id=p_request AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Request unavailable' USING ERRCODE='P0002'; END IF;
 PERFORM 1 FROM worthkind_flow.event_venues v WHERE v.id=r.venue_id AND v.property_id=a.property_id FOR UPDATE;
 IF p_action='review' AND r.state='requested' THEN v_state='reviewed';
 ELSIF p_action='accept' AND r.state='reviewed' THEN
  IF r.starts_at<now() OR NOT EXISTS(SELECT 1 FROM worthkind_flow.event_venues WHERE id=r.venue_id AND active AND capacity>=r.attendance) OR EXISTS(
 SELECT 1 FROM worthkind_flow.venue_requests x WHERE x.property_id=a.property_id AND x.venue_id=r.venue_id AND x.state='accepted'
 AND x.starts_at<r.ends_at AND x.ends_at>r.starts_at AND x.id<>r.id) THEN RAISE EXCEPTION 'Venue conflict' USING ERRCODE='23514'; END IF;
 v_state='accepted';
 ELSIF p_action='decline' AND r.state IN ('requested','reviewed') THEN v_state='declined';
 ELSIF p_action='cancel' AND r.state='accepted' THEN v_state='cancelled';
 ELSE RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.venue_requests SET state=v_state WHERE id=r.id;
 INSERT INTO worthkind_flow.department_events(property_id,actor,resource_id,domain,action) VALUES(a.property_id,a.member_id,r.id,'events',p_action);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.events_queue(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','events') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,case_id,venue_id,starts_at,ends_at,attendance,state FROM worthkind_flow.venue_requests WHERE property_id=a.property_id ORDER BY starts_at LIMIT 200)x),'[]'::jsonb);
END $$;
CREATE FUNCTION worthkind_flow.create_vacancy(p_subject text,p_slug text,p_title text,p_description text,p_deadline date)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','hr') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_deadline<current_date THEN RAISE EXCEPTION 'Past deadline' USING ERRCODE='22023'; END IF;
 INSERT INTO worthkind_flow.vacancies(property_id,title,description,deadline) VALUES(a.property_id,p_title,p_description,p_deadline) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.department_events(property_id,actor,resource_id,domain,action) VALUES(a.property_id,a.member_id,v_id,'recruitment','vacancy_created');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.decide_vacancy(p_subject text,p_slug text,p_vacancy uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','hr') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 UPDATE worthkind_flow.vacancies v SET state=CASE p_action WHEN 'publish' THEN 'published' WHEN 'close' THEN 'closed' END
 WHERE v.id=p_vacancy AND v.property_id=a.property_id AND ((p_action='publish' AND v.state='draft' AND v.deadline>=current_date) OR (p_action='close' AND v.state IN ('draft','published')))
 RETURNING state INTO v_state;
 IF NOT FOUND THEN RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.department_events(property_id,actor,resource_id,domain,action) VALUES(a.property_id,a.member_id,p_vacancy,'recruitment',p_action);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.public_vacancies(p_slug text)
RETURNS TABLE(id uuid,title text,description text,deadline date)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT v.id,v.title,v.description,v.deadline FROM worthkind_flow.vacancies v JOIN worthkind_flow.properties p ON p.id=v.property_id
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' AND v.state='published' AND v.deadline>=current_date ORDER BY v.deadline,v.id
$$;
CREATE FUNCTION worthkind_flow.submit_application(p_slug text,p_case uuid,p_hash text,p_vacancy uuid,p_cipher bytea)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_id uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=v_property AND kind='careers')
 OR NOT EXISTS(SELECT 1 FROM worthkind_flow.vacancies WHERE id=p_vacancy AND property_id=v_property AND state='published' AND deadline>=current_date) THEN RAISE EXCEPTION 'Application unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.job_applications(property_id,vacancy_id,case_id,encrypted_application) VALUES(v_property,p_vacancy,p_case,p_cipher) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.department_events(property_id,resource_id,domain,action) VALUES(v_property,v_id,'recruitment','application_submitted');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.review_application(p_subject text,p_slug text,p_application uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','hr') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 UPDATE worthkind_flow.job_applications j SET state=CASE p_action WHEN 'review' THEN 'reviewing' WHEN 'shortlist' THEN 'shortlisted' WHEN 'reject' THEN 'rejected' WHEN 'select' THEN 'selected' END
 WHERE j.id=p_application AND j.property_id=a.property_id AND (
 (p_action='review' AND j.state='submitted') OR (p_action='shortlist' AND j.state='reviewing') OR
 (p_action='reject' AND j.state IN ('submitted','reviewing','shortlisted')) OR (p_action='select' AND j.state='shortlisted' AND a.member_role IN ('owner','manager')))
 RETURNING state INTO v_state;
 IF NOT FOUND THEN RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.department_events(property_id,actor,resource_id,domain,action) VALUES(a.property_id,a.member_id,p_application,'recruitment',p_action);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.recruitment_queue(p_subject text,p_slug text)
RETURNS TABLE(id uuid,vacancy_id uuid,case_id uuid,state text,encrypted_application bytea,created_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','hr') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT j.id,j.vacancy_id,j.case_id,j.state,j.encrypted_application,j.created_at
 FROM worthkind_flow.job_applications j WHERE j.property_id=a.property_id ORDER BY j.created_at DESC,j.id LIMIT 200;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.create_venue(text,text,text,integer),worthkind_flow.public_venues(text),
 worthkind_flow.request_venue(text,uuid,text,uuid,timestamptz,timestamptz,integer,text),worthkind_flow.decide_venue(text,text,uuid,text),worthkind_flow.events_queue(text,text),
 worthkind_flow.create_vacancy(text,text,text,text,date),worthkind_flow.decide_vacancy(text,text,uuid,text),worthkind_flow.public_vacancies(text),
 worthkind_flow.submit_application(text,uuid,text,uuid,bytea),worthkind_flow.review_application(text,text,uuid,text),worthkind_flow.recruitment_queue(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.create_venue(text,text,text,integer),worthkind_flow.decide_venue(text,text,uuid,text),worthkind_flow.events_queue(text,text),
 worthkind_flow.create_vacancy(text,text,text,text,date),worthkind_flow.decide_vacancy(text,text,uuid,text),worthkind_flow.review_application(text,text,uuid,text),worthkind_flow.recruitment_queue(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.public_venues(text),worthkind_flow.public_vacancies(text) TO wf_public_content;
GRANT EXECUTE ON FUNCTION worthkind_flow.request_venue(text,uuid,text,uuid,timestamptz,timestamptz,integer,text),worthkind_flow.submit_application(text,uuid,text,uuid,bytea) TO wf_guest_api;
COMMIT;
