BEGIN;
CREATE ROLE wf_payment_provider NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_payment_provider;
CREATE TABLE worthkind_flow.hotel_payment_accounts(
 property_id uuid PRIMARY KEY REFERENCES worthkind_flow.properties(id),
 account_alias text NOT NULL UNIQUE CHECK(account_alias ~ '^[A-Za-z0-9_-]{3,80}$'),
 mode text NOT NULL CHECK(mode IN ('test','live')),enabled boolean NOT NULL DEFAULT false,
 approval_reference text NOT NULL CHECK(length(btrim(approval_reference)) BETWEEN 8 AND 240)
);
CREATE TABLE worthkind_flow.hotel_invoices(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 dining_order_id uuid NOT NULL UNIQUE,amount_minor bigint NOT NULL CHECK(amount_minor>0),currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
 state text NOT NULL DEFAULT 'issued' CHECK(state IN ('issued','paid','refunded')),
 issued_by uuid NOT NULL,issued_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,property_id),
 FOREIGN KEY(dining_order_id,property_id) REFERENCES worthkind_flow.dining_orders(id,property_id),
 FOREIGN KEY(issued_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.hotel_payment_intents(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,invoice_id uuid NOT NULL UNIQUE,
 reference text NOT NULL UNIQUE,account_alias text NOT NULL,mode text NOT NULL CHECK(mode IN ('test','live')),
 amount_minor bigint NOT NULL CHECK(amount_minor>0),currency text NOT NULL,
 state text NOT NULL DEFAULT 'initializing' CHECK(state IN ('initializing','pending','init_unknown','verified','refunded')),
 checkout_url text,provider_transaction_id numeric(20,0),verified_at timestamptz,
 created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,property_id),UNIQUE(account_alias,mode,provider_transaction_id),
 FOREIGN KEY(invoice_id,property_id) REFERENCES worthkind_flow.hotel_invoices(id,property_id)
);
CREATE TABLE worthkind_flow.finance_exceptions(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,payment_id uuid NOT NULL,
 kind text NOT NULL CHECK(kind IN ('verification_mismatch','initialization_unknown','refund_unknown')),
 state text NOT NULL DEFAULT 'open' CHECK(state IN ('open','reviewed')),
 created_at timestamptz NOT NULL DEFAULT now(),UNIQUE(payment_id,kind),
 FOREIGN KEY(payment_id,property_id) REFERENCES worthkind_flow.hotel_payment_intents(id,property_id)
);
CREATE TABLE worthkind_flow.hotel_refunds(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,payment_id uuid NOT NULL UNIQUE,
 amount_minor bigint NOT NULL CHECK(amount_minor>0),reason text NOT NULL CHECK(length(btrim(reason)) BETWEEN 8 AND 240),
 state text NOT NULL DEFAULT 'requested' CHECK(state IN ('requested','approved','declined','submitting','unknown','pending','processing','processed','failed','needs-attention')),
 requested_by uuid NOT NULL,approved_by uuid,provider_refund_id numeric(20,0),created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(id,property_id),UNIQUE(property_id,provider_refund_id),
 FOREIGN KEY(payment_id,property_id) REFERENCES worthkind_flow.hotel_payment_intents(id,property_id),
 FOREIGN KEY(requested_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(approved_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.finance_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor uuid,resource_id uuid NOT NULL,action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['hotel_payment_accounts','hotel_invoices','hotel_payment_intents','finance_exceptions','hotel_refunds','finance_events'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
CREATE FUNCTION worthkind_flow.configure_hotel_payments(p_slug text,p_alias text,p_mode text,p_approval text,p_enabled boolean)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'Hotel unavailable' USING ERRCODE='P0002'; END IF;
 IF EXISTS(SELECT 1 FROM worthkind_flow.hotel_payment_intents WHERE property_id=v_property) AND EXISTS(
 SELECT 1 FROM worthkind_flow.hotel_payment_accounts WHERE property_id=v_property AND (account_alias<>p_alias OR mode<>p_mode)) THEN
 RAISE EXCEPTION 'Existing account has payment history' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.hotel_payment_accounts(property_id,account_alias,mode,approval_reference,enabled)
 VALUES(v_property,p_alias,p_mode,p_approval,p_enabled)
 ON CONFLICT(property_id) DO UPDATE SET account_alias=EXCLUDED.account_alias,mode=EXCLUDED.mode,approval_reference=EXCLUDED.approval_reference,enabled=EXCLUDED.enabled;
 INSERT INTO worthkind_flow.finance_events(property_id,resource_id,action) VALUES(v_property,v_property,'account_configured');
 RETURN v_property;
END $$;
CREATE FUNCTION worthkind_flow.issue_dining_invoice(p_subject text,p_slug text,p_order uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; o worthkind_flow.dining_orders%ROWTYPE; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO o FROM worthkind_flow.dining_orders WHERE id=p_order AND property_id=a.property_id AND state='served' AND total_minor>0 FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Billable order unavailable' USING ERRCODE='P0002'; END IF;
 SELECT id INTO v_id FROM worthkind_flow.hotel_invoices WHERE dining_order_id=p_order AND property_id=a.property_id;
 IF FOUND THEN RETURN v_id; END IF;
 INSERT INTO worthkind_flow.hotel_invoices(property_id,dining_order_id,amount_minor,currency,issued_by)
 VALUES(a.property_id,o.id,o.total_minor,o.currency,a.member_id) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'invoice_issued');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.begin_hotel_payment(p_subject text,p_slug text,p_invoice uuid)
RETURNS TABLE(payment_id uuid,reference text,account_alias text,mode text,amount_minor bigint,currency text,state text,checkout_url text,submit boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; inv worthkind_flow.hotel_invoices%ROWTYPE; cfg worthkind_flow.hotel_payment_accounts%ROWTYPE; p worthkind_flow.hotel_payment_intents%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO inv FROM worthkind_flow.hotel_invoices i WHERE i.id=p_invoice AND i.property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Invoice unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO p FROM worthkind_flow.hotel_payment_intents x WHERE x.invoice_id=p_invoice AND x.property_id=a.property_id;
 IF FOUND THEN RETURN QUERY SELECT p.id,p.reference,p.account_alias,p.mode,p.amount_minor,p.currency,p.state,p.checkout_url,false; RETURN; END IF;
 SELECT * INTO cfg FROM worthkind_flow.hotel_payment_accounts x WHERE x.property_id=a.property_id AND x.enabled;
 IF NOT FOUND OR inv.state<>'issued' THEN RAISE EXCEPTION 'Payment unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.hotel_payment_intents(property_id,invoice_id,reference,account_alias,mode,amount_minor,currency)
 VALUES(a.property_id,p_invoice,'wf-'||gen_random_uuid()::text,cfg.account_alias,cfg.mode,inv.amount_minor,inv.currency) RETURNING * INTO p;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,p.id,'payment_initializing');
 RETURN QUERY SELECT p.id,p.reference,p.account_alias,p.mode,p.amount_minor,p.currency,p.state,p.checkout_url,true;
END $$;
CREATE FUNCTION worthkind_flow.payment_checkout_result(p_slug text,p_reference text,p_url text,p_success boolean)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE p worthkind_flow.hotel_payment_intents%ROWTYPE; v_state text;
BEGIN
 SELECT x.* INTO p FROM worthkind_flow.hotel_payment_intents x JOIN worthkind_flow.properties h ON h.id=x.property_id
 WHERE h.slug=p_slug AND x.reference=p_reference FOR UPDATE OF x;
 IF NOT FOUND THEN RAISE EXCEPTION 'Payment unavailable' USING ERRCODE='P0002'; END IF;
 IF p.state<>'initializing' THEN RETURN p.state; END IF;
 IF p_success AND p_url LIKE 'https://checkout.paystack.com/%' THEN v_state='pending';
 ELSE v_state='init_unknown'; p_url=NULL; END IF;
 UPDATE worthkind_flow.hotel_payment_intents SET state=v_state,checkout_url=p_url WHERE id=p.id;
 IF v_state='init_unknown' THEN INSERT INTO worthkind_flow.finance_exceptions(property_id,payment_id,kind) VALUES(p.property_id,p.id,'initialization_unknown') ON CONFLICT DO NOTHING; END IF;
 INSERT INTO worthkind_flow.finance_events(property_id,resource_id,action) VALUES(p.property_id,p.id,v_state);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.provider_payment_lookup(p_slug text,p_reference text)
RETURNS TABLE(account_alias text,mode text,amount_minor bigint,currency text,state text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT x.account_alias,x.mode,x.amount_minor,x.currency,x.state FROM worthkind_flow.hotel_payment_intents x
 JOIN worthkind_flow.properties p ON p.id=x.property_id WHERE p.slug=p_slug AND x.reference=p_reference
$$;
CREATE FUNCTION worthkind_flow.record_verified_payment(p_slug text,p_reference text,p_alias text,p_mode text,p_transaction numeric,p_amount bigint,p_currency text)
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
 UPDATE worthkind_flow.hotel_invoices SET state='paid' WHERE id=p.invoice_id AND property_id=p.property_id;
 INSERT INTO worthkind_flow.finance_events(property_id,resource_id,action) VALUES(p.property_id,p.id,'payment_verified');
 RETURN 'verified';
END $$;
CREATE FUNCTION worthkind_flow.request_hotel_refund(p_subject text,p_slug text,p_payment uuid,p_reason text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; p worthkind_flow.hotel_payment_intents%ROWTYPE; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO p FROM worthkind_flow.hotel_payment_intents WHERE id=p_payment AND property_id=a.property_id AND state='verified' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Payment unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.hotel_refunds(property_id,payment_id,amount_minor,reason,requested_by)
 VALUES(a.property_id,p.id,p.amount_minor,p_reason,a.member_id) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'refund_requested');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.decide_hotel_refund(p_subject text,p_slug text,p_refund uuid,p_action text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action NOT IN ('approve','decline') THEN RAISE EXCEPTION 'Invalid decision' USING ERRCODE='22023'; END IF;
 UPDATE worthkind_flow.hotel_refunds r SET state=CASE p_action WHEN 'approve' THEN 'approved' ELSE 'declined' END,approved_by=a.member_id
 WHERE r.id=p_refund AND r.property_id=a.property_id AND r.state='requested' AND r.requested_by<>a.member_id RETURNING state INTO v_state;
 IF NOT FOUND THEN RAISE EXCEPTION 'Refund unavailable or separate approver required' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,p_refund,'refund_'||v_state);
 RETURN v_state;
END $$;
CREATE FUNCTION worthkind_flow.begin_refund_submission(p_subject text,p_slug text,p_refund uuid)
RETURNS TABLE(reference text,account_alias text,mode text,amount_minor bigint,currency text,provider_transaction_id numeric)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; r worthkind_flow.hotel_refunds%ROWTYPE; p worthkind_flow.hotel_payment_intents%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO r FROM worthkind_flow.hotel_refunds x WHERE x.id=p_refund AND x.property_id=a.property_id AND x.state='approved' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Refund unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO p FROM worthkind_flow.hotel_payment_intents x WHERE x.id=r.payment_id AND x.property_id=a.property_id AND x.state='verified';
 IF NOT FOUND THEN RAISE EXCEPTION 'Payment unavailable' USING ERRCODE='P0002'; END IF;
 UPDATE worthkind_flow.hotel_refunds SET state='submitting' WHERE id=r.id;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,r.id,'refund_submitting');
 RETURN QUERY SELECT p.reference,p.account_alias,p.mode,r.amount_minor,p.currency,p.provider_transaction_id;
END $$;
CREATE FUNCTION worthkind_flow.record_refund_result(p_slug text,p_refund uuid,p_provider_id numeric,p_transaction numeric,p_mode text,p_amount bigint,p_currency text,p_state text)
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
 UPDATE worthkind_flow.hotel_invoices SET state='refunded' WHERE id=p.invoice_id AND property_id=p.property_id;
 END IF;
 INSERT INTO worthkind_flow.finance_events(property_id,resource_id,action) VALUES(p.property_id,r.id,'refund_'||p_state);
 RETURN p_state;
END $$;
CREATE FUNCTION worthkind_flow.finance_overview(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN jsonb_build_object(
 'invoices',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,dining_order_id,amount_minor,currency,state,issued_at FROM worthkind_flow.hotel_invoices WHERE property_id=a.property_id ORDER BY issued_at DESC LIMIT 200)x),'[]'::jsonb),
 'payments',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,invoice_id,reference,mode,amount_minor,currency,state,verified_at FROM worthkind_flow.hotel_payment_intents WHERE property_id=a.property_id ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb),
 'refunds',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,payment_id,amount_minor,reason,state,provider_refund_id,created_at FROM worthkind_flow.hotel_refunds WHERE property_id=a.property_id ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb),
 'exceptions',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,payment_id,kind,state,created_at FROM worthkind_flow.finance_exceptions WHERE property_id=a.property_id ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb));
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.configure_hotel_payments(text,text,text,text,boolean),worthkind_flow.issue_dining_invoice(text,text,uuid),
 worthkind_flow.begin_hotel_payment(text,text,uuid),worthkind_flow.payment_checkout_result(text,text,text,boolean),
 worthkind_flow.provider_payment_lookup(text,text),worthkind_flow.record_verified_payment(text,text,text,text,numeric,bigint,text),
 worthkind_flow.request_hotel_refund(text,text,uuid,text),worthkind_flow.decide_hotel_refund(text,text,uuid,text),
 worthkind_flow.begin_refund_submission(text,text,uuid),worthkind_flow.record_refund_result(text,uuid,numeric,numeric,text,bigint,text,text),
 worthkind_flow.finance_overview(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.configure_hotel_payments(text,text,text,text,boolean) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.issue_dining_invoice(text,text,uuid),worthkind_flow.begin_hotel_payment(text,text,uuid),
 worthkind_flow.request_hotel_refund(text,text,uuid,text),worthkind_flow.decide_hotel_refund(text,text,uuid,text),
 worthkind_flow.begin_refund_submission(text,text,uuid),worthkind_flow.finance_overview(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.payment_checkout_result(text,text,text,boolean),worthkind_flow.provider_payment_lookup(text,text),
 worthkind_flow.record_verified_payment(text,text,text,text,numeric,bigint,text),
 worthkind_flow.record_refund_result(text,uuid,numeric,numeric,text,bigint,text,text) TO wf_payment_provider;

CREATE FUNCTION worthkind_flow.staff_payment_lookup(p_subject text,p_slug text,p_payment uuid)
RETURNS TABLE(reference text,account_alias text,mode text,amount_minor bigint,currency text,state text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT x.reference,x.account_alias,x.mode,x.amount_minor,x.currency,x.state FROM worthkind_flow.hotel_payment_intents x
 WHERE x.id=p_payment AND x.property_id=a.property_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Payment unavailable' USING ERRCODE='P0002'; END IF;
END $$;
CREATE FUNCTION worthkind_flow.staff_refund_lookup(p_subject text,p_slug text,p_refund uuid)
RETURNS TABLE(account_alias text,mode text,provider_refund_id numeric,provider_transaction_id numeric,amount_minor bigint,currency text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT p.account_alias,p.mode,r.provider_refund_id,p.provider_transaction_id,r.amount_minor,p.currency
 FROM worthkind_flow.hotel_refunds r JOIN worthkind_flow.hotel_payment_intents p ON p.id=r.payment_id AND p.property_id=r.property_id
 WHERE r.id=p_refund AND r.property_id=a.property_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Refund unavailable' USING ERRCODE='P0002'; END IF;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.staff_payment_lookup(text,text,uuid),worthkind_flow.staff_refund_lookup(text,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.staff_payment_lookup(text,text,uuid),worthkind_flow.staff_refund_lookup(text,text,uuid) TO wf_operations;

COMMIT;
