BEGIN;
CREATE TABLE worthkind_flow.identity_provisioning_events (
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 identity_id uuid NOT NULL REFERENCES worthkind_flow.staff_identities(id),
 operator_reference text NOT NULL,
 evidence_reference text NOT NULL,
 created_at timestamptz NOT NULL DEFAULT now()
);
ALTER TABLE worthkind_flow.identity_provisioning_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.identity_provisioning_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.identity_provisioning_events FROM PUBLIC;
CREATE FUNCTION worthkind_flow.register_staff_identity(p_subject text,p_operator text,p_evidence text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_identity uuid;
BEGIN
 IF p_operator IS NULL OR length(btrim(p_operator)) NOT BETWEEN 3 AND 255 OR
 p_evidence IS NULL OR length(btrim(p_evidence)) NOT BETWEEN 8 AND 255 THEN
 RAISE EXCEPTION 'Verification reference required' USING ERRCODE='22023'; END IF;
 INSERT INTO worthkind_flow.staff_identities(provider_subject) VALUES(p_subject)
 ON CONFLICT(provider_subject) DO NOTHING RETURNING id INTO v_identity;
 IF v_identity IS NULL THEN RAISE EXCEPTION 'Identity already registered' USING ERRCODE='23505'; END IF;
 INSERT INTO worthkind_flow.identity_provisioning_events(identity_id,operator_reference,evidence_reference)
 VALUES(v_identity,p_operator,p_evidence);
 RETURN v_identity;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.register_staff_identity(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.register_staff_identity(text,text,text) TO wf_hotel_provisioner;
COMMIT;
