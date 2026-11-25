BEGIN;
CREATE FUNCTION worthkind_flow.guard_cancelled_pos_evidence()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF OLD.cancelled_at IS NOT NULL THEN NEW.cancelled_at=OLD.cancelled_at; END IF;
 IF NEW.cancelled_at IS NOT NULL THEN NEW.matched=false; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_cancelled_pos_guard BEFORE UPDATE ON worthkind_flow.pos_receipt_evidence FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_cancelled_pos_evidence();
REVOKE ALL ON FUNCTION worthkind_flow.guard_cancelled_pos_evidence() FROM PUBLIC;
COMMIT;
