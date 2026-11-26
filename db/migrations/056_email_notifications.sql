BEGIN;
CREATE ROLE wf_email_delivery NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_email_delivery;
CREATE TABLE worthkind_flow.email_notification_accounts(
 property_id uuid PRIMARY KEY REFERENCES worthkind_flow.properties(id),
 account_alias text NOT NULL UNIQUE CHECK(account_alias ~ '^[A-Za-z0-9_-]{3,80}$'),
 sender_address text NOT NULL CHECK(length(sender_address) BETWEEN 5 AND 254),
 enabled boolean NOT NULL DEFAULT false,
 approval_reference text NOT NULL CHECK(length(btrim(approval_reference)) BETWEEN 8 AND 240)
);
CREATE TABLE worthkind_flow.email_notifications(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
 event_id uuid NOT NULL UNIQUE REFERENCES worthkind_flow.event_outbox(id),
 property_id uuid NOT NULL,case_id uuid NOT NULL,
 account_alias text NOT NULL,sender_address text NOT NULL,
 consent_id uuid NOT NULL REFERENCES worthkind_flow.guest_consent_events(id),
 authorized_by uuid NOT NULL,verification_reference text NOT NULL CHECK(length(btrim(verification_reference)) BETWEEN 8 AND 240),
 state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','accepted','delivered','failed','unknown','suppressed')),
 provider_id uuid,attempts integer NOT NULL DEFAULT 0,
 lease uuid,lease_until timestamptz,next_attempt_at timestamptz NOT NULL DEFAULT now(),
 created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(account_alias,provider_id),
 FOREIGN KEY(case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id),
 FOREIGN KEY(authorized_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE INDEX wf_email_due ON worthkind_flow.email_notifications(next_attempt_at,id) WHERE state IN ('pending','accepted');
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['email_notification_accounts','email_notifications'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
CREATE FUNCTION worthkind_flow.configure_email_notifications(p_slug text,p_alias text,p_sender text,p_enabled boolean,p_evidence text)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 IF p_enabled IS NULL OR p_sender IS NULL OR p_sender !~ '^[^[:space:]@<>]+@[^[:space:]@<>]+[.][^[:space:]@<>]+$' THEN RAISE EXCEPTION 'Invalid email configuration' USING ERRCODE='22023'; END IF;
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified';
 IF NOT FOUND THEN RAISE EXCEPTION 'Property unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.email_notification_accounts(property_id,account_alias,sender_address,enabled,approval_reference)
 VALUES(v_property,p_alias,p_sender,p_enabled,p_evidence) ON CONFLICT(property_id) DO UPDATE SET
 account_alias=EXCLUDED.account_alias,sender_address=EXCLUDED.sender_address,enabled=EXCLUDED.enabled,approval_reference=EXCLUDED.approval_reference;
END $$;
CREATE FUNCTION worthkind_flow.queue_email_notification(p_subject text,p_slug text,p_case uuid,p_event uuid,p_evidence text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; cfg worthkind_flow.email_notification_accounts%ROWTYPE; c worthkind_flow.guest_consent_events%ROWTYPE; n worthkind_flow.email_notifications%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_evidence IS NULL OR length(btrim(p_evidence)) NOT BETWEEN 8 AND 240 THEN RAISE EXCEPTION 'Contact verification reference required' USING ERRCODE='22023'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.event_outbox e JOIN worthkind_flow.guest_cases g ON g.id=e.case_id AND g.property_id=e.property_id
 WHERE e.id=p_event AND e.case_id=p_case AND e.property_id=a.property_id AND e.event_type IN ('case_responded','case_resolve') AND g.encrypted_guest_payload IS NOT NULL) THEN
 RAISE EXCEPTION 'Event unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO n FROM worthkind_flow.email_notifications WHERE event_id=p_event;
 IF FOUND THEN RETURN jsonb_build_object('id',n.id,'state',n.state,'duplicate',true); END IF;
 SELECT * INTO cfg FROM worthkind_flow.email_notification_accounts WHERE property_id=a.property_id AND enabled;
 IF NOT FOUND THEN RAISE EXCEPTION 'Email disabled' USING ERRCODE='P0002'; END IF;
 SELECT * INTO c FROM worthkind_flow.guest_consent_events WHERE case_id=p_case AND property_id=a.property_id AND purpose='service_followup' ORDER BY created_at DESC,id DESC LIMIT 1;
 IF NOT FOUND OR NOT c.granted THEN RAISE EXCEPTION 'Guest consent required' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.email_notifications(event_id,property_id,case_id,account_alias,sender_address,consent_id,authorized_by,verification_reference)
 VALUES(p_event,a.property_id,p_case,cfg.account_alias,cfg.sender_address,c.id,a.member_id,p_evidence) ON CONFLICT(event_id) DO NOTHING RETURNING * INTO n;
 IF NOT FOUND THEN
 SELECT * INTO n FROM worthkind_flow.email_notifications WHERE event_id=p_event;
 RETURN jsonb_build_object('id',n.id,'state',n.state,'duplicate',true); END IF;
 RETURN jsonb_build_object('id',n.id,'state',n.state,'duplicate',false);
END $$;
CREATE FUNCTION worthkind_flow.list_case_email_notifications(p_subject text,p_slug text,p_case uuid)
RETURNS jsonb LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=a.property_id) THEN RAISE EXCEPTION 'Case unavailable' USING ERRCODE='P0002'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x) ORDER BY x.created_at DESC,x.event_id) FROM (
 SELECT e.id AS event_id,e.event_type,e.created_at,n.id AS notification_id,COALESCE(n.state,'not_queued') AS state
 FROM worthkind_flow.event_outbox e LEFT JOIN worthkind_flow.email_notifications n ON n.event_id=e.id
 WHERE e.property_id=a.property_id AND e.case_id=p_case AND e.event_type IN ('case_responded','case_resolve')
 ORDER BY e.created_at DESC,e.id LIMIT 100)x),'[]'::jsonb);
END $$;
CREATE FUNCTION worthkind_flow.lease_email_notification()
RETURNS TABLE(job_id uuid,lease_id uuid,state text,account_alias text,sender_address text,provider_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 -- Pending retries never cross the provider's 24-hour idempotency window.
 UPDATE worthkind_flow.email_notifications n SET state=CASE WHEN n.attempts=0 THEN 'suppressed' ELSE 'unknown' END,updated_at=now(),lease=NULL,lease_until=NULL
 WHERE n.state='pending' AND (n.lease_until IS NULL OR n.lease_until<=now()) AND (n.created_at<now()-interval '12 hours' OR n.attempts>=6);
 UPDATE worthkind_flow.email_notifications n SET state='unknown',updated_at=now(),lease=NULL,lease_until=NULL
 WHERE n.state='accepted' AND n.created_at<now()-interval '7 days' AND (n.lease_until IS NULL OR n.lease_until<=now());
 RETURN QUERY WITH picked AS (
 SELECT n.id FROM worthkind_flow.email_notifications n JOIN worthkind_flow.email_notification_accounts a ON a.property_id=n.property_id AND a.enabled AND a.account_alias=n.account_alias AND a.sender_address=n.sender_address
 JOIN worthkind_flow.properties p ON p.id=n.property_id AND p.status='active' JOIN worthkind_flow.organizations o ON o.id=p.organization_id AND o.status='verified'
 WHERE n.state IN ('pending','accepted') AND n.next_attempt_at<=now() AND (n.lease_until IS NULL OR n.lease_until<=now())
 ORDER BY n.next_attempt_at,n.id LIMIT 1 FOR UPDATE OF n SKIP LOCKED
 ), leased AS (
 UPDATE worthkind_flow.email_notifications n SET lease=gen_random_uuid(),lease_until=now()+interval '2 minutes',attempts=n.attempts+CASE WHEN n.state='pending' THEN 1 ELSE 0 END
 FROM picked x WHERE n.id=x.id RETURNING n.*
 ) SELECT n.id,n.lease,n.state,n.account_alias,n.sender_address,n.provider_id FROM leased n;
END $$;
CREATE FUNCTION worthkind_flow.email_notification_payload(p_id uuid,p_lease uuid)
RETURNS TABLE(slug text,request_key text,encrypted_payload bytea)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT p.slug,c.request_key,c.encrypted_guest_payload FROM worthkind_flow.email_notifications n
 JOIN worthkind_flow.guest_cases c ON c.id=n.case_id AND c.property_id=n.property_id
 JOIN worthkind_flow.properties p ON p.id=n.property_id AND p.status='active'
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id AND o.status='verified'
 JOIN worthkind_flow.email_notification_accounts a ON a.property_id=n.property_id AND a.enabled AND a.account_alias=n.account_alias AND a.sender_address=n.sender_address
 WHERE n.id=p_id AND n.lease=p_lease AND n.lease_until>now() AND n.state='pending'
 AND n.consent_id=(SELECT g.id FROM worthkind_flow.guest_consent_events g WHERE g.property_id=n.property_id AND g.case_id=n.case_id AND g.purpose='service_followup' ORDER BY g.created_at DESC,g.id DESC LIMIT 1)
$$;
CREATE FUNCTION worthkind_flow.complete_email_notification(p_id uuid,p_lease uuid,p_outcome text,p_provider uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE n worthkind_flow.email_notifications%ROWTYPE; v_state text;
BEGIN
 SELECT * INTO n FROM worthkind_flow.email_notifications WHERE id=p_id AND lease=p_lease AND lease_until>now() FOR UPDATE;
 IF NOT FOUND THEN RETURN false; END IF;
 IF p_outcome IS NULL OR p_outcome NOT IN ('retry','accepted','delivered','failed','suppressed') THEN RAISE EXCEPTION 'Invalid delivery outcome' USING ERRCODE='22023'; END IF;
 IF n.state='pending' THEN
 IF p_outcome='accepted' AND p_provider IS NOT NULL THEN v_state:='accepted';
 ELSIF p_outcome='retry' THEN v_state:=CASE WHEN n.attempts>=6 THEN 'unknown' ELSE 'pending' END;
 ELSIF p_outcome IN ('failed','suppressed') THEN v_state:=CASE WHEN n.attempts>1 THEN 'unknown' ELSE p_outcome END;
 ELSE RAISE EXCEPTION 'Invalid send result' USING ERRCODE='22023'; END IF;
 ELSIF n.state='accepted' THEN
 IF p_provider IS DISTINCT FROM n.provider_id OR p_outcome NOT IN ('retry','delivered','failed') THEN RAISE EXCEPTION 'Invalid receipt result' USING ERRCODE='22023'; END IF;
 v_state:=CASE WHEN p_outcome='retry' THEN 'accepted' ELSE p_outcome END;
 ELSE RETURN false; END IF;
 UPDATE worthkind_flow.email_notifications SET state=v_state,provider_id=COALESCE(n.provider_id,p_provider),lease=NULL,lease_until=NULL,updated_at=now(),
 next_attempt_at=now()+make_interval(mins=>CASE WHEN v_state='accepted' THEN 5 ELSE LEAST(60,5*n.attempts) END) WHERE id=n.id;
 RETURN true;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.configure_email_notifications(text,text,text,boolean,text),worthkind_flow.queue_email_notification(text,text,uuid,uuid,text),worthkind_flow.list_case_email_notifications(text,text,uuid),worthkind_flow.lease_email_notification(),worthkind_flow.email_notification_payload(uuid,uuid),worthkind_flow.complete_email_notification(uuid,uuid,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.configure_email_notifications(text,text,text,boolean,text) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.queue_email_notification(text,text,uuid,uuid,text),worthkind_flow.list_case_email_notifications(text,text,uuid) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.lease_email_notification(),worthkind_flow.email_notification_payload(uuid,uuid),worthkind_flow.complete_email_notification(uuid,uuid,text,uuid) TO wf_email_delivery;
COMMIT;
