BEGIN;
CREATE TABLE worthkind_flow.guest_preferences(
 case_id uuid PRIMARY KEY,property_id uuid NOT NULL,encrypted_preferences bytea NOT NULL CHECK(octet_length(encrypted_preferences) BETWEEN 29 AND 16000),
 revision bigint NOT NULL DEFAULT 1,updated_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id)
);
CREATE TABLE worthkind_flow.guest_consent_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,case_id uuid NOT NULL,
 purpose text NOT NULL CHECK(purpose IN ('service_followup','marketing')),granted boolean NOT NULL,
 policy_version text NOT NULL CHECK(length(btrim(policy_version)) BETWEEN 1 AND 80),created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id)
);
CREATE INDEX wf_consent_history ON worthkind_flow.guest_consent_events(property_id,case_id,purpose,created_at DESC,id);
CREATE TABLE worthkind_flow.guest_feedback(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,case_id uuid NOT NULL UNIQUE,
 rating integer NOT NULL CHECK(rating BETWEEN 1 AND 5),encrypted_comment bytea NOT NULL CHECK(octet_length(encrypted_comment) BETWEEN 29 AND 16000),
 state text NOT NULL DEFAULT 'new' CHECK(state IN ('new','reviewed','resolved')),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(id,property_id),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id)
);
CREATE TABLE worthkind_flow.feedback_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,feedback_id uuid NOT NULL,actor uuid NOT NULL,
 action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(feedback_id,property_id) REFERENCES worthkind_flow.guest_feedback(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.guest_preferences ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_preferences FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_consent_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_consent_events FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_feedback ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_feedback FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.feedback_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.feedback_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.guest_preferences,worthkind_flow.guest_consent_events,worthkind_flow.guest_feedback,worthkind_flow.feedback_events FROM PUBLIC;

CREATE FUNCTION worthkind_flow.verified_guest_case(p_slug text,p_case uuid,p_hash text)
RETURNS uuid LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 SELECT c.property_id INTO v_property FROM worthkind_flow.guest_cases c
 JOIN worthkind_flow.properties p ON p.id=c.property_id JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE c.id=p_case AND c.receipt_hash=p_hash AND p.slug=p_slug AND p.status='active' AND o.status='verified';
 IF NOT FOUND THEN RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 RETURN v_property;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.verified_guest_case(text,uuid,text) FROM PUBLIC;
CREATE FUNCTION worthkind_flow.save_guest_preferences(p_slug text,p_case uuid,p_hash text,p_cipher bytea,p_revision bigint)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_revision bigint;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 IF p_revision=0 THEN
 INSERT INTO worthkind_flow.guest_preferences(case_id,property_id,encrypted_preferences) VALUES(p_case,v_property,p_cipher) RETURNING revision INTO v_revision;
 ELSE
 UPDATE worthkind_flow.guest_preferences SET encrypted_preferences=p_cipher,revision=revision+1,updated_at=now()
 WHERE case_id=p_case AND property_id=v_property AND revision=p_revision RETURNING revision INTO v_revision;
 IF NOT FOUND THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
 END IF;
 RETURN v_revision;
END $$;
CREATE FUNCTION worthkind_flow.record_guest_consent(p_slug text,p_case uuid,p_hash text,p_purpose text,p_granted boolean,p_policy text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_id uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 INSERT INTO worthkind_flow.guest_consent_events(property_id,case_id,purpose,granted,policy_version)
 VALUES(v_property,p_case,p_purpose,p_granted,p_policy) RETURNING id INTO v_id;
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.read_guest_preferences(p_slug text,p_case uuid,p_hash text)
RETURNS TABLE(encrypted_preferences bytea,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 RETURN QUERY SELECT g.encrypted_preferences,g.revision FROM worthkind_flow.guest_preferences g WHERE g.case_id=p_case AND g.property_id=v_property;
END $$;
CREATE FUNCTION worthkind_flow.submit_feedback(p_slug text,p_case uuid,p_hash text,p_rating integer,p_cipher bytea)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_id uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=v_property AND state IN ('responded','resolved')) THEN
 RAISE EXCEPTION 'Case not eligible' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.guest_feedback(property_id,case_id,rating,encrypted_comment) VALUES(v_property,p_case,p_rating,p_cipher) RETURNING id INTO v_id;
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.list_feedback(p_subject text,p_slug text)
RETURNS TABLE(id uuid,case_id uuid,rating integer,state text,encrypted_comment bytea,created_at timestamptz)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT f.id,f.case_id,f.rating,f.state,f.encrypted_comment,f.created_at
 FROM worthkind_flow.guest_feedback f WHERE f.property_id=a.property_id ORDER BY f.created_at DESC,f.id LIMIT 200;
END $$;
CREATE FUNCTION worthkind_flow.review_feedback(p_subject text,p_slug text,p_id uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 UPDATE worthkind_flow.guest_feedback f SET state=CASE p_action WHEN 'review' THEN 'reviewed' WHEN 'resolve' THEN 'resolved' END
 WHERE f.id=p_id AND f.property_id=a.property_id AND ((p_action='review' AND f.state='new') OR (p_action='resolve' AND f.state='reviewed'))
 RETURNING state INTO v_state;
 IF NOT FOUND THEN RAISE EXCEPTION 'Feedback unavailable or state conflict' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.feedback_events(property_id,feedback_id,actor,action) VALUES(a.property_id,p_id,a.member_id,p_action);
 RETURN v_state;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.save_guest_preferences(text,uuid,text,bytea,bigint),worthkind_flow.record_guest_consent(text,uuid,text,text,boolean,text),
 worthkind_flow.read_guest_preferences(text,uuid,text),worthkind_flow.submit_feedback(text,uuid,text,integer,bytea),
 worthkind_flow.list_feedback(text,text),worthkind_flow.review_feedback(text,text,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.save_guest_preferences(text,uuid,text,bytea,bigint),worthkind_flow.record_guest_consent(text,uuid,text,text,boolean,text),
 worthkind_flow.read_guest_preferences(text,uuid,text),worthkind_flow.submit_feedback(text,uuid,text,integer,bytea) TO wf_guest_api;
GRANT EXECUTE ON FUNCTION worthkind_flow.list_feedback(text,text),worthkind_flow.review_feedback(text,text,uuid,text) TO wf_operations;
COMMIT;
