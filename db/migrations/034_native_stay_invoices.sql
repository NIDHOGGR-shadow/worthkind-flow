BEGIN;
ALTER TABLE worthkind_flow.hotel_invoices ALTER COLUMN dining_order_id DROP NOT NULL;
ALTER TABLE worthkind_flow.hotel_invoices ADD COLUMN native_booking_id uuid UNIQUE;
ALTER TABLE worthkind_flow.hotel_invoices ADD FOREIGN KEY(native_booking_id,property_id) REFERENCES worthkind_flow.native_bookings(id,property_id);
ALTER TABLE worthkind_flow.hotel_invoices ADD CONSTRAINT wf_invoice_one_source CHECK((dining_order_id IS NULL)<>(native_booking_id IS NULL));
ALTER TABLE worthkind_flow.hotel_invoices DROP CONSTRAINT hotel_invoices_state_check;
ALTER TABLE worthkind_flow.hotel_invoices ADD CONSTRAINT hotel_invoices_state_check CHECK(state IN ('issued','paid','refunded','test_verified','test_refunded','partially_refunded','test_partially_refunded','voided'));

CREATE FUNCTION worthkind_flow.issue_native_stay_invoice(p_subject text,p_slug text,p_booking uuid)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; b worthkind_flow.native_bookings%ROWTYPE; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO b FROM worthkind_flow.native_bookings WHERE id=p_booking AND property_id=a.property_id AND state='confirmed' FOR UPDATE;
 IF NOT FOUND OR b.arrival>(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=a.property_id) THEN RAISE EXCEPTION 'Stay not billable yet' USING ERRCODE='P0002'; END IF;
 SELECT id INTO v_id FROM worthkind_flow.hotel_invoices WHERE native_booking_id=p_booking AND property_id=a.property_id;
 IF FOUND THEN RETURN v_id; END IF;
 INSERT INTO worthkind_flow.hotel_invoices(property_id,native_booking_id,amount_minor,currency,issued_by)
 VALUES(a.property_id,b.id,b.total_minor,b.currency,a.member_id) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'stay_invoice_issued');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.void_unpaid_invoice(p_subject text,p_slug text,p_invoice uuid,p_reason text)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; i worthkind_flow.hotel_invoices%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF length(btrim(p_reason)) NOT BETWEEN 8 AND 240 THEN RAISE EXCEPTION 'Reason required' USING ERRCODE='22023'; END IF;
 SELECT * INTO i FROM worthkind_flow.hotel_invoices WHERE id=p_invoice AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Invoice unavailable' USING ERRCODE='P0002'; END IF;
 IF i.state='voided' THEN RETURN 'voided'; END IF;
 IF i.state<>'issued' OR EXISTS(SELECT 1 FROM worthkind_flow.hotel_payment_intents WHERE invoice_id=i.id AND property_id=a.property_id) THEN
 RAISE EXCEPTION 'Invoice requires payment reconciliation before adjustment' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.hotel_invoices SET state='voided' WHERE id=i.id;
 INSERT INTO worthkind_flow.finance_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,i.id,'invoice_voided');
 RETURN 'voided';
END $$;
CREATE FUNCTION worthkind_flow.guard_invoiced_booking()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF (NEW.state IS DISTINCT FROM OLD.state OR NEW.total_minor IS DISTINCT FROM OLD.total_minor OR NEW.arrival IS DISTINCT FROM OLD.arrival OR NEW.departure IS DISTINCT FROM OLD.departure)
 AND EXISTS(SELECT 1 FROM worthkind_flow.hotel_invoices i WHERE i.property_id=OLD.property_id AND i.native_booking_id=OLD.id AND i.state NOT IN ('voided','refunded')) THEN
 RAISE EXCEPTION 'Resolve stay invoice before changing booking' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_invoiced_booking_guard BEFORE UPDATE ON worthkind_flow.native_bookings FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_invoiced_booking();
CREATE OR REPLACE FUNCTION worthkind_flow.finance_overview(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN jsonb_build_object(
 'invoices',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,dining_order_id,native_booking_id,amount_minor,currency,state,issued_at FROM worthkind_flow.hotel_invoices WHERE property_id=a.property_id ORDER BY issued_at DESC LIMIT 200)x),'[]'::jsonb),
 'payments',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,invoice_id,reference,mode,amount_minor,currency,state,verified_at FROM worthkind_flow.hotel_payment_intents WHERE property_id=a.property_id ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb),
 'refunds',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,payment_id,amount_minor,reason,state,provider_refund_id,created_at,request_key FROM worthkind_flow.hotel_refunds WHERE property_id=a.property_id ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb),
 'exceptions',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT id,payment_id,kind,state,created_at FROM worthkind_flow.finance_exceptions WHERE property_id=a.property_id ORDER BY created_at DESC LIMIT 200)x),'[]'::jsonb));
END $$;

REVOKE ALL ON FUNCTION worthkind_flow.issue_native_stay_invoice(text,text,uuid),worthkind_flow.void_unpaid_invoice(text,text,uuid,text),worthkind_flow.guard_invoiced_booking() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.issue_native_stay_invoice(text,text,uuid),worthkind_flow.void_unpaid_invoice(text,text,uuid,text) TO wf_operations;
COMMIT;
