BEGIN;
CREATE ROLE wf_operations NOLOGIN;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_operations;
CREATE TABLE worthkind_flow.service_tickets(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 payload_hash text NOT NULL CHECK(payload_hash ~ '^[0-9a-f]{64}$'),
 origin_case_id uuid, category text NOT NULL CHECK(category IN ('it','reception','housekeeping','maintenance','kitchen','billing','general')),
 priority text NOT NULL CHECK(priority IN ('low','normal','high','urgent')),
 encrypted_payload bytea NOT NULL CHECK(octet_length(encrypted_payload) BETWEEN 29 AND 32768),
 status text NOT NULL DEFAULT 'open' CHECK(status IN ('open','assigned','in_progress','resolved','reopened')),
 assignee uuid, created_at timestamptz NOT NULL DEFAULT now(), updated_at timestamptz NOT NULL DEFAULT now(), due_at timestamptz NOT NULL,
 UNIQUE(property_id,request_key), UNIQUE(property_id,origin_case_id), UNIQUE(id,property_id),
 FOREIGN KEY(origin_case_id,property_id) REFERENCES worthkind_flow.guest_cases(id,property_id),
 FOREIGN KEY(assignee,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE INDEX wf_ticket_queue ON worthkind_flow.service_tickets(property_id,status,due_at);
CREATE TABLE worthkind_flow.ticket_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(), property_id uuid NOT NULL, ticket_id uuid NOT NULL,
 actor uuid NOT NULL, action text NOT NULL, encrypted_note bytea, created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(ticket_id,property_id) REFERENCES worthkind_flow.service_tickets(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE INDEX wf_ticket_events_scope ON worthkind_flow.ticket_events(property_id,ticket_id,created_at);
ALTER TABLE worthkind_flow.service_tickets ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.service_tickets FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.ticket_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.ticket_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.service_tickets,worthkind_flow.ticket_events FROM PUBLIC;

CREATE FUNCTION worthkind_flow.ops_actor(p_subject text,p_slug text)
RETURNS TABLE(property_id uuid,member_id uuid,member_role text)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT p.id,m.id,m.role FROM worthkind_flow.properties p
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 JOIN worthkind_flow.staff_memberships m ON m.property_id=p.id
 JOIN worthkind_flow.staff_identities i ON i.id=m.identity_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified'
 AND m.state='active' AND i.state='active' AND i.provider_subject=p_subject
$$;
REVOKE ALL ON FUNCTION worthkind_flow.ops_actor(text,text) FROM PUBLIC;
CREATE FUNCTION worthkind_flow.ops_category_allowed(p_role text,p_category text)
RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
 SELECT COALESCE(p_role IN ('owner','manager') OR
 (p_role='reception' AND p_category IN ('reception','general')) OR
 (p_role='housekeeping' AND p_category='housekeeping') OR
 (p_role='maintenance' AND p_category IN ('maintenance','it')) OR
 (p_role='kitchen' AND p_category='kitchen') OR
 (p_role='finance' AND p_category='billing'),false)
$$;
REVOKE ALL ON FUNCTION worthkind_flow.ops_category_allowed(text,text) FROM PUBLIC;
CREATE FUNCTION worthkind_flow.create_ticket(p_subject text,p_slug text,p_key text,p_hash text,p_category text,p_priority text,p_payload bytea,p_case uuid)
RETURNS TABLE(ticket_id uuid,status text,duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; t worthkind_flow.service_tickets%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR NOT (a.member_role='reception' OR worthkind_flow.ops_category_allowed(a.member_role,p_category)) THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO t FROM worthkind_flow.service_tickets WHERE property_id=a.property_id AND request_key=p_key;
 IF FOUND THEN
   IF t.payload_hash<>p_hash THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
   RETURN QUERY SELECT t.id,t.status,true; RETURN;
 END IF;
 IF p_case IS NOT NULL AND (a.member_role NOT IN ('owner','manager','reception') OR NOT EXISTS(
 SELECT 1 FROM worthkind_flow.guest_cases WHERE id=p_case AND property_id=a.property_id AND state IN ('claimed','responded'))) THEN
 RAISE EXCEPTION 'Source case unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.service_tickets(property_id,request_key,payload_hash,category,priority,encrypted_payload,origin_case_id,due_at)
 VALUES(a.property_id,p_key,p_hash,p_category,p_priority,p_payload,p_case,
 now()+make_interval(hours=>CASE p_priority WHEN 'urgent' THEN 1 WHEN 'high' THEN 4 WHEN 'normal' THEN 24 WHEN 'low' THEN 72 END))
 RETURNING * INTO t;
 INSERT INTO worthkind_flow.ticket_events(property_id,ticket_id,actor,action) VALUES(a.property_id,t.id,a.member_id,'created');
 RETURN QUERY SELECT t.id,t.status,false;
END $$;
CREATE FUNCTION worthkind_flow.list_tickets(p_subject text,p_slug text,p_limit integer)
RETURNS TABLE(id uuid,request_key text,category text,priority text,status text,assignee uuid,due_at timestamptz,encrypted_payload bytea,overdue boolean)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_limit NOT BETWEEN 1 AND 100 THEN RAISE EXCEPTION 'Invalid limit' USING ERRCODE='22023'; END IF;
 RETURN QUERY SELECT t.id,t.request_key,t.category,t.priority,t.status,t.assignee,t.due_at,t.encrypted_payload,
 t.status<>'resolved' AND t.due_at<now()
 FROM worthkind_flow.service_tickets t WHERE t.property_id=a.property_id
 AND worthkind_flow.ops_category_allowed(a.member_role,t.category)
 ORDER BY (t.status='resolved'),t.due_at,t.id LIMIT p_limit;
END $$;
CREATE FUNCTION worthkind_flow.transition_ticket(p_subject text,p_slug text,p_ticket uuid,p_action text,p_note bytea)
RETURNS text LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; t worthkind_flow.service_tickets%ROWTYPE; next_state text;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO t FROM worthkind_flow.service_tickets WHERE id=p_ticket AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Ticket unavailable' USING ERRCODE='P0002'; END IF;
 IF NOT worthkind_flow.ops_category_allowed(a.member_role,t.category) THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_action='claim' AND t.status IN ('open','reopened') THEN next_state='assigned'; t.assignee=a.member_id;
 ELSIF p_action='start' AND t.status='assigned' AND t.assignee=a.member_id THEN next_state='in_progress';
 ELSIF p_action='resolve' AND t.status='in_progress' AND t.assignee=a.member_id AND p_note IS NOT NULL THEN next_state='resolved';
 ELSIF p_action='reopen' AND t.status='resolved' AND a.member_role IN ('owner','manager') AND p_note IS NOT NULL THEN next_state='reopened'; t.assignee=NULL;
 ELSIF p_action='note' AND p_note IS NOT NULL THEN next_state=t.status;
 ELSE RAISE EXCEPTION 'Invalid transition' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.service_tickets SET status=next_state,assignee=t.assignee,updated_at=now() WHERE id=t.id;
 INSERT INTO worthkind_flow.ticket_events(property_id,ticket_id,actor,action,encrypted_note) VALUES(a.property_id,t.id,a.member_id,p_action,p_note);
 RETURN next_state;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.create_ticket(text,text,text,text,text,text,bytea,uuid),
 worthkind_flow.list_tickets(text,text,integer),worthkind_flow.transition_ticket(text,text,uuid,text,bytea) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.create_ticket(text,text,text,text,text,text,bytea,uuid),
 worthkind_flow.list_tickets(text,text,integer),worthkind_flow.transition_ticket(text,text,uuid,text,bytea) TO wf_operations;
COMMIT;
