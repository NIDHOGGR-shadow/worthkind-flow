BEGIN;
CREATE ROLE wf_public_content NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_public_content;
CREATE TABLE worthkind_flow.content_versions(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 content_key text NOT NULL CHECK(content_key ~ '^[a-z0-9][a-z0-9_-]{1,79}$'),
 version integer NOT NULL CHECK(version>0),
 content jsonb NOT NULL CHECK(jsonb_typeof(content)='object' AND octet_length(content::text)<=16000),
 source_reference text NOT NULL CHECK(length(btrim(source_reference)) BETWEEN 8 AND 240),
 author uuid NOT NULL, reviewer uuid, state text NOT NULL DEFAULT 'draft' CHECK(state IN ('draft','published','rejected','withdrawn')),
 created_at timestamptz NOT NULL DEFAULT now(), decided_at timestamptz,
 UNIQUE(property_id,content_key,version), UNIQUE(id,property_id),
 FOREIGN KEY(author,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(reviewer,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE UNIQUE INDEX wf_one_published_version ON worthkind_flow.content_versions(property_id,content_key) WHERE state='published';
CREATE TABLE worthkind_flow.content_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), property_id uuid NOT NULL, content_id uuid NOT NULL, actor uuid NOT NULL,
 action text NOT NULL, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(content_id,property_id) REFERENCES worthkind_flow.content_versions(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.content_versions ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.content_versions FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.content_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.content_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.content_versions,worthkind_flow.content_events FROM PUBLIC;
CREATE FUNCTION worthkind_flow.draft_content(p_subject text,p_slug text,p_key text,p_content jsonb,p_source text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid; v_version integer;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT COALESCE(max(version),0)+1 INTO v_version FROM worthkind_flow.content_versions WHERE property_id=a.property_id AND content_key=p_key;
 INSERT INTO worthkind_flow.content_versions(property_id,content_key,version,content,source_reference,author)
 VALUES(a.property_id,p_key,v_version,p_content,p_source,a.member_id) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.content_events(property_id,content_id,actor,action) VALUES(a.property_id,v_id,a.member_id,'drafted');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.decide_content(p_subject text,p_slug text,p_id uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; c worthkind_flow.content_versions%ROWTYPE; v_state text; old_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO c FROM worthkind_flow.content_versions WHERE id=p_id AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Content unavailable' USING ERRCODE='P0002'; END IF;
 IF p_action='publish' AND c.state='draft' THEN
   IF EXISTS(SELECT 1 FROM worthkind_flow.content_versions WHERE property_id=a.property_id AND content_key=c.content_key AND version>c.version AND state='published') THEN
     RAISE EXCEPTION 'Stale version' USING ERRCODE='23514'; END IF;
   FOR old_id IN UPDATE worthkind_flow.content_versions SET state='withdrawn',reviewer=a.member_id,decided_at=now()
     WHERE property_id=a.property_id AND content_key=c.content_key AND state='published' RETURNING id
   LOOP
     INSERT INTO worthkind_flow.content_events(property_id,content_id,actor,action) VALUES(a.property_id,old_id,a.member_id,'superseded');
   END LOOP;
   v_state='published';
 ELSIF p_action='reject' AND c.state='draft' THEN v_state='rejected';
 ELSIF p_action='withdraw' AND c.state='published' THEN v_state='withdrawn';
 ELSE RAISE EXCEPTION 'Invalid content transition' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.content_versions SET state=v_state,reviewer=a.member_id,decided_at=now() WHERE id=c.id;
 INSERT INTO worthkind_flow.content_events(property_id,content_id,actor,action) VALUES(a.property_id,c.id,a.member_id,p_action);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.read_public_content(p_slug text)
RETURNS TABLE(content_key text,version integer,content jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT c.content_key,c.version,c.content FROM worthkind_flow.content_versions c
 JOIN worthkind_flow.properties p ON p.id=c.property_id JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' AND c.state='published' ORDER BY c.content_key
$$;
CREATE FUNCTION worthkind_flow.list_content(p_subject text,p_slug text)
RETURNS TABLE(id uuid,content_key text,version integer,content jsonb,state text,source_reference text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT c.id,c.content_key,c.version,c.content,c.state,c.source_reference FROM worthkind_flow.content_versions c
 WHERE c.property_id=a.property_id ORDER BY c.created_at DESC,c.id LIMIT 100;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.draft_content(text,text,text,jsonb,text),worthkind_flow.decide_content(text,text,uuid,text),
 worthkind_flow.read_public_content(text),worthkind_flow.list_content(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.draft_content(text,text,text,jsonb,text),worthkind_flow.decide_content(text,text,uuid,text),worthkind_flow.list_content(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.read_public_content(text) TO wf_public_content;
COMMIT;
