BEGIN;
CREATE FUNCTION worthkind_flow.check_pms_command_payload(p_subject text,p_slug text,p_id uuid,p_hash text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='42501'; END IF;
 RETURN EXISTS(SELECT 1 FROM worthkind_flow.pms_commands c WHERE c.property_id=a.property_id AND c.id=p_id AND c.payload_hash=p_hash);
END $$;
CREATE FUNCTION worthkind_flow.guard_pms_pending_account()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.account_alias<>OLD.account_alias OR NEW.external_property_id<>OLD.external_property_id)
 AND EXISTS(SELECT 1 FROM worthkind_flow.pms_commands c WHERE c.property_id=OLD.property_id) THEN
 RAISE EXCEPTION 'Provider commands require account history migration' USING ERRCODE='23514'; END IF;
 IF NOT NEW.enabled AND EXISTS(SELECT 1 FROM worthkind_flow.pms_commands c WHERE c.property_id=NEW.property_id AND c.state IN ('submitting','accepted','unknown')) THEN
 RAISE EXCEPTION 'Resolve pending provider commands before disabling account' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_pms_pending_account_guard BEFORE UPDATE ON worthkind_flow.pms_accounts FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_pms_pending_account();
REVOKE ALL ON FUNCTION worthkind_flow.check_pms_command_payload(text,text,uuid,text),worthkind_flow.guard_pms_pending_account() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.check_pms_command_payload(text,text,uuid,text) TO wf_operations;
COMMIT;
