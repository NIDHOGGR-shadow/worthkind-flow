BEGIN;
CREATE ROLE wf_platform_crm NOLOGIN;
CREATE ROLE wf_platform_crm_admin NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_platform_crm,wf_platform_crm_admin;
CREATE TABLE worthkind_flow.crm_operators(
 provider_subject text PRIMARY KEY CHECK(length(provider_subject) BETWEEN 8 AND 255),
 active boolean NOT NULL DEFAULT false,updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE worthkind_flow.crm_operator_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),provider_subject text NOT NULL REFERENCES worthkind_flow.crm_operators(provider_subject),
 active boolean NOT NULL,evidence_reference text NOT NULL CHECK(length(btrim(evidence_reference)) BETWEEN 8 AND 240),
 created_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE worthkind_flow.crm_prospects(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),account_key text NOT NULL UNIQUE CHECK(account_key ~ '^[a-z0-9][a-z0-9_-]{2,99}$'),
 hotel_name text NOT NULL CHECK(length(btrim(hotel_name)) BETWEEN 2 AND 200),
 source_reference text NOT NULL CHECK(length(btrim(source_reference)) BETWEEN 3 AND 240),
 encrypted_contact bytea CHECK(octet_length(encrypted_contact) BETWEEN 29 AND 12000),
 payload_hash text NOT NULL CHECK(payload_hash ~ '^[a-f0-9]{64}$'),
 stage text NOT NULL DEFAULT 'prospect' CHECK(stage IN ('prospect','discovery','consented_waitlist','written_pilot_interest','closed')),
 outreach_allowed boolean NOT NULL DEFAULT false,revision bigint NOT NULL DEFAULT 1,
 created_by text NOT NULL REFERENCES worthkind_flow.crm_operators(provider_subject),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE TABLE worthkind_flow.crm_prospect_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),prospect_id uuid NOT NULL REFERENCES worthkind_flow.crm_prospects(id),
 actor text NOT NULL REFERENCES worthkind_flow.crm_operators(provider_subject),request_key uuid NOT NULL,
 action text NOT NULL CHECK(action IN ('stage','consent')),
 value text NOT NULL,evidence_reference text NOT NULL CHECK(length(btrim(evidence_reference)) BETWEEN 8 AND 240),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(prospect_id,request_key)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['crm_operators','crm_operator_events','crm_prospects','crm_prospect_events'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
CREATE FUNCTION worthkind_flow.set_crm_operator(p_subject text,p_active boolean,p_evidence text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF p_subject IS NULL OR p_active IS NULL OR p_evidence IS NULL THEN RAISE EXCEPTION 'Invalid operator change' USING ERRCODE='22023'; END IF;
 INSERT INTO worthkind_flow.crm_operators(provider_subject,active) VALUES(p_subject,p_active)
 ON CONFLICT(provider_subject) DO UPDATE SET active=EXCLUDED.active,updated_at=now();
 INSERT INTO worthkind_flow.crm_operator_events(provider_subject,active,evidence_reference) VALUES(p_subject,p_active,p_evidence);
END $$;
CREATE FUNCTION worthkind_flow.require_crm_operator(p_subject text)
RETURNS void LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.crm_operators WHERE provider_subject=p_subject AND active) THEN RAISE EXCEPTION 'CRM access denied' USING ERRCODE='42501'; END IF;
END $$;
CREATE FUNCTION worthkind_flow.create_crm_prospect(p_subject text,p_key text,p_name text,p_source text,p_contact bytea,p_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE q worthkind_flow.crm_prospects%ROWTYPE; v_duplicate boolean:=false;
BEGIN
 PERFORM worthkind_flow.require_crm_operator(p_subject);
 INSERT INTO worthkind_flow.crm_prospects(account_key,hotel_name,source_reference,encrypted_contact,payload_hash,created_by)
 VALUES(p_key,p_name,p_source,p_contact,p_hash,p_subject) ON CONFLICT(account_key) DO NOTHING RETURNING * INTO q;
 IF NOT FOUND THEN
 SELECT * INTO q FROM worthkind_flow.crm_prospects WHERE account_key=p_key;
 IF q.payload_hash IS DISTINCT FROM p_hash THEN RAISE EXCEPTION 'Prospect already exists' USING ERRCODE='23505'; END IF;
 v_duplicate:=true;
 END IF;
 RETURN jsonb_build_object('id',q.id,'stage',q.stage,'revision',q.revision,'duplicate',v_duplicate);
END $$;
CREATE FUNCTION worthkind_flow.change_crm_prospect(p_subject text,p_id uuid,p_key uuid,p_revision bigint,p_action text,p_value text,p_evidence text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE q worthkind_flow.crm_prospects%ROWTYPE; e worthkind_flow.crm_prospect_events%ROWTYPE;
BEGIN
 PERFORM worthkind_flow.require_crm_operator(p_subject);
 IF p_key IS NULL OR p_revision IS NULL OR p_action IS NULL OR p_action NOT IN ('stage','consent') OR p_value IS NULL OR p_evidence IS NULL THEN RAISE EXCEPTION 'Invalid change' USING ERRCODE='22023'; END IF;
 SELECT * INTO q FROM worthkind_flow.crm_prospects WHERE id=p_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Prospect unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO e FROM worthkind_flow.crm_prospect_events WHERE prospect_id=p_id AND request_key=p_key;
 IF FOUND THEN
 IF e.actor<>p_subject OR e.action<>p_action OR e.value<>p_value OR e.evidence_reference<>p_evidence THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN jsonb_build_object('id',q.id,'stage',q.stage,'outreach_allowed',q.outreach_allowed,'revision',q.revision,'duplicate',true);
 END IF;
 IF q.revision<>p_revision THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
 IF p_action='consent' THEN
 IF p_value NOT IN ('granted','revoked') OR (p_value='granted' AND (q.stage='closed' OR q.encrypted_contact IS NULL)) THEN RAISE EXCEPTION 'Invalid consent change' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.crm_prospects SET outreach_allowed=(p_value='granted'),revision=revision+1,updated_at=now() WHERE id=p_id RETURNING * INTO q;
 ELSE
 IF NOT ((q.stage='prospect' AND p_value='discovery') OR (q.stage='discovery' AND p_value='consented_waitlist' AND q.outreach_allowed) OR
 (q.stage='consented_waitlist' AND p_value='written_pilot_interest' AND q.outreach_allowed) OR (q.stage<>'closed' AND p_value='closed')) THEN RAISE EXCEPTION 'Invalid stage transition' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.crm_prospects SET stage=p_value,outreach_allowed=CASE WHEN p_value='closed' THEN false ELSE outreach_allowed END,revision=revision+1,updated_at=now() WHERE id=p_id RETURNING * INTO q;
 END IF;
 INSERT INTO worthkind_flow.crm_prospect_events(prospect_id,actor,request_key,action,value,evidence_reference) VALUES(p_id,p_subject,p_key,p_action,p_value,p_evidence);
 RETURN jsonb_build_object('id',q.id,'stage',q.stage,'outreach_allowed',q.outreach_allowed,'revision',q.revision,'duplicate',false);
END $$;
CREATE FUNCTION worthkind_flow.list_crm_prospects(p_subject text,p_after uuid,p_limit integer)
RETURNS TABLE(id uuid,account_key text,hotel_name text,source_reference text,encrypted_contact bytea,stage text,outreach_allowed boolean,revision bigint,created_at timestamptz)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 PERFORM worthkind_flow.require_crm_operator(p_subject);
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT q.id,q.account_key,q.hotel_name,q.source_reference,q.encrypted_contact,q.stage,q.outreach_allowed,q.revision,q.created_at
 FROM worthkind_flow.crm_prospects q WHERE p_after IS NULL OR q.id>p_after ORDER BY q.id LIMIT p_limit;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.set_crm_operator(text,boolean,text),worthkind_flow.require_crm_operator(text),worthkind_flow.create_crm_prospect(text,text,text,text,bytea,text),worthkind_flow.change_crm_prospect(text,uuid,uuid,bigint,text,text,text),worthkind_flow.list_crm_prospects(text,uuid,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.set_crm_operator(text,boolean,text) TO wf_platform_crm_admin;
GRANT EXECUTE ON FUNCTION worthkind_flow.create_crm_prospect(text,text,text,text,bytea,text),worthkind_flow.change_crm_prospect(text,uuid,uuid,bigint,text,text,text),worthkind_flow.list_crm_prospects(text,uuid,integer) TO wf_platform_crm;
COMMIT;
