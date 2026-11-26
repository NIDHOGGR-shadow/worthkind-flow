BEGIN;
CREATE FUNCTION worthkind_flow.staff_payment_account(p_subject text,p_slug text)
RETURNS TABLE(account_alias text,mode text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT p.account_alias,p.mode FROM worthkind_flow.hotel_payment_accounts p WHERE p.property_id=a.property_id AND p.enabled;
 IF NOT FOUND THEN RAISE EXCEPTION 'Payment account unavailable' USING ERRCODE='P0002'; END IF;
END $$;
CREATE FUNCTION worthkind_flow.compare_settlement_page(p_subject text,p_slug text,p_alias text,p_mode text,p_rows jsonb)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; cfg worthkind_flow.hotel_payment_accounts%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO cfg FROM worthkind_flow.hotel_payment_accounts WHERE property_id=a.property_id AND enabled;
 IF NOT FOUND OR cfg.account_alias IS DISTINCT FROM p_alias OR cfg.mode IS DISTINCT FROM p_mode THEN RAISE EXCEPTION 'Account mismatch' USING ERRCODE='42501'; END IF;
 IF p_rows IS NULL OR jsonb_typeof(p_rows)<>'array' THEN RAISE EXCEPTION 'Invalid transaction list' USING ERRCODE='22023'; END IF;
 IF jsonb_array_length(p_rows)>50 THEN RAISE EXCEPTION 'Page too large' USING ERRCODE='22023'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(jsonb_build_object('reference',x.reference,'provider_transaction_id',x.transaction_id,
 'amount_minor',x.amount_minor,'currency',x.currency,'provider_status',x.status,'payment_id',p.id,
 'comparison',CASE WHEN p.id IS NULL THEN 'not_in_flow' WHEN p.provider_transaction_id IS NULL THEN 'unverified_flow_payment'
 WHEN p.provider_transaction_id IS DISTINCT FROM x.transaction_id OR p.amount_minor IS DISTINCT FROM x.amount_minor OR p.currency IS DISTINCT FROM x.currency OR x.status<>'success'
 THEN 'mismatch' ELSE 'matched_verified_payment' END))
 FROM jsonb_to_recordset(p_rows) AS x(reference text,transaction_id numeric,amount_minor bigint,currency text,status text)
 LEFT JOIN worthkind_flow.hotel_payment_intents p ON p.property_id=a.property_id AND p.account_alias=p_alias AND p.mode=p_mode AND p.reference=x.reference),'[]'::jsonb);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.staff_payment_account(text,text),worthkind_flow.compare_settlement_page(text,text,text,text,jsonb) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.staff_payment_account(text,text),worthkind_flow.compare_settlement_page(text,text,text,text,jsonb) TO wf_operations;
COMMIT;
