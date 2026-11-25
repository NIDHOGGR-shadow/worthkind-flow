BEGIN;
CREATE ROLE wf_ai_gateway NOLOGIN;
CREATE ROLE wf_ai_policy NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_ai_gateway,wf_ai_policy;
CREATE TABLE worthkind_flow.ai_policies(
 property_id uuid PRIMARY KEY REFERENCES worthkind_flow.properties(id),
 provider_approved boolean NOT NULL DEFAULT false,
 approval_reference text,
 guest_chat boolean NOT NULL DEFAULT false,
 staff_assist boolean NOT NULL DEFAULT false,
 autonomous_alerts boolean NOT NULL DEFAULT false,
 voice_enabled boolean NOT NULL DEFAULT false,
 max_calls_per_day integer NOT NULL DEFAULT 50 CHECK(max_calls_per_day BETWEEN 1 AND 1000),
 revision bigint NOT NULL DEFAULT 1,
 CHECK(provider_approved OR NOT(guest_chat OR staff_assist OR voice_enabled)),
 CHECK(NOT voice_enabled OR guest_chat)
);
CREATE TABLE worthkind_flow.ai_policy_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor uuid, action text NOT NULL,revision bigint NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.ai_calls(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor uuid,channel text NOT NULL CHECK(channel IN ('guest_chat','staff_assist','voice')),
 policy_revision bigint NOT NULL,state text NOT NULL DEFAULT 'reserved' CHECK(state IN ('reserved','answered','abstained','failed','revoked')),
 source_ids uuid[] NOT NULL DEFAULT '{}',created_at timestamptz NOT NULL DEFAULT now(),finished_at timestamptz,
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE INDEX wf_ai_usage ON worthkind_flow.ai_calls(property_id,created_at);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['ai_policies','ai_policy_events','ai_calls'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
ALTER TABLE worthkind_flow.property_settings DROP CONSTRAINT property_settings_ai_enabled_check;
CREATE FUNCTION worthkind_flow.approve_ai_provider(p_slug text,p_approved boolean,p_evidence text)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE prop uuid; rev bigint;
BEGIN
 IF p_approved IS NULL OR length(btrim(coalesce(p_evidence,''))) NOT BETWEEN 8 AND 240 THEN RAISE EXCEPTION 'Approval reference required' USING ERRCODE='22023'; END IF;
 SELECT p.id INTO prop FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'Property unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.ai_policies(property_id,provider_approved,approval_reference) VALUES(prop,p_approved,p_evidence)
 ON CONFLICT(property_id) DO UPDATE SET provider_approved=EXCLUDED.provider_approved,approval_reference=EXCLUDED.approval_reference,
 guest_chat=false,staff_assist=false,voice_enabled=false,revision=worthkind_flow.ai_policies.revision+1 RETURNING revision INTO rev;
 UPDATE worthkind_flow.property_settings SET ai_enabled=false,revision=revision+1,updated_at=now() WHERE property_id=prop;
 INSERT INTO worthkind_flow.ai_policy_events(property_id,action,revision) VALUES(prop,CASE WHEN p_approved THEN 'provider_approved' ELSE 'provider_revoked' END,rev);
 RETURN rev;
END $$;
CREATE FUNCTION worthkind_flow.manage_ai_policy(p_subject text,p_slug text,p_revision bigint,p_chat boolean,p_staff boolean,p_auto boolean,p_voice boolean,p_cap integer)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; cfg worthkind_flow.ai_policies%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role<>'owner' THEN RAISE EXCEPTION 'Owner required' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 INSERT INTO worthkind_flow.ai_policies(property_id) VALUES(a.property_id) ON CONFLICT DO NOTHING;
 SELECT * INTO cfg FROM worthkind_flow.ai_policies WHERE property_id=a.property_id FOR UPDATE;
 IF p_revision IS NOT NULL THEN
 IF cfg.revision<>p_revision THEN RAISE EXCEPTION 'Policy revision conflict' USING ERRCODE='40001'; END IF;
 IF p_chat IS NULL OR p_staff IS NULL OR p_auto IS NULL OR p_voice IS NULL OR p_cap IS NULL THEN RAISE EXCEPTION 'Complete policy required' USING ERRCODE='22023'; END IF;
 UPDATE worthkind_flow.ai_policies SET guest_chat=p_chat,staff_assist=p_staff,autonomous_alerts=p_auto,voice_enabled=p_voice,max_calls_per_day=p_cap,revision=revision+1
 WHERE property_id=a.property_id RETURNING * INTO cfg;
 UPDATE worthkind_flow.property_settings SET ai_enabled=(cfg.guest_chat OR cfg.staff_assist OR cfg.voice_enabled),revision=revision+1,updated_at=now() WHERE property_id=a.property_id;
 INSERT INTO worthkind_flow.ai_policy_events(property_id,actor,action,revision) VALUES(a.property_id,a.member_id,'policy_changed',cfg.revision);
 END IF;
 RETURN to_jsonb(cfg)-'property_id'-'approval_reference';
END $$;
CREATE FUNCTION worthkind_flow.begin_ai_call(p_slug text,p_subject text,p_channel text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE prop uuid; member uuid; cfg worthkind_flow.ai_policies%ROWTYPE; v_id uuid;
BEGIN
 SELECT p.id INTO prop FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'AI unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO cfg FROM worthkind_flow.ai_policies WHERE property_id=prop;
 IF NOT FOUND OR NOT cfg.provider_approved OR NOT CASE p_channel WHEN 'guest_chat' THEN cfg.guest_chat WHEN 'voice' THEN cfg.voice_enabled WHEN 'staff_assist' THEN cfg.staff_assist ELSE false END THEN RAISE EXCEPTION 'AI unavailable' USING ERRCODE='P0002'; END IF;
 IF p_channel='staff_assist' THEN
 SELECT member_id INTO member FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 ELSIF p_subject IS NOT NULL THEN RAISE EXCEPTION 'Unexpected staff identity' USING ERRCODE='22023'; END IF;
 IF (SELECT count(*) FROM worthkind_flow.ai_calls WHERE property_id=prop AND created_at>=now()-interval '24 hours')>=cfg.max_calls_per_day THEN
 RAISE EXCEPTION 'AI quota exhausted' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.ai_calls(property_id,actor,channel,policy_revision) VALUES(prop,member,p_channel,cfg.revision) RETURNING id INTO v_id;
 RETURN v_id;
END $$;
-- Public approved content only. No guest records, financial data, personnel records or tools.
CREATE FUNCTION worthkind_flow.ai_retrieve(p_slug text,p_call uuid,p_query text)
RETURNS TABLE(id uuid,content_key text,version integer,title text,body text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 WITH q AS (SELECT websearch_to_tsquery('simple',left(p_query,800)) AS terms)
 SELECT c.id,c.content_key,c.version,c.content->>'title',c.content->>'body'
 FROM worthkind_flow.ai_calls ac JOIN worthkind_flow.properties p ON p.id=ac.property_id
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 JOIN worthkind_flow.ai_policies ap ON ap.property_id=p.id AND ap.revision=ac.policy_revision AND ap.provider_approved
 JOIN worthkind_flow.content_versions c ON c.property_id=p.id CROSS JOIN q
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' AND ac.id=p_call AND ac.state='reserved'
 AND ac.created_at>now()-interval '5 minutes' AND c.state='published'
 AND c.content_key NOT IN ('payment','bank-details','credentials')
 AND to_tsvector('simple',coalesce(c.content->>'title','')||' '||coalesce(c.content->>'body','')) @@ q.terms
 ORDER BY ts_rank(to_tsvector('simple',coalesce(c.content->>'title','')||' '||coalesce(c.content->>'body','')),q.terms) DESC,c.id LIMIT 5
$$;
CREATE FUNCTION worthkind_flow.finish_ai_call(p_slug text,p_call uuid,p_state text,p_ids uuid[])
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE prop uuid; c worthkind_flow.ai_calls%ROWTYPE; cfg worthkind_flow.ai_policies%ROWTYPE; allowed boolean;
BEGIN
 SELECT p.id INTO prop FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO c FROM worthkind_flow.ai_calls WHERE id=p_call AND property_id=prop AND state='reserved' FOR UPDATE;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO cfg FROM worthkind_flow.ai_policies WHERE property_id=prop;
 allowed:=coalesce(cfg.provider_approved AND cfg.revision=c.policy_revision AND c.created_at>now()-interval '5 minutes',false);
 IF c.actor IS NOT NULL AND NOT EXISTS(SELECT 1 FROM worthkind_flow.staff_memberships m JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id WHERE m.id=c.actor AND m.property_id=prop AND m.state='active' AND i.state='active') THEN allowed:=false; END IF;
 IF p_state NOT IN ('answered','abstained','failed') OR p_ids IS NULL OR cardinality(p_ids)>5 THEN RAISE EXCEPTION 'Invalid AI result' USING ERRCODE='22023'; END IF;
 IF p_state='answered' AND (cardinality(p_ids)=0 OR EXISTS(SELECT 1 FROM unnest(p_ids) x(id) WHERE NOT EXISTS(SELECT 1 FROM worthkind_flow.content_versions v WHERE v.id=x.id AND v.property_id=prop AND v.state='published'))) THEN allowed:=false; END IF;
 UPDATE worthkind_flow.ai_calls SET state=CASE WHEN allowed THEN p_state ELSE 'revoked' END,source_ids=CASE WHEN allowed AND p_state='answered' THEN p_ids ELSE '{}'::uuid[] END,finished_at=now() WHERE id=c.id;
 RETURN allowed;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.approve_ai_provider(text,boolean,text),worthkind_flow.manage_ai_policy(text,text,bigint,boolean,boolean,boolean,boolean,integer),worthkind_flow.begin_ai_call(text,text,text),worthkind_flow.ai_retrieve(text,uuid,text),worthkind_flow.finish_ai_call(text,uuid,text,uuid[]) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.approve_ai_provider(text,boolean,text) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.manage_ai_policy(text,text,bigint,boolean,boolean,boolean,boolean,integer) TO wf_ai_policy;
GRANT EXECUTE ON FUNCTION worthkind_flow.begin_ai_call(text,text,text),worthkind_flow.ai_retrieve(text,uuid,text),worthkind_flow.finish_ai_call(text,uuid,text,uuid[]) TO wf_ai_gateway;
COMMIT;
