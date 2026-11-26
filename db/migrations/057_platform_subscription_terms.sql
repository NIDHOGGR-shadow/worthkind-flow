BEGIN;
-- Contract records, not a payment ledger. No price or plan is preselected.
CREATE TABLE worthkind_flow.platform_plans(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 code text NOT NULL CHECK(code ~ '^[a-z0-9][a-z0-9_-]{2,63}$'),
 version integer NOT NULL CHECK(version>0),
 name text NOT NULL CHECK(length(btrim(name)) BETWEEN 2 AND 120),
 currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
 monthly_price_minor bigint NOT NULL CHECK(monthly_price_minor>=0),
 included_ai_calls integer NOT NULL CHECK(included_ai_calls>=0),
 operator_reference text NOT NULL CHECK(length(btrim(operator_reference)) BETWEEN 3 AND 255),
 evidence_reference text NOT NULL CHECK(length(btrim(evidence_reference)) BETWEEN 8 AND 255),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(code,version)
);
CREATE TABLE worthkind_flow.platform_subscription_terms(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 plan_id uuid NOT NULL REFERENCES worthkind_flow.platform_plans(id),
 request_key uuid NOT NULL,
 starts_at timestamptz NOT NULL,ends_at timestamptz NOT NULL CHECK(ends_at>starts_at),
 operator_reference text NOT NULL CHECK(length(btrim(operator_reference)) BETWEEN 3 AND 255),
 evidence_reference text NOT NULL CHECK(length(btrim(evidence_reference)) BETWEEN 8 AND 255),
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key)
);
CREATE INDEX wf_platform_term_lookup ON worthkind_flow.platform_subscription_terms(property_id,starts_at,ends_at);
ALTER TABLE worthkind_flow.platform_plans ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.platform_plans FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.platform_subscription_terms ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.platform_subscription_terms FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.platform_plans,worthkind_flow.platform_subscription_terms FROM PUBLIC;
CREATE FUNCTION worthkind_flow.register_platform_plan(p_code text,p_version integer,p_name text,p_currency text,p_price bigint,p_calls integer,p_operator text,p_evidence text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE q worthkind_flow.platform_plans%ROWTYPE;
BEGIN
 INSERT INTO worthkind_flow.platform_plans(code,version,name,currency,monthly_price_minor,included_ai_calls,operator_reference,evidence_reference)
 VALUES(p_code,p_version,p_name,p_currency,p_price,p_calls,p_operator,p_evidence)
 ON CONFLICT(code,version) DO NOTHING RETURNING * INTO q;
 IF NOT FOUND THEN
 SELECT * INTO q FROM worthkind_flow.platform_plans WHERE code=p_code AND version=p_version;
 IF ROW(q.name,q.currency,q.monthly_price_minor,q.included_ai_calls,q.operator_reference,q.evidence_reference)
 IS DISTINCT FROM ROW(p_name,p_currency,p_price,p_calls,p_operator,p_evidence) THEN
 RAISE EXCEPTION 'Plan version conflict' USING ERRCODE='23505'; END IF;
 END IF;
 RETURN q.id;
END $$;
CREATE FUNCTION worthkind_flow.record_platform_subscription(p_slug text,p_plan uuid,p_key uuid,p_start timestamptz,p_end timestamptz,p_operator text,p_evidence text)
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
 IF EXISTS(SELECT 1 FROM worthkind_flow.platform_subscription_terms t WHERE t.property_id=v_property AND t.starts_at<p_end AND t.ends_at>p_start) THEN
 RAISE EXCEPTION 'Overlapping subscription term' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.platform_subscription_terms(property_id,plan_id,request_key,starts_at,ends_at,operator_reference,evidence_reference)
 VALUES(v_property,p_plan,p_key,p_start,p_end,p_operator,p_evidence) RETURNING * INTO q;
 RETURN q.id;
END $$;
CREATE FUNCTION worthkind_flow.read_platform_subscription(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_term jsonb;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT jsonb_build_object('id',t.id,'starts_at',t.starts_at,'ends_at',t.ends_at,'plan_code',p.code,'plan_version',p.version,'plan_name',p.name,
 'currency',p.currency,'monthly_price_minor',p.monthly_price_minor::text,'included_ai_calls',p.included_ai_calls)
 INTO v_term FROM worthkind_flow.platform_subscription_terms t JOIN worthkind_flow.platform_plans p ON p.id=t.plan_id
 WHERE t.property_id=a.property_id AND t.starts_at<=statement_timestamp() AND t.ends_at>statement_timestamp();
 RETURN jsonb_build_object('status',CASE WHEN v_term IS NULL THEN 'no_current_term' ELSE 'contract_recorded' END,
 'term',v_term,'payment_verified',false,'usage_allowance_enforced',false);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.register_platform_plan(text,integer,text,text,bigint,integer,text,text),worthkind_flow.record_platform_subscription(text,uuid,uuid,timestamptz,timestamptz,text,text),worthkind_flow.read_platform_subscription(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.register_platform_plan(text,integer,text,text,bigint,integer,text,text),worthkind_flow.record_platform_subscription(text,uuid,uuid,timestamptz,timestamptz,text,text) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.read_platform_subscription(text,text) TO wf_operations;
COMMIT;
