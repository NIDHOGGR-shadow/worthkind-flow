BEGIN;
CREATE ROLE wf_pos_provider NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_pos_provider;
CREATE TABLE worthkind_flow.pos_accounts(
 property_id uuid PRIMARY KEY REFERENCES worthkind_flow.properties(id),
 provider text NOT NULL CHECK(provider='loyverse'),store_id text NOT NULL UNIQUE CHECK(length(btrim(store_id)) BETWEEN 1 AND 100),
 account_alias text NOT NULL UNIQUE CHECK(account_alias ~ '^[A-Za-z0-9_-]{3,80}$'),
 currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),minor_digits integer NOT NULL CHECK(minor_digits BETWEEN 0 AND 3),
 approval_reference text NOT NULL CHECK(length(btrim(approval_reference)) BETWEEN 8 AND 240),enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE worthkind_flow.pos_receipt_evidence(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,order_id uuid NOT NULL UNIQUE,
 account_alias text NOT NULL,store_id text NOT NULL,receipt_number text NOT NULL,
 amount_minor bigint NOT NULL CHECK(amount_minor>=0),currency text NOT NULL,
 receipt_type text NOT NULL CHECK(receipt_type IN ('SALE','REFUND')),provider_created_at timestamptz NOT NULL,
 provider_updated_at timestamptz NOT NULL,matched boolean NOT NULL,
 recorded_at timestamptz NOT NULL DEFAULT now(),UNIQUE(account_alias,receipt_number),UNIQUE(id,property_id),
 FOREIGN KEY(order_id,property_id) REFERENCES worthkind_flow.dining_orders(id,property_id)
);
CREATE TABLE worthkind_flow.pos_receipt_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,evidence_id uuid NOT NULL,
 actor uuid NOT NULL,action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(evidence_id,property_id) REFERENCES worthkind_flow.pos_receipt_evidence(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['pos_accounts','pos_receipt_evidence','pos_receipt_events'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
CREATE FUNCTION worthkind_flow.configure_loyverse(p_slug text,p_store text,p_alias text,p_currency text,p_digits integer,p_approval text,p_enabled boolean)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'Hotel unavailable' USING ERRCODE='P0002'; END IF;
 IF EXISTS(SELECT 1 FROM worthkind_flow.pos_receipt_evidence WHERE property_id=v_property) AND EXISTS(
 SELECT 1 FROM worthkind_flow.pos_accounts WHERE property_id=v_property AND (store_id<>p_store OR account_alias<>p_alias OR currency<>p_currency OR minor_digits<>p_digits)) THEN
 RAISE EXCEPTION 'Account has existing receipt evidence' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.pos_accounts(property_id,provider,store_id,account_alias,currency,minor_digits,approval_reference,enabled)
 VALUES(v_property,'loyverse',p_store,p_alias,p_currency,p_digits,p_approval,p_enabled)
 ON CONFLICT(property_id) DO UPDATE SET store_id=EXCLUDED.store_id,account_alias=EXCLUDED.account_alias,currency=EXCLUDED.currency,
 minor_digits=EXCLUDED.minor_digits,approval_reference=EXCLUDED.approval_reference,enabled=EXCLUDED.enabled;
 RETURN v_property;
END $$;
CREATE FUNCTION worthkind_flow.staff_pos_account(p_subject text,p_slug text,p_order uuid)
RETURNS TABLE(store_id text,account_alias text,currency text,minor_digits integer)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.dining_orders WHERE property_id=a.property_id AND id=p_order AND state='served') THEN RAISE EXCEPTION 'Order unavailable' USING ERRCODE='P0002'; END IF;
 RETURN QUERY SELECT p.store_id,p.account_alias,p.currency,p.minor_digits FROM worthkind_flow.pos_accounts p WHERE p.property_id=a.property_id AND p.enabled;
 IF NOT FOUND THEN RAISE EXCEPTION 'POS unavailable' USING ERRCODE='P0002'; END IF;
END $$;
CREATE FUNCTION worthkind_flow.record_pos_receipt(p_subject text,p_slug text,p_order uuid,p_alias text,p_store text,p_receipt text,p_minor bigint,p_currency text,p_type text,p_created timestamptz,p_updated timestamptz)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; cfg worthkind_flow.pos_accounts%ROWTYPE; d worthkind_flow.dining_orders%ROWTYPE; e worthkind_flow.pos_receipt_evidence%ROWTYPE; v_match boolean;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO cfg FROM worthkind_flow.pos_accounts WHERE property_id=a.property_id AND enabled;
 IF NOT FOUND OR cfg.account_alias IS DISTINCT FROM p_alias OR cfg.store_id IS DISTINCT FROM p_store OR cfg.currency IS DISTINCT FROM p_currency THEN RAISE EXCEPTION 'POS account mismatch' USING ERRCODE='42501'; END IF;
 SELECT * INTO d FROM worthkind_flow.dining_orders WHERE property_id=a.property_id AND id=p_order AND state='served' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Order unavailable' USING ERRCODE='P0002'; END IF;
 IF p_receipt IS NULL OR length(p_receipt) NOT BETWEEN 1 AND 100 OR p_created IS NULL OR p_updated IS NULL OR p_updated<p_created THEN RAISE EXCEPTION 'Invalid receipt evidence' USING ERRCODE='22023'; END IF;
 v_match:=p_type='SALE' AND d.currency=p_currency AND d.total_minor=p_minor AND p_created>=d.created_at-interval '5 minutes';
 SELECT * INTO e FROM worthkind_flow.pos_receipt_evidence WHERE order_id=d.id AND property_id=a.property_id;
 IF FOUND THEN
 IF e.account_alias<>p_alias OR e.receipt_number<>p_receipt THEN RAISE EXCEPTION 'Receipt already assigned; manual investigation required' USING ERRCODE='23505'; END IF;
 IF e.provider_updated_at>p_updated THEN RETURN to_jsonb(e)-'property_id'; END IF;
 UPDATE worthkind_flow.pos_receipt_evidence SET amount_minor=p_minor,receipt_type=p_type,provider_updated_at=p_updated,
 matched=v_match,recorded_at=now() WHERE id=e.id RETURNING * INTO e;
 ELSE
 INSERT INTO worthkind_flow.pos_receipt_evidence(property_id,order_id,account_alias,store_id,receipt_number,amount_minor,currency,receipt_type,provider_created_at,provider_updated_at,matched)
 VALUES(a.property_id,d.id,p_alias,p_store,p_receipt,p_minor,p_currency,p_type,p_created,p_updated,v_match) RETURNING * INTO e;
 END IF;
 INSERT INTO worthkind_flow.pos_receipt_events(property_id,evidence_id,actor,action) VALUES(a.property_id,e.id,a.member_id,CASE WHEN v_match THEN 'amount_matched' ELSE 'mismatch' END);
 RETURN to_jsonb(e)-'property_id';
END $$;
CREATE FUNCTION worthkind_flow.pos_reconciliation(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT e.id,e.order_id,e.receipt_number,e.amount_minor,e.currency,e.receipt_type,e.matched,e.provider_updated_at,e.recorded_at,d.total_minor AS order_total_minor,
 CASE WHEN i.state='paid' THEN true ELSE false END AS paystack_paid
 FROM worthkind_flow.pos_receipt_evidence e JOIN worthkind_flow.dining_orders d ON d.id=e.order_id AND d.property_id=e.property_id
 LEFT JOIN worthkind_flow.hotel_invoices i ON i.dining_order_id=d.id AND i.property_id=d.property_id
 WHERE e.property_id=a.property_id ORDER BY e.recorded_at DESC LIMIT 200)x),'[]'::jsonb);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.configure_loyverse(text,text,text,text,integer,text,boolean),worthkind_flow.staff_pos_account(text,text,uuid),
 worthkind_flow.record_pos_receipt(text,text,uuid,text,text,text,bigint,text,text,timestamptz,timestamptz),worthkind_flow.pos_reconciliation(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.configure_loyverse(text,text,text,text,integer,text,boolean) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.staff_pos_account(text,text,uuid),worthkind_flow.pos_reconciliation(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.record_pos_receipt(text,text,uuid,text,text,text,bigint,text,text,timestamptz,timestamptz) TO wf_pos_provider;
COMMIT;
