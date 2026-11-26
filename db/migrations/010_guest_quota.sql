-- Bounded distributed guest request quota; stored per property and HMAC bucket.
BEGIN;
CREATE ROLE wf_guest_quota NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_guest_quota;
CREATE TABLE worthkind_flow.guest_quota_windows (
 property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 bucket text NOT NULL CHECK(bucket ~ '^[0-9a-f]{64}$'),
 window_start timestamptz NOT NULL,
 request_count integer NOT NULL CHECK(request_count BETWEEN 1 AND 60),
 PRIMARY KEY(property_id,bucket,window_start)
);
ALTER TABLE worthkind_flow.guest_quota_windows ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_quota_windows FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.guest_quota_windows FROM PUBLIC;
CREATE FUNCTION worthkind_flow.consume_guest_quota(p_slug text,p_bucket text)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; v_window timestamptz; v_count integer;
BEGIN
 IF p_bucket IS NULL OR p_bucket !~ '^[0-9a-f]{64}$' THEN RAISE EXCEPTION 'Invalid bucket' USING ERRCODE='22023'; END IF;
 SELECT p.id INTO v_property FROM worthkind_flow.properties p
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified';
 IF v_property IS NULL THEN RAISE EXCEPTION 'Hotel unavailable' USING ERRCODE='P0002'; END IF;
 v_window=date_trunc('minute',statement_timestamp());
 INSERT INTO worthkind_flow.guest_quota_windows AS q(property_id,bucket,window_start,request_count)
 VALUES(v_property,p_bucket,v_window,1)
 ON CONFLICT(property_id,bucket,window_start) DO UPDATE SET request_count=q.request_count+1
 WHERE q.request_count<60 RETURNING request_count INTO v_count;
 RETURN v_count IS NOT NULL;
END $$;
CREATE FUNCTION worthkind_flow.prune_guest_quota()
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE n bigint;
BEGIN
 DELETE FROM worthkind_flow.guest_quota_windows WHERE window_start<now()-interval '1 day';
 GET DIAGNOSTICS n=ROW_COUNT; RETURN n;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.consume_guest_quota(text,text),worthkind_flow.prune_guest_quota() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.consume_guest_quota(text,text),worthkind_flow.prune_guest_quota() TO wf_guest_quota;
COMMIT;
