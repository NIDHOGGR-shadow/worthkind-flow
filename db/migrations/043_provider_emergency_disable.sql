BEGIN;
-- A provider connection must always be disableable during a security incident.
-- Keep its history intact and prevent native authority until outstanding work is resolved.
CREATE OR REPLACE FUNCTION worthkind_flow.guard_pms_pending_account()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.account_alias<>OLD.account_alias OR NEW.external_property_id<>OLD.external_property_id)
 AND EXISTS(SELECT 1 FROM worthkind_flow.pms_commands c WHERE c.property_id=OLD.property_id) THEN
 RAISE EXCEPTION 'Provider commands require account history migration' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE FUNCTION worthkind_flow.guard_native_after_pms()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF NEW.enabled AND (EXISTS(SELECT 1 FROM worthkind_flow.pms_commands c WHERE c.property_id=NEW.property_id AND c.state IN ('submitting','accepted','unknown'))
 OR EXISTS(SELECT 1 FROM worthkind_flow.pms_reservation_evidence e WHERE e.property_id=NEW.property_id AND e.provider_state IN ('confirmed','not_confirmed','checked_in','in_progress') AND e.departure>=current_date)) THEN
 RAISE EXCEPTION 'Resolve external booking history before changing inventory authority' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_native_pending_external_guard BEFORE INSERT OR UPDATE ON worthkind_flow.native_booking_accounts FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_native_after_pms();
REVOKE ALL ON FUNCTION worthkind_flow.guard_native_after_pms() FROM PUBLIC;
COMMIT;
