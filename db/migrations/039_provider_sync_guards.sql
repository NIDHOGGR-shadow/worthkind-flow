BEGIN;
-- Never close a booking intent while an external booking may exist.
CREATE FUNCTION worthkind_flow.guard_pms_intent_state()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF NEW.state<>OLD.state AND NEW.state IN ('withdrawn','declined') AND (
 EXISTS(SELECT 1 FROM worthkind_flow.pms_commands c WHERE c.intent_id=NEW.id AND c.property_id=NEW.property_id AND c.operation='create' AND c.state IN ('submitting','accepted','unknown'))
 OR EXISTS(SELECT 1 FROM worthkind_flow.pms_reservation_evidence e WHERE e.intent_id=NEW.id AND e.property_id=NEW.property_id AND e.provider_state NOT IN ('canceled','checked_out','no_show'))) THEN
 RAISE EXCEPTION 'External booking must be resolved first' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_pms_intent_guard BEFORE UPDATE OF state ON worthkind_flow.reservation_intents FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_pms_intent_state();
CREATE FUNCTION worthkind_flow.get_pms_command(p_subject text,p_slug text,p_id uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; c worthkind_flow.pms_commands%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='42501'; END IF;
 SELECT * INTO c FROM worthkind_flow.pms_commands WHERE property_id=a.property_id AND id=p_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Command unavailable' USING ERRCODE='P0002'; END IF;
 RETURN to_jsonb(c)-'property_id'-'actor'-'payload_hash';
END $$;
CREATE FUNCTION worthkind_flow.linked_pos_receipts(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT e.order_id,e.receipt_number FROM worthkind_flow.pos_receipt_evidence e JOIN worthkind_flow.pos_accounts p ON p.property_id=e.property_id AND p.enabled AND p.account_alias=e.account_alias WHERE e.property_id=a.property_id ORDER BY e.recorded_at,e.id LIMIT 50)x),'[]'::jsonb);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.guard_pms_intent_state(),worthkind_flow.get_pms_command(text,text,uuid),worthkind_flow.linked_pos_receipts(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.get_pms_command(text,text,uuid),worthkind_flow.linked_pos_receipts(text,text) TO wf_operations;
COMMIT;
