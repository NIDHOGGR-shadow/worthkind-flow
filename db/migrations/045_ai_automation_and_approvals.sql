BEGIN;
CREATE ROLE wf_ai_automation NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_ai_automation;
CREATE TABLE worthkind_flow.ai_internal_alerts(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,ticket_id uuid NOT NULL,
 due_at timestamptz NOT NULL,category text NOT NULL,priority text NOT NULL,
 state text NOT NULL DEFAULT 'open' CHECK(state IN ('open','acknowledged','resolved')),
 acknowledged_by uuid,created_at timestamptz NOT NULL DEFAULT now(),updated_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,ticket_id,due_at),
 FOREIGN KEY(ticket_id,property_id) REFERENCES worthkind_flow.service_tickets(id,property_id),
 FOREIGN KEY(acknowledged_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE TABLE worthkind_flow.ai_action_proposals(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 requested_by uuid NOT NULL,decided_by uuid,request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 category text NOT NULL CHECK(category IN ('it','reception','housekeeping','maintenance','kitchen','general')),
 priority text NOT NULL CHECK(priority IN ('low','normal','high')),
 payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
 encrypted_payload bytea NOT NULL CHECK(octet_length(encrypted_payload) BETWEEN 29 AND 32768),
 policy_revision bigint NOT NULL,state text NOT NULL DEFAULT 'pending' CHECK(state IN ('pending','executed','rejected','expired')),
 ticket_id uuid,expires_at timestamptz NOT NULL DEFAULT now()+interval '30 minutes',created_at timestamptz NOT NULL DEFAULT now(),decided_at timestamptz,
 UNIQUE(property_id,request_key),UNIQUE(id,property_id),
 FOREIGN KEY(requested_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(decided_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id),
 FOREIGN KEY(ticket_id,property_id) REFERENCES worthkind_flow.service_tickets(id,property_id)
);
CREATE TABLE worthkind_flow.ai_action_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,proposal_id uuid NOT NULL,actor uuid NOT NULL,
 action text NOT NULL CHECK(action IN ('proposed','executed','rejected','expired')),created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(proposal_id,property_id) REFERENCES worthkind_flow.ai_action_proposals(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['ai_internal_alerts','ai_action_proposals','ai_action_events'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
CREATE FUNCTION worthkind_flow.scan_ai_alerts(p_limit integer)
RETURNS integer LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE n integer;
BEGIN
 IF p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 100 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 -- Lock property policy for each batch, so a kill switch cannot be bypassed by a concurrent scan.
 WITH candidates AS MATERIALIZED (
 SELECT t.id,t.property_id,t.due_at,t.category,t.priority FROM worthkind_flow.service_tickets t
 JOIN worthkind_flow.ai_policies ap ON ap.property_id=t.property_id AND ap.autonomous_alerts
 JOIN worthkind_flow.properties p ON p.id=t.property_id AND p.status='active'
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id AND o.status='verified'
 WHERE t.status<>'resolved' AND t.due_at<now()
 AND NOT EXISTS(SELECT 1 FROM worthkind_flow.ai_internal_alerts x WHERE x.property_id=t.property_id AND x.ticket_id=t.id AND x.due_at=t.due_at)
 ORDER BY t.due_at,t.id LIMIT p_limit FOR UPDATE OF ap SKIP LOCKED
 )
 INSERT INTO worthkind_flow.ai_internal_alerts(property_id,ticket_id,due_at,category,priority)
 SELECT property_id,id,due_at,category,priority FROM candidates ON CONFLICT DO NOTHING;
 GET DIAGNOSTICS n=ROW_COUNT;
 UPDATE worthkind_flow.ai_internal_alerts x SET state='resolved',updated_at=now()
 WHERE x.state<>'resolved' AND EXISTS(SELECT 1 FROM worthkind_flow.service_tickets t WHERE t.id=x.ticket_id AND t.property_id=x.property_id AND (t.status='resolved' OR t.due_at<>x.due_at));
 RETURN n;
END $$;
CREATE FUNCTION worthkind_flow.staff_ai_insights(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.ai_policies WHERE property_id=a.property_id AND (staff_assist OR autonomous_alerts)) THEN RAISE EXCEPTION 'Assistance unavailable' USING ERRCODE='P0002'; END IF;
 RETURN jsonb_build_object('ticket_counts',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT t.category,count(*) FILTER(WHERE t.status<>'resolved') AS open_count,count(*) FILTER(WHERE t.status<>'resolved' AND t.due_at<now()) AS overdue_count FROM worthkind_flow.service_tickets t WHERE t.property_id=a.property_id AND worthkind_flow.ops_category_allowed(a.member_role,t.category) GROUP BY t.category)x),'[]'::jsonb),
 'alerts',COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT al.id,al.ticket_id,al.category,al.priority,al.due_at,al.state FROM worthkind_flow.ai_internal_alerts al WHERE al.property_id=a.property_id AND al.state<>'resolved' AND worthkind_flow.ops_category_allowed(a.member_role,al.category) ORDER BY al.due_at LIMIT 100)x),'[]'::jsonb));
END $$;
CREATE FUNCTION worthkind_flow.ack_ai_alert(p_subject text,p_slug text,p_id uuid)
RETURNS boolean LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 UPDATE worthkind_flow.ai_internal_alerts x SET state='acknowledged',acknowledged_by=a.member_id,updated_at=now()
 WHERE x.property_id=a.property_id AND x.id=p_id AND x.state='open' AND worthkind_flow.ops_category_allowed(a.member_role,x.category);
 RETURN FOUND;
END $$;
CREATE FUNCTION worthkind_flow.propose_ai_ticket(p_subject text,p_slug text,p_key text,p_hash text,p_category text,p_priority text,p_payload bytea)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; cfg worthkind_flow.ai_policies%ROWTYPE; proposal worthkind_flow.ai_action_proposals%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR NOT worthkind_flow.ops_category_allowed(a.member_role,p_category) THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO cfg FROM worthkind_flow.ai_policies WHERE property_id=a.property_id AND staff_assist;
 IF NOT FOUND THEN RAISE EXCEPTION 'Assistance unavailable' USING ERRCODE='P0002'; END IF;
 SELECT * INTO proposal FROM worthkind_flow.ai_action_proposals WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
 IF proposal.requested_by<>a.member_id OR proposal.payload_hash<>p_hash OR proposal.category<>p_category OR proposal.priority<>p_priority THEN RAISE EXCEPTION 'Proposal conflict' USING ERRCODE='23505'; END IF;
 RETURN proposal.id; END IF;
 IF (SELECT count(*) FROM worthkind_flow.ai_action_proposals WHERE property_id=a.property_id AND requested_by=a.member_id AND created_at>now()-interval '1 hour')>=20 THEN RAISE EXCEPTION 'Proposal limit' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.ai_action_proposals(property_id,requested_by,request_key,category,priority,payload_hash,encrypted_payload,policy_revision)
 VALUES(a.property_id,a.member_id,p_key,p_category,p_priority,p_hash,p_payload,cfg.revision) RETURNING * INTO proposal;
 INSERT INTO worthkind_flow.ai_action_events(property_id,proposal_id,actor,action) VALUES(a.property_id,proposal.id,a.member_id,'proposed');
 RETURN proposal.id;
END $$;
CREATE FUNCTION worthkind_flow.decide_ai_ticket(p_subject text,p_slug text,p_id uuid,p_approve boolean)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; p worthkind_flow.ai_action_proposals%ROWTYPE; tid uuid; new_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO p FROM worthkind_flow.ai_action_proposals WHERE property_id=a.property_id AND id=p_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Proposal unavailable' USING ERRCODE='P0002'; END IF;
 IF p.state<>'pending' THEN RETURN jsonb_build_object('id',p.id,'state',p.state,'ticket_id',p.ticket_id); END IF;
 IF p_approve IS NULL THEN RAISE EXCEPTION 'Decision required' USING ERRCODE='22023'; END IF;
 IF NOT p_approve THEN new_state:='rejected';
 ELSIF p.expires_at<=now() OR NOT EXISTS(SELECT 1 FROM worthkind_flow.ai_policies WHERE property_id=a.property_id AND revision=p.policy_revision AND staff_assist)
 OR NOT EXISTS(SELECT 1 FROM worthkind_flow.staff_memberships m JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id WHERE m.id=p.requested_by AND m.property_id=a.property_id AND m.state='active' AND i.state='active' AND worthkind_flow.ops_category_allowed(m.role,p.category)) THEN new_state:='expired';
 ELSE
 SELECT ticket_id INTO tid FROM worthkind_flow.create_ticket(p_subject,p_slug,p.request_key,p.payload_hash,p.category,p.priority,p.encrypted_payload,NULL);
 new_state:='executed';
 END IF;
 UPDATE worthkind_flow.ai_action_proposals SET state=new_state,decided_by=a.member_id,decided_at=now(),ticket_id=tid WHERE id=p.id;
 INSERT INTO worthkind_flow.ai_action_events(property_id,proposal_id,actor,action) VALUES(a.property_id,p.id,a.member_id,new_state);
 RETURN jsonb_build_object('id',p.id,'state',new_state,'ticket_id',tid);
END $$;
CREATE FUNCTION worthkind_flow.list_ai_proposals(p_subject text,p_slug text)
RETURNS TABLE(id uuid,request_key text,category text,priority text,state text,encrypted_payload bytea,expires_at timestamptz,ticket_id uuid)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT p.id,p.request_key,p.category,p.priority,CASE WHEN p.state='pending' AND p.expires_at<=now() THEN 'expired' ELSE p.state END,p.encrypted_payload,p.expires_at,p.ticket_id
 FROM worthkind_flow.ai_action_proposals p WHERE p.property_id=a.property_id AND (a.member_role IN ('owner','manager') OR p.requested_by=a.member_id) ORDER BY p.created_at DESC LIMIT 100;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.scan_ai_alerts(integer),worthkind_flow.staff_ai_insights(text,text),worthkind_flow.ack_ai_alert(text,text,uuid),worthkind_flow.propose_ai_ticket(text,text,text,text,text,text,bytea),worthkind_flow.decide_ai_ticket(text,text,uuid,boolean),worthkind_flow.list_ai_proposals(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.scan_ai_alerts(integer) TO wf_ai_automation;
GRANT EXECUTE ON FUNCTION worthkind_flow.staff_ai_insights(text,text),worthkind_flow.ack_ai_alert(text,text,uuid),worthkind_flow.propose_ai_ticket(text,text,text,text,text,text,bytea),worthkind_flow.decide_ai_ticket(text,text,uuid,boolean),worthkind_flow.list_ai_proposals(text,text) TO wf_ai_policy;
COMMIT;
