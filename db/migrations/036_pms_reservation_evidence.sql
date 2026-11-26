BEGIN;
CREATE ROLE wf_pms_provider NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_pms_provider;
CREATE TABLE worthkind_flow.pms_reservation_evidence(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 account_alias text NOT NULL,external_property_id text NOT NULL,external_reservation_id text NOT NULL CHECK(length(external_reservation_id) BETWEEN 1 AND 100),
 intent_id uuid,provider_state text NOT NULL CHECK(provider_state IN ('confirmed','not_confirmed','canceled','checked_in','checked_out','no_show','in_progress')),
 arrival date NOT NULL,departure date NOT NULL CHECK(departure>arrival),
 source_id text,source_name text,channel_reservation_id text,
 retrieved_at timestamptz NOT NULL DEFAULT now(),revision bigint NOT NULL DEFAULT 1,
 UNIQUE(property_id,external_reservation_id),UNIQUE(intent_id),UNIQUE(id,property_id),
 FOREIGN KEY(intent_id,property_id) REFERENCES worthkind_flow.reservation_intents(id,property_id)
);
CREATE TABLE worthkind_flow.pms_reservation_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,evidence_id uuid NOT NULL,actor uuid NOT NULL,
 action text NOT NULL,details jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(evidence_id,property_id) REFERENCES worthkind_flow.pms_reservation_evidence(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.pms_reservation_evidence ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.pms_reservation_evidence FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.pms_reservation_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.pms_reservation_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.pms_reservation_evidence,worthkind_flow.pms_reservation_events FROM PUBLIC;
CREATE FUNCTION worthkind_flow.record_pms_reservation(p_subject text,p_slug text,p_external_property text,p_alias text,p_external_id text,p_state text,p_arrival date,p_departure date,p_source_id text,p_source_name text,p_channel_id text,p_intent uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; cfg worthkind_flow.pms_accounts%ROWTYPE; e worthkind_flow.pms_reservation_evidence%ROWTYPE; r worthkind_flow.reservation_intents%ROWTYPE; old_data jsonb;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO cfg FROM worthkind_flow.pms_accounts WHERE property_id=a.property_id AND enabled AND provider='cloudbeds';
 IF NOT FOUND OR cfg.external_property_id IS DISTINCT FROM p_external_property OR cfg.account_alias IS DISTINCT FROM p_alias THEN RAISE EXCEPTION 'PMS account mismatch' USING ERRCODE='42501'; END IF;
 IF p_intent IS NOT NULL THEN
 SELECT * INTO r FROM worthkind_flow.reservation_intents WHERE id=p_intent AND property_id=a.property_id AND state='under_review' FOR UPDATE;
 IF NOT FOUND OR r.arrival<>p_arrival OR r.departure<>p_departure THEN RAISE EXCEPTION 'Intent date or state mismatch' USING ERRCODE='23514'; END IF;
 IF EXISTS(SELECT 1 FROM worthkind_flow.native_bookings WHERE intent_id=p_intent AND state IN ('held','confirmed')) THEN RAISE EXCEPTION 'Native booking conflict' USING ERRCODE='23514'; END IF;
 END IF;
 SELECT * INTO e FROM worthkind_flow.pms_reservation_evidence WHERE property_id=a.property_id AND external_reservation_id=p_external_id FOR UPDATE;
 IF FOUND THEN
 IF e.account_alias<>p_alias OR e.external_property_id<>p_external_property OR (p_intent IS NOT NULL AND e.intent_id IS NOT NULL AND e.intent_id<>p_intent) THEN
 RAISE EXCEPTION 'Existing provider link conflict' USING ERRCODE='23505'; END IF;
 old_data:=jsonb_build_object('state',e.provider_state,'arrival',e.arrival,'departure',e.departure,'intent_id',e.intent_id);
 UPDATE worthkind_flow.pms_reservation_evidence SET provider_state=p_state,arrival=p_arrival,departure=p_departure,
 source_id=p_source_id,source_name=p_source_name,channel_reservation_id=p_channel_id,intent_id=COALESCE(intent_id,p_intent),retrieved_at=now(),revision=revision+1
 WHERE id=e.id RETURNING * INTO e;
 ELSE
 INSERT INTO worthkind_flow.pms_reservation_evidence(property_id,account_alias,external_property_id,external_reservation_id,intent_id,provider_state,arrival,departure,source_id,source_name,channel_reservation_id)
 VALUES(a.property_id,p_alias,p_external_property,p_external_id,p_intent,p_state,p_arrival,p_departure,p_source_id,p_source_name,p_channel_id) RETURNING * INTO e;
 END IF;
 INSERT INTO worthkind_flow.pms_reservation_events(property_id,evidence_id,actor,action,details) VALUES(a.property_id,e.id,a.member_id,'provider_readback',
 jsonb_build_object('previous',old_data,'state',p_state,'arrival',p_arrival,'departure',p_departure));
 RETURN to_jsonb(e)-'property_id'-'account_alias'-'external_property_id';
END $$;
CREATE FUNCTION worthkind_flow.list_pms_evidence(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,external_reservation_id,intent_id,provider_state,arrival,departure,source_id,source_name,channel_reservation_id,retrieved_at,revision
 FROM worthkind_flow.pms_reservation_evidence WHERE property_id=a.property_id ORDER BY retrieved_at DESC LIMIT 200)x),'[]'::jsonb);
END $$;
CREATE FUNCTION worthkind_flow.guard_pms_reconfiguration()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF TG_OP='UPDATE' AND (NEW.account_alias<>OLD.account_alias OR NEW.external_property_id<>OLD.external_property_id)
 AND EXISTS(SELECT 1 FROM worthkind_flow.pms_reservation_evidence WHERE property_id=OLD.property_id) THEN RAISE EXCEPTION 'Existing PMS evidence requires migration' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_pms_history_guard BEFORE UPDATE ON worthkind_flow.pms_accounts FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_pms_reconfiguration();
REVOKE ALL ON FUNCTION worthkind_flow.record_pms_reservation(text,text,text,text,text,text,date,date,text,text,text,uuid),
 worthkind_flow.list_pms_evidence(text,text),worthkind_flow.guard_pms_reconfiguration() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.record_pms_reservation(text,text,text,text,text,text,date,date,text,text,text,uuid) TO wf_pms_provider;
GRANT EXECUTE ON FUNCTION worthkind_flow.list_pms_evidence(text,text) TO wf_operations;
COMMIT;
