BEGIN;
-- A platform-wide weighted ceiling is independent of the hotel owner's limit.
CREATE TABLE worthkind_flow.ai_platform_limits(
 singleton boolean PRIMARY KEY DEFAULT true CHECK(singleton),
 enabled boolean NOT NULL DEFAULT false,
 max_daily_units integer NOT NULL DEFAULT 1000 CHECK(max_daily_units BETWEEN 1 AND 100000),
 updated_at timestamptz NOT NULL DEFAULT now()
);
INSERT INTO worthkind_flow.ai_platform_limits(singleton) VALUES(true);
ALTER TABLE worthkind_flow.ai_platform_limits ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.ai_platform_limits FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.ai_platform_limits FROM PUBLIC;
ALTER TABLE worthkind_flow.ai_calls ADD COLUMN usage_units integer NOT NULL DEFAULT 1 CHECK(usage_units BETWEEN 1 AND 3);
ALTER TABLE worthkind_flow.ai_calls ADD COLUMN retrieved_ids uuid[];
ALTER TABLE worthkind_flow.ai_policy_events ADD COLUMN content_id uuid;
ALTER TABLE worthkind_flow.ai_policy_events ADD FOREIGN KEY(content_id,property_id) REFERENCES worthkind_flow.content_versions(id,property_id);
CREATE FUNCTION worthkind_flow.configure_ai_platform(p_enabled boolean,p_units integer)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF p_enabled IS NULL OR p_units IS NULL OR p_units NOT BETWEEN 1 AND 100000 THEN RAISE EXCEPTION 'Invalid platform limit' USING ERRCODE='22023'; END IF;
 UPDATE worthkind_flow.ai_platform_limits SET enabled=p_enabled,max_daily_units=p_units,updated_at=now() WHERE singleton;
 -- Invalidate in-flight answers on any global policy change, even disable/re-enable.
 UPDATE worthkind_flow.ai_calls SET state='revoked',finished_at=now() WHERE state='reserved';
 RETURN p_enabled;
END $$;
CREATE OR REPLACE FUNCTION worthkind_flow.begin_ai_call(p_slug text,p_subject text,p_channel text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE prop uuid; member uuid; cfg worthkind_flow.ai_policies%ROWTYPE; lim worthkind_flow.ai_platform_limits%ROWTYPE; v_id uuid; units integer;
BEGIN
 SELECT * INTO lim FROM worthkind_flow.ai_platform_limits WHERE singleton FOR UPDATE;
 IF NOT FOUND OR NOT lim.enabled THEN RAISE EXCEPTION 'Platform AI unavailable' USING ERRCODE='P0002'; END IF;
 SELECT p.id INTO prop FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'AI unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO cfg FROM worthkind_flow.ai_policies WHERE property_id=prop;
 IF NOT FOUND OR NOT cfg.provider_approved OR NOT (CASE p_channel WHEN 'guest_chat' THEN cfg.guest_chat WHEN 'voice' THEN cfg.voice_enabled WHEN 'staff_assist' THEN cfg.staff_assist ELSE false END) THEN RAISE EXCEPTION 'AI unavailable' USING ERRCODE='P0002'; END IF;
 IF p_channel='staff_assist' THEN
 SELECT member_id INTO member FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 ELSIF p_subject IS NOT NULL THEN RAISE EXCEPTION 'Unexpected staff identity' USING ERRCODE='22023'; END IF;
 units:=CASE WHEN p_channel='voice' THEN 3 ELSE 1 END;
 IF COALESCE((SELECT sum(usage_units) FROM worthkind_flow.ai_calls WHERE created_at>=now()-interval '24 hours'),0)+units>lim.max_daily_units THEN RAISE EXCEPTION 'Platform AI quota exhausted' USING ERRCODE='23514'; END IF;
 IF COALESCE((SELECT sum(usage_units) FROM worthkind_flow.ai_calls WHERE property_id=prop AND created_at>=now()-interval '24 hours'),0)+units>cfg.max_calls_per_day THEN RAISE EXCEPTION 'AI quota exhausted' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.ai_calls(property_id,actor,channel,policy_revision,usage_units) VALUES(prop,member,p_channel,cfg.revision,units) RETURNING id INTO v_id;
 RETURN v_id;
END $$;
-- Each reservation may retrieve only one bounded set. The model cannot nominate a source
-- outside that set, even if it is another approved record from the same hotel.
CREATE OR REPLACE FUNCTION worthkind_flow.ai_retrieve(p_slug text,p_call uuid,p_query text)
RETURNS TABLE(id uuid,content_key text,version integer,title text,body text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE prop uuid; ccall worthkind_flow.ai_calls%ROWTYPE; selected uuid[];
BEGIN
 SELECT p.id INTO prop FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RETURN; END IF;
 SELECT * INTO ccall FROM worthkind_flow.ai_calls ac WHERE ac.id=p_call AND ac.property_id=prop AND ac.state='reserved' AND ac.retrieved_ids IS NULL AND ac.created_at>now()-interval '5 minutes' FOR UPDATE;
 IF NOT FOUND OR NOT EXISTS(SELECT 1 FROM worthkind_flow.ai_policies ap WHERE ap.property_id=prop AND ap.revision=ccall.policy_revision AND ap.provider_approved)
 OR NOT EXISTS(SELECT 1 FROM worthkind_flow.ai_platform_limits WHERE singleton AND enabled) THEN RETURN; END IF;
 IF ccall.actor IS NOT NULL AND NOT EXISTS(SELECT 1 FROM worthkind_flow.staff_memberships m JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id WHERE m.id=ccall.actor AND m.property_id=prop AND m.state='active' AND i.state='active') THEN RETURN; END IF;
 WITH q AS (SELECT websearch_to_tsquery('simple',left(p_query,800)) AS terms), ranked AS (
 SELECT v.id,ts_rank(to_tsvector('simple',coalesce(v.content->>'title','')||' '||coalesce(v.content->>'body','')),q.terms) AS score
 FROM worthkind_flow.content_versions v JOIN worthkind_flow.ai_source_permissions sp ON sp.property_id=v.property_id AND sp.content_id=v.id CROSS JOIN q
 WHERE v.property_id=prop AND v.state='published' AND v.content_key NOT IN ('payment','bank-details','credentials')
 AND to_tsvector('simple',coalesce(v.content->>'title','')||' '||coalesce(v.content->>'body','')) @@ q.terms ORDER BY score DESC,v.id LIMIT 5
 ) SELECT COALESCE(array_agg(r.id ORDER BY r.score DESC,r.id),'{}'::uuid[]) INTO selected FROM ranked r;
 UPDATE worthkind_flow.ai_calls ac SET retrieved_ids=selected WHERE ac.id=p_call AND ac.property_id=prop;
 RETURN QUERY SELECT v.id,v.content_key,v.version,v.content->>'title',v.content->>'body'
 FROM unnest(selected) WITH ORDINALITY chosen(cid,ord) JOIN worthkind_flow.content_versions v ON v.id=chosen.cid AND v.property_id=prop ORDER BY chosen.ord;
END $$;
CREATE OR REPLACE FUNCTION worthkind_flow.finish_ai_call(p_slug text,p_call uuid,p_state text,p_ids uuid[])
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE prop uuid; c worthkind_flow.ai_calls%ROWTYPE; cfg worthkind_flow.ai_policies%ROWTYPE; allowed boolean;
BEGIN
 SELECT p.id INTO prop FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO c FROM worthkind_flow.ai_calls WHERE id=p_call AND property_id=prop AND state='reserved' FOR UPDATE;
 IF NOT FOUND THEN RETURN false; END IF;
 SELECT * INTO cfg FROM worthkind_flow.ai_policies WHERE property_id=prop;
 allowed:=coalesce(cfg.provider_approved AND cfg.revision=c.policy_revision AND c.created_at>now()-interval '5 minutes',false)
 AND EXISTS(SELECT 1 FROM worthkind_flow.ai_platform_limits WHERE singleton AND enabled);
 IF c.actor IS NOT NULL AND NOT EXISTS(SELECT 1 FROM worthkind_flow.staff_memberships m JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id WHERE m.id=c.actor AND m.property_id=prop AND m.state='active' AND i.state='active') THEN allowed:=false; END IF;
 IF p_state IS NULL OR p_state NOT IN ('answered','abstained','failed') OR p_ids IS NULL OR cardinality(p_ids)>3 THEN RAISE EXCEPTION 'Invalid AI result' USING ERRCODE='22023'; END IF;
 IF p_state='answered' AND (cardinality(p_ids)=0 OR c.retrieved_ids IS NULL OR NOT(p_ids<@c.retrieved_ids) OR EXISTS(SELECT 1 FROM unnest(p_ids) x(id) WHERE NOT EXISTS(SELECT 1 FROM worthkind_flow.content_versions v WHERE v.id=x.id AND v.property_id=prop AND v.state='published' AND EXISTS(SELECT 1 FROM worthkind_flow.ai_source_permissions sp WHERE sp.property_id=prop AND sp.content_id=v.id)))) THEN allowed:=false; END IF;
 UPDATE worthkind_flow.ai_calls SET state=CASE WHEN allowed THEN p_state ELSE 'revoked' END,source_ids=CASE WHEN allowed AND p_state='answered' THEN p_ids ELSE '{}'::uuid[] END,finished_at=now() WHERE id=c.id;
 RETURN allowed;
END $$;
CREATE OR REPLACE FUNCTION worthkind_flow.manage_ai_source(p_subject text,p_slug text,p_content uuid,p_allow boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; rev bigint;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role<>'owner' THEN RAISE EXCEPTION 'Owner required' USING ERRCODE='42501'; END IF;
 IF p_allow IS NULL THEN RAISE EXCEPTION 'Decision required' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.content_versions WHERE id=p_content AND property_id=a.property_id AND (NOT p_allow OR state='published')) THEN RAISE EXCEPTION 'Source unavailable' USING ERRCODE='P0002'; END IF;
 IF p_allow THEN INSERT INTO worthkind_flow.ai_source_permissions(property_id,content_id,approved_by) VALUES(a.property_id,p_content,a.member_id) ON CONFLICT DO NOTHING;
 ELSE DELETE FROM worthkind_flow.ai_source_permissions WHERE property_id=a.property_id AND content_id=p_content; END IF;
 INSERT INTO worthkind_flow.ai_policies(property_id) VALUES(a.property_id) ON CONFLICT DO NOTHING;
 UPDATE worthkind_flow.ai_policies SET revision=revision+1 WHERE property_id=a.property_id RETURNING revision INTO rev;
 INSERT INTO worthkind_flow.ai_policy_events(property_id,actor,action,revision,content_id) VALUES(a.property_id,a.member_id,CASE WHEN p_allow THEN 'source_allowed' ELSE 'source_revoked' END,rev,p_content);
 RETURN p_allow;
END $$;
CREATE FUNCTION worthkind_flow.list_ai_sources(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role<>'owner' THEN RAISE EXCEPTION 'Owner required' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.content_key,x.version DESC) FROM (
 SELECT v.id,v.content_key,v.version,v.content->>'title' AS title,v.state,(sp.content_id IS NOT NULL AND v.state='published') AS ai_allowed
 FROM worthkind_flow.content_versions v LEFT JOIN worthkind_flow.ai_source_permissions sp ON sp.property_id=v.property_id AND sp.content_id=v.id
 WHERE v.property_id=a.property_id AND (v.state='published' OR sp.content_id IS NOT NULL) ORDER BY v.content_key,v.version DESC LIMIT 200)x),'[]'::jsonb);
END $$;
CREATE FUNCTION worthkind_flow.ai_usage(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role<>'owner' THEN RAISE EXCEPTION 'Owner required' USING ERRCODE='42501'; END IF;
 RETURN jsonb_build_object('window_hours',24,'used_units',COALESCE((SELECT sum(usage_units) FROM worthkind_flow.ai_calls WHERE property_id=a.property_id AND created_at>=now()-interval '24 hours'),0),
 'channels',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT channel,state,count(*) AS calls,sum(usage_units) AS units FROM worthkind_flow.ai_calls WHERE property_id=a.property_id AND created_at>=now()-interval '24 hours' GROUP BY channel,state)x),'[]'::jsonb));
END $$;
CREATE INDEX wf_ai_global_usage ON worthkind_flow.ai_calls(created_at);
REVOKE ALL ON FUNCTION worthkind_flow.configure_ai_platform(boolean,integer),worthkind_flow.list_ai_sources(text,text),worthkind_flow.ai_usage(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.configure_ai_platform(boolean,integer) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.list_ai_sources(text,text),worthkind_flow.ai_usage(text,text) TO wf_ai_policy;
COMMIT;
