-- Small encrypted private documents; not a public media CDN.
BEGIN;
CREATE ROLE wf_document_store NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_document_store;
CREATE TABLE worthkind_flow.private_documents(
 id uuid PRIMARY KEY,
 property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 created_by uuid NOT NULL REFERENCES worthkind_flow.staff_identities(id),
 ciphertext bytea NOT NULL CHECK(octet_length(ciphertext) BETWEEN 29 AND 3000000),
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE worthkind_flow.private_documents ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.private_documents FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.private_documents FROM PUBLIC;
CREATE FUNCTION worthkind_flow.write_private_document(p_actor text,p_slug text,p_id uuid,p_cipher bytea)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_actor uuid; v_role text;
BEGIN
 SELECT s.property_id,s.actor_id,s.membership_role INTO v_property,v_actor,v_role
 FROM worthkind_flow.resolve_staff_session(p_actor,p_slug,'case:read') s;
 IF v_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 INSERT INTO worthkind_flow.private_documents(id,property_id,created_by,ciphertext)
 VALUES(p_id,v_property,v_actor,p_cipher);
 RETURN p_id;
END $$;
CREATE FUNCTION worthkind_flow.read_private_document(p_actor text,p_slug text,p_id uuid)
RETURNS bytea LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_role text; v_cipher bytea;
BEGIN
 SELECT s.property_id,s.membership_role INTO v_property,v_role
 FROM worthkind_flow.resolve_staff_session(p_actor,p_slug,'case:read') s;
 IF v_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT d.ciphertext INTO v_cipher FROM worthkind_flow.private_documents d
 WHERE d.id=p_id AND d.property_id=v_property;
 IF v_cipher IS NULL THEN RAISE EXCEPTION 'Document unavailable' USING ERRCODE='P0002'; END IF;
 RETURN v_cipher;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.write_private_document(text,text,uuid,bytea),
 worthkind_flow.read_private_document(text,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.write_private_document(text,text,uuid,bytea),
 worthkind_flow.read_private_document(text,text,uuid) TO wf_document_store;
COMMIT;
