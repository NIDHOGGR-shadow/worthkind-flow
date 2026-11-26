BEGIN;
CREATE TABLE worthkind_flow.pms_accounts(
 property_id uuid PRIMARY KEY REFERENCES worthkind_flow.properties(id),provider text NOT NULL CHECK(provider='cloudbeds'),
 external_property_id text NOT NULL CHECK(external_property_id ~ '^[A-Za-z0-9_-]{1,80}$'),
 account_alias text NOT NULL UNIQUE CHECK(account_alias ~ '^[A-Za-z0-9_-]{3,80}$'),
 approval_reference text NOT NULL CHECK(length(btrim(approval_reference)) BETWEEN 8 AND 240),enabled boolean NOT NULL DEFAULT false,
 UNIQUE(provider,external_property_id)
);
ALTER TABLE worthkind_flow.pms_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.pms_accounts FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.pms_accounts FROM PUBLIC;
CREATE FUNCTION worthkind_flow.configure_cloudbeds(p_slug text,p_external text,p_alias text,p_approval text,p_enabled boolean)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'Hotel unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.pms_accounts(property_id,provider,external_property_id,account_alias,approval_reference,enabled)
 VALUES(v_property,'cloudbeds',p_external,p_alias,p_approval,p_enabled)
 ON CONFLICT(property_id) DO UPDATE SET external_property_id=EXCLUDED.external_property_id,account_alias=EXCLUDED.account_alias,approval_reference=EXCLUDED.approval_reference,enabled=EXCLUDED.enabled;
 RETURN v_property;
END $$;
CREATE FUNCTION worthkind_flow.staff_pms_account(p_subject text,p_slug text)
RETURNS TABLE(external_property_id text,account_alias text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT p.external_property_id,p.account_alias FROM worthkind_flow.pms_accounts p
 WHERE p.property_id=a.property_id AND p.provider='cloudbeds' AND p.enabled;
 IF NOT FOUND THEN RAISE EXCEPTION 'PMS unavailable' USING ERRCODE='P0002'; END IF;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.configure_cloudbeds(text,text,text,text,boolean),worthkind_flow.staff_pms_account(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.configure_cloudbeds(text,text,text,text,boolean) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.staff_pms_account(text,text) TO wf_operations;
COMMIT;
