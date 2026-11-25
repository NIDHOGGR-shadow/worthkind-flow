BEGIN;
ALTER TABLE worthkind_flow.hotel_invoices DROP CONSTRAINT hotel_invoices_state_check;
ALTER TABLE worthkind_flow.hotel_invoices ADD CONSTRAINT hotel_invoices_state_check CHECK(state IN ('issued','paid','refunded','test_verified','test_refunded','partially_refunded','test_partially_refunded'));
ALTER TABLE worthkind_flow.hotel_refunds ADD COLUMN request_key text;
UPDATE worthkind_flow.hotel_refunds SET request_key='legacy-full-'||payment_id::text;
ALTER TABLE worthkind_flow.hotel_refunds ALTER COLUMN request_key SET NOT NULL;
ALTER TABLE worthkind_flow.hotel_refunds ADD CONSTRAINT wf_refund_request_key_length CHECK(length(request_key) BETWEEN 8 AND 100);
ALTER TABLE worthkind_flow.hotel_refunds ADD CONSTRAINT wf_refund_idempotency UNIQUE(property_id,request_key);
ALTER TABLE worthkind_flow.hotel_refunds DROP CONSTRAINT hotel_refunds_payment_id_key;
CREATE INDEX wf_refunds_payment_state ON worthkind_flow.hotel_refunds(payment_id,state);

CREATE FUNCTION worthkind_flow.request_partial_hotel_refund(p_subject text,p_slug text,p_payment uuid,p_reason text,p_amount bigint,p_key text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; p worthkind_flow.hotel_payment_intents%ROWTYPE; r worthkind_flow.hotel_refunds%ROWTYPE; reserved numeric; v_amount bigint;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO p FROM worthkind_flow.hotel_payment_intents WHERE id=p_payment AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Payment unavailable' USING ERRCODE='P0002'; END IF;
 v_amount:=COALESCE(p_amount,p.amount_minor);
 SELECT * INTO r FROM worthkind_flow.hotel_refunds WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
 IF r.payment_id<>p_payment OR r.reason<>p_reason OR r.amount_minor<>v_amount THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN r.id; END IF;
 IF p.state<>'verified' OR v_amount<=0 OR v_amount>p.amount_minor THEN RAISE EXCEPTION 'Refund unavailable' USING ERRCODE='23514'; END IF;
 -- Unknown/failed provider outcomes remain reserved until independently reconciled.
 SELECT COALESCE(sum(amount_minor),0) INTO reserved FROM worthkind_flow.hotel_refunds WHERE payment_id=p_payment AND property_id=a.property_id AND state<>'declined';
 IF reserved+v_amount>p.amount_minor THEN RAISE EXCEPTION 'Refund exceeds available balance' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.hotel_refunds(property_id,payment_id,amount_minor,reason,requested_by,request_key)
 VALUES(a.property_id,p.id,v_amount,p_reason,a.member_id,p_key) RETURNING * INTO r;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,r.id,'refund_requested');
 RETURN r.id;
END $$;
CREATE OR REPLACE FUNCTION worthkind_flow.request_hotel_refund(p_subject text,p_slug text,p_payment uuid,p_reason text)
RETURNS uuid LANGUAGE sql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT worthkind_flow.request_partial_hotel_refund(p_subject,p_slug,p_payment,p_reason,NULL::bigint,'legacy-full-'||p_payment::text)
$$;
CREATE OR REPLACE FUNCTION worthkind_flow.record_refund_result(p_slug text,p_refund uuid,p_provider_id numeric,p_transaction numeric,p_mode text,p_amount bigint,p_currency text,p_state text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE r worthkind_flow.hotel_refunds%ROWTYPE; p worthkind_flow.hotel_payment_intents%ROWTYPE; v_refunded numeric;
BEGIN
 SELECT x.* INTO r FROM worthkind_flow.hotel_refunds x JOIN worthkind_flow.properties h ON h.id=x.property_id WHERE x.id=p_refund AND h.slug=p_slug FOR UPDATE OF x;
 IF NOT FOUND THEN RAISE EXCEPTION 'Refund unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO p FROM worthkind_flow.hotel_payment_intents WHERE id=r.payment_id AND property_id=r.property_id FOR UPDATE;
 IF r.state='processed' THEN RETURN 'processed'; END IF;
 IF r.state NOT IN ('submitting','unknown','pending','processing','needs-attention','failed') THEN RAISE EXCEPTION 'Refund not submitted' USING ERRCODE='23514'; END IF;
 IF p_state IS NULL OR p_state NOT IN ('pending','processing','processed','failed','needs-attention') OR p_provider_id IS NULL OR p_provider_id<=0 OR p_provider_id<>trunc(p_provider_id) OR p_provider_id>18446744073709551615 OR p_transaction IS DISTINCT FROM p.provider_transaction_id OR
 p_mode IS DISTINCT FROM p.mode OR p_amount IS DISTINCT FROM r.amount_minor OR p_currency IS DISTINCT FROM p.currency OR
 (r.provider_refund_id IS NOT NULL AND r.provider_refund_id<>p_provider_id) THEN
 INSERT INTO worthkind_flow.finance_exceptions(property_id,payment_id,kind) VALUES(p.property_id,p.id,'refund_unknown') ON CONFLICT DO NOTHING;
 UPDATE worthkind_flow.hotel_refunds SET state='unknown' WHERE id=r.id;
 RETURN 'unknown';
 END IF;
 UPDATE worthkind_flow.hotel_refunds SET state=p_state,provider_refund_id=p_provider_id WHERE id=r.id;
 IF p_state='processed' THEN
 SELECT COALESCE(sum(x.amount_minor),0) INTO v_refunded FROM worthkind_flow.hotel_refunds x WHERE x.payment_id=p.id AND x.property_id=p.property_id AND x.state='processed';
 IF v_refunded>p.amount_minor THEN RAISE EXCEPTION 'Refund total exceeds verified payment' USING ERRCODE='23514'; END IF;
 IF v_refunded=p.amount_minor THEN
 UPDATE worthkind_flow.hotel_payment_intents SET state='refunded' WHERE id=p.id;
 UPDATE worthkind_flow.hotel_invoices SET state=CASE WHEN p.mode='live' THEN 'refunded' ELSE 'test_refunded' END WHERE id=p.invoice_id AND property_id=p.property_id;
 ELSE
 UPDATE worthkind_flow.hotel_invoices SET state=CASE WHEN p.mode='live' THEN 'partially_refunded' ELSE 'test_partially_refunded' END WHERE id=p.invoice_id AND property_id=p.property_id;
 END IF;
 END IF;
 INSERT INTO worthkind_flow.finance_events(property_id,resource_id,action) VALUES(p.property_id,r.id,'refund_'||p_state);
 RETURN p_state;
END $$;


REVOKE ALL ON FUNCTION worthkind_flow.request_partial_hotel_refund(text,text,uuid,text,bigint,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.request_partial_hotel_refund(text,text,uuid,text,bigint,text) TO wf_operations;
COMMIT;
