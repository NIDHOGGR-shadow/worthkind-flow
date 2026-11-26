-- Operator-approved hotel onboarding and scoped configuration.
BEGIN;
CREATE ROLE wf_hotel_provisioner NOLOGIN;
CREATE ROLE wf_property_config NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_hotel_provisioner,wf_property_config;
CREATE TABLE worthkind_flow.property_settings (
 property_id uuid PRIMARY KEY REFERENCES worthkind_flow.properties(id),
 guest_enquiries_enabled boolean NOT NULL DEFAULT true,
 ai_enabled boolean NOT NULL DEFAULT false CHECK (NOT ai_enabled),
 revision bigint NOT NULL DEFAULT 1,
 updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE worthkind_flow.property_admin_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor_reference text NOT NULL,
 action text NOT NULL CHECK(action IN ('registered','activated','settings_changed')),
 evidence_reference text,
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE worthkind_flow.property_settings ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.property_settings FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.property_admin_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.property_admin_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.property_settings,worthkind_flow.property_admin_events FROM PUBLIC;

CREATE FUNCTION worthkind_flow.register_hotel(p_legal_name text,p_slug text,p_display_name text,p_timezone text,p_operator text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_org uuid; v_property uuid;
BEGIN
 IF p_operator IS NULL OR length(btrim(p_operator)) NOT BETWEEN 3 AND 255
 OR NOT EXISTS(SELECT 1 FROM pg_timezone_names WHERE name=p_timezone) THEN
   RAISE EXCEPTION 'Invalid registration' USING ERRCODE='22023';
 END IF;
 INSERT INTO worthkind_flow.organizations(legal_name) VALUES(p_legal_name) RETURNING id INTO v_org;
 INSERT INTO worthkind_flow.properties(organization_id,slug,display_name,time_zone)
 VALUES(v_org,p_slug,p_display_name,p_timezone) RETURNING id INTO v_property;
 INSERT INTO worthkind_flow.property_settings(property_id) VALUES(v_property);
 INSERT INTO worthkind_flow.property_admin_events(property_id,actor_reference,action)
 VALUES(v_property,p_operator,'registered');
 RETURN v_property;
END $$;

CREATE FUNCTION worthkind_flow.activate_hotel(p_slug text,p_owner_subject text,p_operator text,p_evidence text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_org uuid; v_identity uuid;
BEGIN
 IF p_operator IS NULL OR length(btrim(p_operator)) NOT BETWEEN 3 AND 255 OR
 p_evidence IS NULL OR length(btrim(p_evidence)) NOT BETWEEN 8 AND 255 THEN
   RAISE EXCEPTION 'Operator approval reference required' USING ERRCODE='22023';
 END IF;
 SELECT id,organization_id INTO v_property,v_org FROM worthkind_flow.properties
 WHERE slug=p_slug AND status='pending' FOR UPDATE;
 IF v_property IS NULL THEN RAISE EXCEPTION 'Hotel unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.staff_identities(provider_subject) VALUES(p_owner_subject)
 ON CONFLICT(provider_subject) DO NOTHING;
 SELECT id INTO v_identity FROM worthkind_flow.staff_identities
 WHERE provider_subject=p_owner_subject AND state='active';
 IF v_identity IS NULL THEN RAISE EXCEPTION 'Owner unavailable' USING ERRCODE='42501'; END IF;
 INSERT INTO worthkind_flow.staff_memberships(organization_id,property_id,identity_id,role,state,activated_at)
 VALUES(v_org,v_property,v_identity,'owner','active',now());
 UPDATE worthkind_flow.organizations SET status='verified' WHERE id=v_org AND status='pending';
 IF NOT FOUND THEN RAISE EXCEPTION 'Organization unavailable' USING ERRCODE='P0002'; END IF;
 UPDATE worthkind_flow.properties SET status='active' WHERE id=v_property;
 INSERT INTO worthkind_flow.property_admin_events(property_id,actor_reference,action,evidence_reference)
 VALUES(v_property,p_operator,'activated',p_evidence);
 RETURN v_property;
END $$;

CREATE FUNCTION worthkind_flow.manage_property_settings(p_actor text,p_slug text,p_expected_revision bigint,p_guest_enabled boolean)
RETURNS TABLE(guest_enquiries_enabled boolean,ai_enabled boolean,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_role text;
BEGIN
 SELECT s.property_id,s.membership_role INTO v_property,v_role
 FROM worthkind_flow.resolve_staff_session(p_actor,p_slug,'case:read') s;
 IF v_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_expected_revision IS NOT NULL THEN
   IF p_guest_enabled IS NULL THEN RAISE EXCEPTION 'Setting required' USING ERRCODE='22023'; END IF;
   UPDATE worthkind_flow.property_settings ps SET guest_enquiries_enabled=p_guest_enabled,
     revision=ps.revision+1,updated_at=now()
   WHERE ps.property_id=v_property AND ps.revision=p_expected_revision;
   IF NOT FOUND THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
   INSERT INTO worthkind_flow.property_admin_events(property_id,actor_reference,action)
   VALUES(v_property,p_actor,'settings_changed');
 END IF;
 RETURN QUERY SELECT ps.guest_enquiries_enabled,ps.ai_enabled,ps.revision
 FROM worthkind_flow.property_settings ps WHERE ps.property_id=v_property;
END $$;

-- Enforce guest intake control at the database boundary, including direct command calls.
CREATE FUNCTION worthkind_flow.check_guest_intake() RETURNS trigger
LANGUAGE plpgsql SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF EXISTS(SELECT 1 FROM worthkind_flow.property_settings ps WHERE ps.property_id=NEW.property_id AND NOT ps.guest_enquiries_enabled) THEN
   RAISE EXCEPTION 'Guest intake paused' USING ERRCODE='P0002';
 END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_guest_intake_guard BEFORE INSERT ON worthkind_flow.guest_cases
FOR EACH ROW EXECUTE FUNCTION worthkind_flow.check_guest_intake();
REVOKE ALL ON FUNCTION worthkind_flow.register_hotel(text,text,text,text,text),
 worthkind_flow.activate_hotel(text,text,text,text),
 worthkind_flow.manage_property_settings(text,text,bigint,boolean),
 worthkind_flow.check_guest_intake() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.register_hotel(text,text,text,text,text),
 worthkind_flow.activate_hotel(text,text,text,text) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.manage_property_settings(text,text,bigint,boolean) TO wf_property_config;
COMMIT;
