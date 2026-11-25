BEGIN;
ALTER TABLE worthkind_flow.hotel_invoices DROP CONSTRAINT hotel_invoices_state_check;
ALTER TABLE worthkind_flow.hotel_invoices ADD CONSTRAINT hotel_invoices_state_check CHECK(state IN ('issued','paid','refunded','test_verified','test_refunded'));
CREATE OR REPLACE FUNCTION worthkind_flow.record_verified_payment(p_slug text,p_reference text,p_alias text,p_mode text,p_transaction numeric,p_amount bigint,p_currency text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE p worthkind_flow.hotel_payment_intents%ROWTYPE;
BEGIN
 SELECT x.* INTO p FROM worthkind_flow.hotel_payment_intents x JOIN worthkind_flow.properties h ON h.id=x.property_id
 WHERE h.slug=p_slug AND x.reference=p_reference FOR UPDATE OF x;
 IF NOT FOUND THEN RAISE EXCEPTION 'Payment unavailable' USING ERRCODE='P0002'; END IF;
 IF p.account_alias IS DISTINCT FROM p_alias OR p.mode IS DISTINCT FROM p_mode OR p.amount_minor IS DISTINCT FROM p_amount OR p.currency IS DISTINCT FROM p_currency OR p_transaction IS NULL OR p_transaction<=0 OR p_transaction<>trunc(p_transaction) OR p_transaction>18446744073709551615 OR
 (p.provider_transaction_id IS NOT NULL AND p.provider_transaction_id<>p_transaction) OR
 EXISTS(SELECT 1 FROM worthkind_flow.hotel_payment_intents x WHERE x.account_alias=p_alias AND x.mode=p_mode AND x.provider_transaction_id=p_transaction AND x.id<>p.id) THEN
 INSERT INTO worthkind_flow.finance_exceptions(property_id,payment_id,kind) VALUES(p.property_id,p.id,'verification_mismatch') ON CONFLICT DO NOTHING;
 RETURN 'mismatch'; END IF;
 IF p.state IN ('verified','refunded') THEN RETURN p.state; END IF;
 UPDATE worthkind_flow.hotel_payment_intents SET state='verified',provider_transaction_id=p_transaction,verified_at=now() WHERE id=p.id;
 UPDATE worthkind_flow.hotel_invoices SET state=CASE WHEN p.mode='live' THEN 'paid' ELSE 'test_verified' END WHERE id=p.invoice_id AND property_id=p.property_id;
 INSERT INTO worthkind_flow.finance_events(property_id,resource_id,action) VALUES(p.property_id,p.id,'payment_verified');
 RETURN 'verified';
END $$;

CREATE OR REPLACE FUNCTION worthkind_flow.record_refund_result(p_slug text,p_refund uuid,p_provider_id numeric,p_transaction numeric,p_mode text,p_amount bigint,p_currency text,p_state text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE r worthkind_flow.hotel_refunds%ROWTYPE; p worthkind_flow.hotel_payment_intents%ROWTYPE;
BEGIN
 SELECT x.* INTO r FROM worthkind_flow.hotel_refunds x JOIN worthkind_flow.properties h ON h.id=x.property_id WHERE x.id=p_refund AND h.slug=p_slug FOR UPDATE OF x;
 IF NOT FOUND THEN RAISE EXCEPTION 'Refund unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO p FROM worthkind_flow.hotel_payment_intents WHERE id=r.payment_id AND property_id=r.property_id FOR UPDATE;
 IF r.state='processed' THEN RETURN 'processed'; END IF;
 IF r.state NOT IN ('submitting','unknown','pending','processing','needs-attention','failed') THEN RAISE EXCEPTION 'Refund not submitted' USING ERRCODE='23514'; END IF;
 IF p_state NOT IN ('pending','processing','processed','failed','needs-attention') OR p_provider_id IS NULL OR p_provider_id<=0 OR p_provider_id<>trunc(p_provider_id) OR p_provider_id>18446744073709551615 OR p_transaction IS DISTINCT FROM p.provider_transaction_id OR
 p_mode IS DISTINCT FROM p.mode OR p_amount IS DISTINCT FROM r.amount_minor OR p_currency IS DISTINCT FROM p.currency OR
 (r.provider_refund_id IS NOT NULL AND r.provider_refund_id<>p_provider_id) THEN
 INSERT INTO worthkind_flow.finance_exceptions(property_id,payment_id,kind) VALUES(p.property_id,p.id,'refund_unknown') ON CONFLICT DO NOTHING;
 UPDATE worthkind_flow.hotel_refunds SET state='unknown' WHERE id=r.id;
 RETURN 'unknown';
 END IF;
 UPDATE worthkind_flow.hotel_refunds SET state=p_state,provider_refund_id=p_provider_id WHERE id=r.id;
 IF p_state='processed' THEN
 UPDATE worthkind_flow.hotel_payment_intents SET state='refunded' WHERE id=p.id;
 UPDATE worthkind_flow.hotel_invoices SET state=CASE WHEN p.mode='live' THEN 'refunded' ELSE 'test_refunded' END WHERE id=p.invoice_id AND property_id=p.property_id;
 END IF;
 INSERT INTO worthkind_flow.finance_events(property_id,resource_id,action) VALUES(p.property_id,r.id,'refund_'||p_state);
 RETURN p_state;
END $$;

COMMIT;
