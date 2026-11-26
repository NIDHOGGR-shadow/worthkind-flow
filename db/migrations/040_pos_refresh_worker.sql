BEGIN;
CREATE ROLE wf_pos_sync NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_pos_sync;
ALTER TABLE worthkind_flow.pos_receipt_evidence ADD COLUMN next_sync_at timestamptz NOT NULL DEFAULT now();
ALTER TABLE worthkind_flow.pos_receipt_evidence ADD COLUMN sync_lease uuid;
ALTER TABLE worthkind_flow.pos_receipt_evidence ADD COLUMN sync_lease_until timestamptz;
ALTER TABLE worthkind_flow.pos_receipt_evidence ADD COLUMN sync_failures integer NOT NULL DEFAULT 0;
ALTER TABLE worthkind_flow.pos_receipt_evidence ADD COLUMN cancelled_at timestamptz;
CREATE TABLE worthkind_flow.pos_sync_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,evidence_id uuid NOT NULL,
 outcome text NOT NULL CHECK(outcome IN ('refreshed','failed','cancelled','stale')),
 created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(evidence_id,property_id) REFERENCES worthkind_flow.pos_receipt_evidence(id,property_id)
);
ALTER TABLE worthkind_flow.pos_sync_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.pos_sync_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.pos_sync_events FROM PUBLIC;
CREATE FUNCTION worthkind_flow.lease_pos_refresh(p_limit integer)
RETURNS TABLE(id uuid,lease uuid,slug text,store_id text,account_alias text,currency text,minor_digits integer,receipt_number text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF p_limit NOT BETWEEN 1 AND 20 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY WITH picked AS (
 SELECT e.id FROM worthkind_flow.pos_receipt_evidence e JOIN worthkind_flow.pos_accounts a ON a.property_id=e.property_id AND a.enabled AND a.account_alias=e.account_alias
 JOIN worthkind_flow.properties p ON p.id=e.property_id AND p.status='active'
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id AND o.status='verified'
 WHERE e.next_sync_at<=now() AND (e.sync_lease_until IS NULL OR e.sync_lease_until<=now())
 ORDER BY e.next_sync_at,e.id LIMIT p_limit FOR UPDATE OF e SKIP LOCKED
 ), leased AS (
 UPDATE worthkind_flow.pos_receipt_evidence e SET sync_lease=gen_random_uuid(),sync_lease_until=now()+interval '3 minutes'
 FROM picked x WHERE e.id=x.id RETURNING e.*
 )
 SELECT e.id,e.sync_lease,p.slug,e.store_id,e.account_alias,e.currency,a.minor_digits,e.receipt_number FROM leased e
 JOIN worthkind_flow.properties p ON p.id=e.property_id JOIN worthkind_flow.pos_accounts a ON a.property_id=e.property_id;
END $$;
CREATE FUNCTION worthkind_flow.complete_pos_refresh(p_id uuid,p_lease uuid,p_alias text,p_store text,p_receipt text,p_amount bigint,p_type text,p_created timestamptz,p_updated timestamptz,p_cancelled timestamptz,p_ok boolean)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE e worthkind_flow.pos_receipt_evidence%ROWTYPE; d worthkind_flow.dining_orders%ROWTYPE; v_outcome text;
BEGIN
 SELECT * INTO e FROM worthkind_flow.pos_receipt_evidence WHERE id=p_id AND sync_lease=p_lease AND sync_lease_until>now() FOR UPDATE;
 IF NOT FOUND THEN RETURN false; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.pos_accounts a JOIN worthkind_flow.properties h ON h.id=a.property_id AND h.status='active'
 JOIN worthkind_flow.organizations o ON o.id=h.organization_id AND o.status='verified' WHERE a.property_id=e.property_id AND a.enabled AND a.account_alias=e.account_alias AND a.store_id=e.store_id) THEN
 UPDATE worthkind_flow.pos_receipt_evidence SET sync_lease=NULL,sync_lease_until=NULL,next_sync_at=now()+interval '1 hour' WHERE id=e.id;
 RETURN false; END IF;
 IF p_ok IS DISTINCT FROM true OR p_alias IS DISTINCT FROM e.account_alias OR p_store IS DISTINCT FROM e.store_id OR p_receipt IS DISTINCT FROM e.receipt_number OR p_amount IS NULL OR p_amount<0 OR p_type NOT IN ('SALE','REFUND') OR p_created IS DISTINCT FROM e.provider_created_at OR p_updated IS NULL OR p_updated<p_created THEN
 UPDATE worthkind_flow.pos_receipt_evidence SET sync_failures=LEAST(sync_failures+1,20),sync_lease=NULL,sync_lease_until=NULL,
 next_sync_at=now()+make_interval(mins=>LEAST(360,5*(1+sync_failures))) WHERE id=e.id;
 v_outcome='failed';
 ELSIF p_updated<e.provider_updated_at THEN
 UPDATE worthkind_flow.pos_receipt_evidence SET sync_lease=NULL,sync_lease_until=NULL,next_sync_at=now()+interval '30 minutes' WHERE id=e.id;
 v_outcome='stale';
 ELSE
 SELECT * INTO d FROM worthkind_flow.dining_orders WHERE id=e.order_id AND property_id=e.property_id;
 UPDATE worthkind_flow.pos_receipt_evidence SET amount_minor=p_amount,receipt_type=p_type,provider_updated_at=p_updated,
 cancelled_at=COALESCE(p_cancelled,e.cancelled_at),matched=(p_type='SALE' AND p_cancelled IS NULL AND e.cancelled_at IS NULL AND d.currency=e.currency AND d.total_minor=p_amount AND p_created>=d.created_at-interval '5 minutes'),
 recorded_at=now(),next_sync_at=now()+interval '30 minutes',sync_failures=0,sync_lease=NULL,sync_lease_until=NULL WHERE id=e.id;
 v_outcome=CASE WHEN p_cancelled IS NOT NULL OR e.cancelled_at IS NOT NULL THEN 'cancelled' ELSE 'refreshed' END;
 END IF;
 INSERT INTO worthkind_flow.pos_sync_events(property_id,evidence_id,outcome) VALUES(e.property_id,e.id,v_outcome);
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.lease_pos_refresh(integer),worthkind_flow.complete_pos_refresh(uuid,uuid,text,text,text,bigint,text,timestamptz,timestamptz,timestamptz,boolean) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.lease_pos_refresh(integer),worthkind_flow.complete_pos_refresh(uuid,uuid,text,text,text,bigint,text,timestamptz,timestamptz,timestamptz,boolean) TO wf_pos_sync;
COMMIT;
