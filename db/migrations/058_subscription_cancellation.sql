BEGIN;
-- Immutable cancellation record; no provider payment or refund is implied.
ALTER TABLE worthkind_flow.platform_subscription_terms ADD UNIQUE(id,property_id);
CREATE TABLE worthkind_flow.platform_subscription_cancellations(
 term_id uuid PRIMARY KEY,property_id uuid NOT NULL,request_key uuid NOT NULL,
 effective_at timestamptz NOT NULL,
 operator_reference text NOT NULL CHECK(length(btrim(operator_reference)) BETWEEN 3 AND 255),
 evidence_reference text NOT NULL CHECK(length(btrim(evidence_reference)) BETWEEN 8 AND 255),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),
 FOREIGN KEY(term_id,property_id) REFERENCES worthkind_flow.platform_subscription_terms(id,property_id)
);
ALTER TABLE worthkind_flow.platform_subscription_cancellations ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.platform_subscription_cancellations FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.platform_subscription_cancellations FROM PUBLIC;
CREATE FUNCTION worthkind_flow.cancel_platform_subscription(p_slug text,p_term uuid,p_key uuid,p_operator text,p_evidence text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; t worthkind_flow.platform_subscription_terms%ROWTYPE; c worthkind_flow.platform_subscription_cancellations%ROWTYPE;
BEGIN
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'Property unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO t FROM worthkind_flow.platform_subscription_terms WHERE id=p_term AND property_id=v_property;
 IF NOT FOUND THEN RAISE EXCEPTION 'Term unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO c FROM worthkind_flow.platform_subscription_cancellations WHERE property_id=v_property AND (term_id=p_term OR request_key=p_key) ORDER BY term_id LIMIT 1;
 IF FOUND THEN
 IF ROW(c.term_id,c.request_key,c.operator_reference,c.evidence_reference) IS DISTINCT FROM ROW(p_term,p_key,p_operator,p_evidence) THEN
 RAISE EXCEPTION 'Cancellation conflict' USING ERRCODE='23505'; END IF;
 RETURN jsonb_build_object('term_id',c.term_id,'effective_at',c.effective_at,'duplicate',true); END IF;
 IF p_key IS NULL OR p_operator IS NULL OR p_evidence IS NULL OR t.ends_at<=now() THEN RAISE EXCEPTION 'Invalid cancellation' USING ERRCODE='22023'; END IF;
 INSERT INTO worthkind_flow.platform_subscription_cancellations(term_id,property_id,request_key,effective_at,operator_reference,evidence_reference)
 VALUES(p_term,v_property,p_key,GREATEST(now(),t.starts_at),p_operator,p_evidence) RETURNING * INTO c;
 IF t.starts_at<=now() THEN
 UPDATE worthkind_flow.ai_calls SET state='revoked',finished_at=now() WHERE property_id=v_property AND state='reserved';
 END IF;
 RETURN jsonb_build_object('term_id',c.term_id,'effective_at',c.effective_at,'duplicate',false);
END $$;
CREATE OR REPLACE FUNCTION worthkind_flow.record_platform_subscription(p_slug text,p_plan uuid,p_key uuid,p_start timestamptz,p_end timestamptz,p_operator text,p_evidence text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; q worthkind_flow.platform_subscription_terms%ROWTYPE;
BEGIN
 IF p_start IS NULL OR p_end IS NULL OR NOT isfinite(p_start) OR NOT isfinite(p_end) OR p_end<=p_start THEN
 RAISE EXCEPTION 'Invalid subscription term' USING ERRCODE='22023'; END IF;
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'Property unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO q FROM worthkind_flow.platform_subscription_terms WHERE property_id=v_property AND request_key=p_key;
 IF FOUND THEN
 IF ROW(q.plan_id,q.starts_at,q.ends_at,q.operator_reference,q.evidence_reference) IS DISTINCT FROM ROW(p_plan,p_start,p_end,p_operator,p_evidence) THEN
 RAISE EXCEPTION 'Subscription request conflict' USING ERRCODE='23505'; END IF;
 RETURN q.id; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.platform_plans WHERE id=p_plan) THEN RAISE EXCEPTION 'Plan unavailable' USING ERRCODE='P0002'; END IF;
 IF EXISTS(SELECT 1 FROM worthkind_flow.platform_subscription_terms t LEFT JOIN worthkind_flow.platform_subscription_cancellations c ON c.term_id=t.id
 WHERE t.property_id=v_property AND t.starts_at<p_end AND LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at))>p_start
 AND t.starts_at<LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at))) THEN
 RAISE EXCEPTION 'Overlapping subscription term' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.platform_subscription_terms(property_id,plan_id,request_key,starts_at,ends_at,operator_reference,evidence_reference)
 VALUES(v_property,p_plan,p_key,p_start,p_end,p_operator,p_evidence) RETURNING * INTO q;
 RETURN q.id;
END $$;
CREATE OR REPLACE FUNCTION worthkind_flow.read_platform_subscription(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_term jsonb;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT jsonb_build_object('id',t.id,'starts_at',t.starts_at,'ends_at',LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at)),'plan_code',p.code,'plan_version',p.version,'plan_name',p.name,
 'currency',p.currency,'monthly_price_minor',p.monthly_price_minor::text,'included_ai_calls',p.included_ai_calls)
 INTO v_term FROM worthkind_flow.platform_subscription_terms t JOIN worthkind_flow.platform_plans p ON p.id=t.plan_id
 LEFT JOIN worthkind_flow.platform_subscription_cancellations c ON c.term_id=t.id
 WHERE t.property_id=a.property_id AND t.starts_at<=statement_timestamp() AND LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at))>statement_timestamp();
 RETURN jsonb_build_object('status',CASE WHEN v_term IS NULL THEN 'no_current_term' ELSE 'contract_recorded' END,
 'term',v_term,'payment_verified',false,'usage_allowance_enforced',false);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.cancel_platform_subscription(text,uuid,uuid,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.cancel_platform_subscription(text,uuid,uuid,text,text) TO wf_hotel_provisioner;
COMMIT;
