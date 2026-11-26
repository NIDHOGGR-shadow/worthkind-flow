BEGIN;
-- Weighted reservations enforce contractual usage, not exact provider-token cost.
CREATE OR REPLACE FUNCTION worthkind_flow.begin_ai_call(p_slug text,p_subject text,p_channel text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE prop uuid; member uuid; cfg worthkind_flow.ai_policies%ROWTYPE; lim worthkind_flow.ai_platform_limits%ROWTYPE; v_id uuid; units integer; term record;
BEGIN
 SELECT * INTO lim FROM worthkind_flow.ai_platform_limits WHERE singleton FOR UPDATE;
 IF NOT FOUND OR NOT lim.enabled THEN RAISE EXCEPTION 'Platform AI unavailable' USING ERRCODE='P0002'; END IF;
 SELECT p.id INTO prop FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'AI unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO cfg FROM worthkind_flow.ai_policies WHERE property_id=prop;
 IF NOT FOUND OR NOT cfg.provider_approved OR NOT (CASE p_channel WHEN 'guest_chat' THEN cfg.guest_chat WHEN 'voice' THEN cfg.voice_enabled WHEN 'staff_assist' THEN cfg.staff_assist ELSE false END) THEN RAISE EXCEPTION 'AI unavailable' USING ERRCODE='P0002'; END IF;
 IF p_channel='staff_assist' THEN
 SELECT member_id INTO member FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 ELSIF p_subject IS NOT NULL THEN RAISE EXCEPTION 'Unexpected staff identity' USING ERRCODE='22023'; END IF;
 units:=CASE WHEN p_channel='voice' THEN 3 ELSE 1 END;
 IF COALESCE((SELECT sum(usage_units) FROM worthkind_flow.ai_calls WHERE created_at>=now()-interval '24 hours'),0)+units>lim.max_daily_units THEN RAISE EXCEPTION 'Platform AI quota exhausted' USING ERRCODE='23514'; END IF;
 IF COALESCE((SELECT sum(usage_units) FROM worthkind_flow.ai_calls WHERE property_id=prop AND created_at>=now()-interval '24 hours'),0)+units>cfg.max_calls_per_day THEN RAISE EXCEPTION 'AI quota exhausted' USING ERRCODE='23514'; END IF;
 -- A property with contract history must have a current uncancelled term.
 SELECT t.starts_at,LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at)) AS ends_at,p.included_ai_calls INTO term
 FROM worthkind_flow.platform_subscription_terms t JOIN worthkind_flow.platform_plans p ON p.id=t.plan_id
 LEFT JOIN worthkind_flow.platform_subscription_cancellations c ON c.term_id=t.id
 WHERE t.property_id=prop AND t.starts_at<=now() AND LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at))>now();
 IF FOUND THEN
 IF COALESCE((SELECT sum(usage_units) FROM worthkind_flow.ai_calls WHERE property_id=prop AND created_at>=term.starts_at AND created_at<term.ends_at),0)+units>term.included_ai_calls THEN
 RAISE EXCEPTION 'Contract AI allowance exhausted' USING ERRCODE='23514'; END IF;
 ELSIF EXISTS(SELECT 1 FROM worthkind_flow.platform_subscription_terms WHERE property_id=prop) THEN
 RAISE EXCEPTION 'Current subscription term required' USING ERRCODE='P0002';
 END IF;
 INSERT INTO worthkind_flow.ai_calls(property_id,actor,channel,policy_revision,usage_units) VALUES(prop,member,p_channel,cfg.revision,units) RETURNING id INTO v_id;
 RETURN v_id;
END $$;
CREATE OR REPLACE FUNCTION worthkind_flow.read_platform_subscription(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_term jsonb; used bigint;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT jsonb_build_object('id',t.id,'starts_at',t.starts_at,'ends_at',LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at)),'plan_code',p.code,'plan_version',p.version,'plan_name',p.name,
 'currency',p.currency,'monthly_price_minor',p.monthly_price_minor::text,'included_ai_calls',p.included_ai_calls)
 INTO v_term FROM worthkind_flow.platform_subscription_terms t JOIN worthkind_flow.platform_plans p ON p.id=t.plan_id
 LEFT JOIN worthkind_flow.platform_subscription_cancellations c ON c.term_id=t.id
 WHERE t.property_id=a.property_id AND t.starts_at<=statement_timestamp() AND LEAST(t.ends_at,COALESCE(c.effective_at,t.ends_at))>statement_timestamp();
 IF v_term IS NOT NULL THEN
 SELECT COALESCE(sum(usage_units),0) INTO used FROM worthkind_flow.ai_calls
 WHERE property_id=a.property_id AND created_at>=(v_term->>'starts_at')::timestamptz AND created_at<(v_term->>'ends_at')::timestamptz;
 END IF;
 RETURN jsonb_build_object('status',CASE WHEN v_term IS NULL THEN 'no_current_term' ELSE 'contract_recorded' END,
 'term',v_term,'payment_verified',false,'usage_allowance_enforced',EXISTS(SELECT 1 FROM worthkind_flow.platform_subscription_terms WHERE property_id=a.property_id), 'used_ai_units',used,'remaining_ai_units',CASE WHEN used IS NULL THEN NULL ELSE GREATEST(0,(v_term->>'included_ai_calls')::bigint-used) END,'allowance_unit','chat=1;voice=3;reserved attempts counted');
END $$;
COMMIT;
