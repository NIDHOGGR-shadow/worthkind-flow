BEGIN;
CREATE TABLE worthkind_flow.pms_commands(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 account_alias text NOT NULL,external_property_id text NOT NULL,
 request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
 operation text NOT NULL CHECK(operation IN ('create','cancel','change_checkout','rate_update')),
 intent_id uuid,external_reservation_id text,provider_job_id text,
 state text NOT NULL DEFAULT 'submitting' CHECK(state IN ('submitting','unknown','accepted','verified','error')),
 result jsonb NOT NULL DEFAULT '{}'::jsonb,actor uuid NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),
 FOREIGN KEY(intent_id,property_id) REFERENCES worthkind_flow.reservation_intents(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE UNIQUE INDEX wf_pms_one_creation ON worthkind_flow.pms_commands(intent_id) WHERE operation='create';
CREATE UNIQUE INDEX wf_pms_one_mutation ON worthkind_flow.pms_commands(property_id,external_reservation_id) WHERE state IN ('submitting','unknown','accepted') AND external_reservation_id IS NOT NULL;
ALTER TABLE worthkind_flow.pms_commands ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.pms_commands FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.pms_commands FROM PUBLIC;
CREATE FUNCTION worthkind_flow.begin_pms_command(p_subject text,p_slug text,p_op text,p_key text,p_hash text,p_intent uuid,p_external text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; cfg worthkind_flow.pms_accounts%ROWTYPE; c worthkind_flow.pms_commands%ROWTYPE; i worthkind_flow.reservation_intents%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO cfg FROM worthkind_flow.pms_accounts WHERE property_id=a.property_id AND enabled AND provider='cloudbeds';
 IF NOT FOUND THEN RAISE EXCEPTION 'PMS unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO c FROM worthkind_flow.pms_commands WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
 IF c.operation<>p_op OR c.payload_hash<>p_hash OR c.intent_id IS DISTINCT FROM p_intent OR (p_op IN ('cancel','change_checkout') AND c.external_reservation_id IS DISTINCT FROM p_external) THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN (to_jsonb(c)-'property_id'-'actor'-'payload_hash')||jsonb_build_object('submit',false);
 END IF;
 IF p_op='create' THEN
 SELECT * INTO i FROM worthkind_flow.reservation_intents WHERE id=p_intent AND property_id=a.property_id AND state='under_review' FOR UPDATE;
 IF NOT FOUND OR i.room_count<>1 OR i.room_type_id IS NULL OR i.arrival<(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=a.property_id)
 OR EXISTS(SELECT 1 FROM worthkind_flow.pms_reservation_evidence WHERE intent_id=p_intent) THEN RAISE EXCEPTION 'Single-room PMS intent unavailable' USING ERRCODE='23514'; END IF;
 ELSIF p_op IN ('cancel','change_checkout') THEN
 IF p_intent IS NOT NULL OR NOT EXISTS(SELECT 1 FROM worthkind_flow.pms_reservation_evidence e WHERE e.property_id=a.property_id AND e.external_reservation_id=p_external AND e.account_alias=cfg.account_alias AND e.external_property_id=cfg.external_property_id AND e.provider_state IN ('confirmed','not_confirmed')) THEN RAISE EXCEPTION 'Reservation evidence unavailable' USING ERRCODE='23514'; END IF;
 ELSIF p_op='rate_update' THEN
 IF p_intent IS NOT NULL OR p_external IS NOT NULL THEN RAISE EXCEPTION 'Invalid rate command' USING ERRCODE='22023'; END IF;
 ELSE RAISE EXCEPTION 'Invalid operation' USING ERRCODE='22023'; END IF;
 INSERT INTO worthkind_flow.pms_commands(property_id,account_alias,external_property_id,request_key,payload_hash,operation,intent_id,external_reservation_id,actor)
 VALUES(a.property_id,cfg.account_alias,cfg.external_property_id,p_key,p_hash,p_op,p_intent,p_external,a.member_id) RETURNING * INTO c;
 RETURN (to_jsonb(c)-'property_id'-'actor'-'payload_hash')||jsonb_build_object('submit',true,'intent',CASE WHEN p_op='create' THEN jsonb_build_object('room_type_id',i.room_type_id,'arrival',i.arrival,'departure',i.departure,'adults',i.adults,'children',i.children) ELSE NULL END);
END $$;
CREATE FUNCTION worthkind_flow.finish_pms_command(p_subject text,p_slug text,p_id uuid,p_state text,p_external text,p_job text,p_result jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; c worthkind_flow.pms_commands%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='42501'; END IF;
 SELECT * INTO c FROM worthkind_flow.pms_commands WHERE id=p_id AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Command unavailable' USING ERRCODE='P0002'; END IF;
 IF c.state IN ('verified','error') THEN RETURN to_jsonb(c)-'property_id'-'actor'-'payload_hash'; END IF;
 IF p_state NOT IN ('unknown','accepted','verified','error') OR jsonb_typeof(p_result)<>'object' OR octet_length(p_result::text)>12000 THEN RAISE EXCEPTION 'Invalid result' USING ERRCODE='22023'; END IF;
 IF c.operation='rate_update' AND p_state IN ('accepted','verified','error') AND COALESCE(c.provider_job_id,p_job) IS NULL THEN RAISE EXCEPTION 'Job reference required' USING ERRCODE='23514'; END IF;
 IF c.operation<>'rate_update' AND p_state='verified' AND COALESCE(c.external_reservation_id,p_external) IS NULL THEN RAISE EXCEPTION 'Reservation readback required' USING ERRCODE='23514'; END IF;
 IF c.external_reservation_id IS NOT NULL AND p_external IS NOT NULL AND c.external_reservation_id<>p_external OR c.provider_job_id IS NOT NULL AND p_job IS NOT NULL AND c.provider_job_id<>p_job THEN RAISE EXCEPTION 'Provider identifier conflict' USING ERRCODE='23505'; END IF;
 UPDATE worthkind_flow.pms_commands SET state=p_state,external_reservation_id=COALESCE(external_reservation_id,p_external),provider_job_id=COALESCE(provider_job_id,p_job),result=p_result,updated_at=now() WHERE id=c.id RETURNING * INTO c;
 RETURN to_jsonb(c)-'property_id'-'actor'-'payload_hash';
END $$;
CREATE FUNCTION worthkind_flow.staff_pms_commands(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)-'property_id'-'actor'-'payload_hash') FROM (SELECT * FROM worthkind_flow.pms_commands WHERE property_id=a.property_id ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.begin_pms_command(text,text,text,text,text,uuid,text),worthkind_flow.finish_pms_command(text,text,uuid,text,text,text,jsonb),worthkind_flow.staff_pms_commands(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.begin_pms_command(text,text,text,text,text,uuid,text),worthkind_flow.staff_pms_commands(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.finish_pms_command(text,text,uuid,text,text,text,jsonb) TO wf_pms_provider;
COMMIT;
