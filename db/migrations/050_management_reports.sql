BEGIN;
-- Current recorded operational state only; not a forecast, accounting ledger or PMS occupancy.
CREATE FUNCTION worthkind_flow.management_snapshot(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; result jsonb;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT jsonb_build_object(
 'as_of',statement_timestamp(),
 'scope','native_property_records',
 'cases',(SELECT jsonb_build_object('open',count(*) FILTER(WHERE state IN ('queued','claimed','responded','escalated','disputed')),
 'queued',count(*) FILTER(WHERE state='queued'),'escalated',count(*) FILTER(WHERE state='escalated'),
 'staff_resolved',count(*) FILTER(WHERE state='resolved')) FROM worthkind_flow.guest_cases WHERE property_id=a.property_id),
 'tickets',(SELECT jsonb_build_object('open',count(*) FILTER(WHERE status<>'resolved'),
 'overdue',count(*) FILTER(WHERE status<>'resolved' AND due_at<statement_timestamp()),
 'urgent_open',count(*) FILTER(WHERE status<>'resolved' AND priority='urgent')) FROM worthkind_flow.service_tickets WHERE property_id=a.property_id),
 'rooms',(SELECT jsonb_build_object('registered',count(*),'out_of_service',count(*) FILTER(WHERE operational_state='out_of_service'),
 'dirty',count(*) FILTER(WHERE operational_state='dirty'),'native_occupied',(SELECT count(*) FROM worthkind_flow.occupied_rooms WHERE property_id=a.property_id))
 FROM worthkind_flow.hotel_rooms WHERE property_id=a.property_id),
 'bookings',(SELECT jsonb_build_object('unexpired_holds',count(*) FILTER(WHERE state='held' AND expires_at>statement_timestamp()),
 'confirmed',count(*) FILTER(WHERE state='confirmed')) FROM worthkind_flow.native_bookings WHERE property_id=a.property_id),
 'dining',(SELECT jsonb_build_object('awaiting_acceptance',count(*) FILTER(WHERE state='submitted'),
 'in_service',count(*) FILTER(WHERE state IN ('accepted','preparing','ready'))) FROM worthkind_flow.dining_orders WHERE property_id=a.property_id),
 'stock',(SELECT jsonb_build_object('active_items',count(*) FILTER(WHERE active),
 'at_or_below_reorder',count(*) FILTER(WHERE active AND balance<=reorder_level)) FROM worthkind_flow.stock_items WHERE property_id=a.property_id),
 'handover_pending',(SELECT count(*) FROM worthkind_flow.reception_handovers WHERE property_id=a.property_id AND state='pending'),
 'venue_requests_pending',(SELECT count(*) FROM worthkind_flow.venue_requests WHERE property_id=a.property_id AND state IN ('requested','reviewed')),
 'notification_outbox',(SELECT jsonb_build_object('pending',count(*) FILTER(WHERE event_state='pending'),
 'failed',count(*) FILTER(WHERE event_state='failed'),'dead_letter',count(*) FILTER(WHERE event_state='dead_letter')) FROM worthkind_flow.event_outbox WHERE property_id=a.property_id)
 ) INTO result;
 RETURN result;
END $$;
-- Cumulative provider-verified evidence; amounts are strings in minor units to preserve integer precision.
-- Processed refunds are joined once per payment. No fees, bank settlement or revenue inference.
CREATE FUNCTION worthkind_flow.payment_evidence_summary(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; result jsonb;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 WITH verified AS (
 SELECT p.mode,p.currency,p.amount_minor,
 COALESCE((SELECT sum(r.amount_minor) FROM worthkind_flow.hotel_refunds r
 WHERE r.property_id=p.property_id AND r.payment_id=p.id AND r.state='processed' AND r.provider_refund_id IS NOT NULL),0) AS refunded
 FROM worthkind_flow.hotel_payment_intents p WHERE p.property_id=a.property_id AND p.state IN ('verified','refunded')
 AND p.verified_at IS NOT NULL AND p.provider_transaction_id IS NOT NULL
 ), grouped AS (
 SELECT mode,currency,count(*) AS payment_count,sum(amount_minor) AS gross,sum(refunded) AS refunds FROM verified GROUP BY mode,currency
 )
 SELECT jsonb_build_object('as_of',statement_timestamp(),'scope','cumulative_verified_provider_evidence',
 'settlement_verified',false,'groups',COALESCE((SELECT jsonb_agg(jsonb_build_object(
 'mode',mode,'currency',currency,'payment_count',payment_count,'verified_gross_minor',gross::text,
 'processed_refunds_minor',refunds::text,'net_after_refunds_minor',(gross-refunds)::text) ORDER BY mode,currency) FROM grouped),'[]'::jsonb),
 'open_exceptions',(SELECT count(*) FROM worthkind_flow.finance_exceptions WHERE property_id=a.property_id AND state='open'))
 INTO result;
 RETURN result;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.management_snapshot(text,text),worthkind_flow.payment_evidence_summary(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.management_snapshot(text,text),worthkind_flow.payment_evidence_summary(text,text) TO wf_operations;
COMMIT;
