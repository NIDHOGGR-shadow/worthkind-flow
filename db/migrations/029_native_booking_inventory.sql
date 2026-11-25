BEGIN;
-- Native inventory is authoritative ONLY for explicitly onboarded properties.
CREATE TABLE worthkind_flow.native_booking_accounts(
 property_id uuid PRIMARY KEY REFERENCES worthkind_flow.properties(id),
 approval_reference text NOT NULL CHECK(length(btrim(approval_reference)) BETWEEN 8 AND 240),
 inventory_verified_at timestamptz NOT NULL DEFAULT now(),
 enabled boolean NOT NULL DEFAULT false
);
CREATE TABLE worthkind_flow.bookable_rates(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,room_type_id uuid NOT NULL,
 code text NOT NULL CHECK(code ~ '^[A-Za-z0-9_-]{2,40}$'),
 currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),nightly_total_minor bigint NOT NULL CHECK(nightly_total_minor BETWEEN 1 AND 1000000000000),
 start_date date NOT NULL,end_date date NOT NULL CHECK(end_date>start_date),
 policy_reference text NOT NULL CHECK(length(btrim(policy_reference)) BETWEEN 8 AND 240),
 active boolean NOT NULL DEFAULT true,revision bigint NOT NULL DEFAULT 1,
 UNIQUE(property_id,room_type_id,code),
 FOREIGN KEY(room_type_id,property_id) REFERENCES worthkind_flow.room_types(id,property_id)
);
CREATE TABLE worthkind_flow.native_bookings(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,intent_id uuid NOT NULL,
 room_type_id uuid NOT NULL,rate_id uuid NOT NULL REFERENCES worthkind_flow.bookable_rates(id),
 arrival date NOT NULL,departure date NOT NULL CHECK(departure>arrival AND departure-arrival<=90),
 room_count integer NOT NULL CHECK(room_count BETWEEN 1 AND 10),adults integer NOT NULL,children integer NOT NULL,
 currency text NOT NULL,nightly_total_minor bigint NOT NULL CHECK(nightly_total_minor>0),
 total_minor bigint NOT NULL CHECK(total_minor=nightly_total_minor*room_count*(departure-arrival)),
 policy_reference text NOT NULL,request_key text NOT NULL CHECK(length(request_key) BETWEEN 8 AND 100),
 state text NOT NULL DEFAULT 'held' CHECK(state IN ('held','confirmed','cancelled','expired')),
 expires_at timestamptz NOT NULL,confirmed_at timestamptz,revision bigint NOT NULL DEFAULT 1,
 created_by uuid NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,request_key),UNIQUE(id,property_id),
 FOREIGN KEY(intent_id,property_id) REFERENCES worthkind_flow.reservation_intents(id,property_id),
 FOREIGN KEY(room_type_id,property_id) REFERENCES worthkind_flow.room_types(id,property_id),
 FOREIGN KEY(created_by,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
CREATE UNIQUE INDEX wf_native_one_active ON worthkind_flow.native_bookings(intent_id) WHERE state IN ('held','confirmed');
CREATE TABLE worthkind_flow.booking_room_nights(
 property_id uuid NOT NULL,booking_id uuid NOT NULL,room_id uuid NOT NULL,night date NOT NULL,
 PRIMARY KEY(property_id,room_id,night),
 FOREIGN KEY(booking_id,property_id) REFERENCES worthkind_flow.native_bookings(id,property_id),
 FOREIGN KEY(room_id,property_id) REFERENCES worthkind_flow.hotel_rooms(id,property_id)
);
CREATE INDEX wf_native_nights_booking ON worthkind_flow.booking_room_nights(booking_id);
CREATE TABLE worthkind_flow.native_booking_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,booking_id uuid NOT NULL,actor uuid,
 action text NOT NULL,details jsonb NOT NULL DEFAULT '{}'::jsonb,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(booking_id,property_id) REFERENCES worthkind_flow.native_bookings(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['native_booking_accounts','bookable_rates','native_bookings','booking_room_nights','native_booking_events'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;

CREATE FUNCTION worthkind_flow.configure_native_bookings(p_slug text,p_approval text,p_enabled boolean)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 SELECT p.id INTO v_property FROM worthkind_flow.properties p JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' FOR UPDATE OF p;
 IF NOT FOUND THEN RAISE EXCEPTION 'Property unavailable' USING ERRCODE='P0002'; END IF;
 IF p_enabled AND (EXISTS(SELECT 1 FROM worthkind_flow.pms_accounts WHERE property_id=v_property AND enabled)
 OR NOT EXISTS(SELECT 1 FROM worthkind_flow.hotel_rooms WHERE property_id=v_property AND operational_state IN ('clean','dirty','inspecting'))) THEN
 RAISE EXCEPTION 'Inventory authority not established' USING ERRCODE='23514'; END IF;
 IF NOT p_enabled AND EXISTS(SELECT 1 FROM worthkind_flow.native_bookings WHERE property_id=v_property AND
 (state='confirmed' AND departure>=current_date OR state='held' AND expires_at>now())) THEN
 RAISE EXCEPTION 'Active native stays must be migrated before disabling inventory' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.native_booking_accounts(property_id,approval_reference,enabled)
 VALUES(v_property,p_approval,p_enabled)
 ON CONFLICT(property_id) DO UPDATE SET approval_reference=EXCLUDED.approval_reference,enabled=EXCLUDED.enabled,inventory_verified_at=now();
 RETURN v_property;
END $$;
CREATE FUNCTION worthkind_flow.guard_external_inventory()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 PERFORM 1 FROM worthkind_flow.properties WHERE id=NEW.property_id FOR UPDATE;
 IF NEW.enabled AND EXISTS(SELECT 1 FROM worthkind_flow.native_booking_accounts WHERE property_id=NEW.property_id AND enabled) THEN
 RAISE EXCEPTION 'Native inventory authority already active' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_no_dual_inventory BEFORE INSERT OR UPDATE ON worthkind_flow.pms_accounts FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_external_inventory();

CREATE FUNCTION worthkind_flow.save_bookable_rate(p_subject text,p_slug text,p_type uuid,p_code text,p_currency text,p_nightly bigint,p_start date,p_end date,p_policy text,p_active boolean,p_revision bigint)
RETURNS TABLE(id uuid,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; r worthkind_flow.bookable_rates%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties p WHERE p.id=a.property_id FOR UPDATE;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.room_types t WHERE t.id=p_type AND t.property_id=a.property_id) THEN RAISE EXCEPTION 'Room type unavailable' USING ERRCODE='P0002'; END IF;
 IF p_revision=0 THEN
 INSERT INTO worthkind_flow.bookable_rates(property_id,room_type_id,code,currency,nightly_total_minor,start_date,end_date,policy_reference,active)
 VALUES(a.property_id,p_type,p_code,p_currency,p_nightly,p_start,p_end,p_policy,p_active) RETURNING * INTO r;
 ELSE
 UPDATE worthkind_flow.bookable_rates x SET currency=p_currency,nightly_total_minor=p_nightly,start_date=p_start,end_date=p_end,
 policy_reference=p_policy,active=p_active,revision=x.revision+1
 WHERE x.property_id=a.property_id AND x.room_type_id=p_type AND x.code=p_code AND x.revision=p_revision RETURNING * INTO r;
 IF NOT FOUND THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
 END IF;
 INSERT INTO worthkind_flow.room_catalog_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,r.id,'bookable_rate_saved');
 RETURN QUERY SELECT r.id,r.revision;
END $$;

CREATE FUNCTION worthkind_flow.expire_native_holds(p_property uuid)
RETURNS void LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_id uuid;
BEGIN
 FOR v_id IN UPDATE worthkind_flow.native_bookings b SET state='expired',revision=revision+1
 WHERE b.property_id=p_property AND b.state='held' AND b.expires_at<=now() RETURNING b.id
 LOOP
 DELETE FROM worthkind_flow.booking_room_nights WHERE booking_id=v_id AND property_id=p_property;
 INSERT INTO worthkind_flow.native_booking_events(property_id,booking_id,action) VALUES(p_property,v_id,'expired');
 END LOOP;
END $$;

CREATE FUNCTION worthkind_flow.hold_native_booking(p_subject text,p_slug text,p_intent uuid,p_type uuid,p_rate uuid,p_key text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; r worthkind_flow.reservation_intents%ROWTYPE; rate worthkind_flow.bookable_rates%ROWTYPE; b worthkind_flow.native_bookings%ROWTYPE; picked uuid[]; room uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties p WHERE p.id=a.property_id FOR UPDATE;
 PERFORM worthkind_flow.expire_native_holds(a.property_id);
 SELECT * INTO b FROM worthkind_flow.native_bookings x WHERE x.property_id=a.property_id AND x.request_key=p_key;
 IF FOUND THEN
 IF b.intent_id<>p_intent OR b.room_type_id<>p_type OR b.rate_id<>p_rate THEN RAISE EXCEPTION 'Request conflict' USING ERRCODE='23505'; END IF;
 RETURN to_jsonb(b)-'created_by'-'property_id'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.native_booking_accounts WHERE property_id=a.property_id AND enabled) THEN RAISE EXCEPTION 'Native inventory disabled' USING ERRCODE='23514'; END IF;
 SELECT * INTO r FROM worthkind_flow.reservation_intents x WHERE x.id=p_intent AND x.property_id=a.property_id AND x.state='under_review' FOR UPDATE;
 IF NOT FOUND OR r.arrival<(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=a.property_id) OR
 (r.room_type_id IS NOT NULL AND r.room_type_id<>p_type) THEN RAISE EXCEPTION 'Stay unavailable' USING ERRCODE='P0002'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.room_types t WHERE t.id=p_type AND t.property_id=a.property_id AND t.published AND t.max_guests*r.room_count>=r.adults+r.children) THEN
 RAISE EXCEPTION 'Room capacity unavailable' USING ERRCODE='23514'; END IF;
 SELECT * INTO rate FROM worthkind_flow.bookable_rates x WHERE x.id=p_rate AND x.property_id=a.property_id AND x.room_type_id=p_type AND x.active
 AND x.start_date<=r.arrival AND x.end_date>=r.departure;
 IF NOT FOUND THEN RAISE EXCEPTION 'Rate unavailable' USING ERRCODE='P0002'; END IF;
 SELECT array_agg(x.id) INTO picked FROM (SELECT h.id FROM worthkind_flow.hotel_rooms h
 WHERE h.property_id=a.property_id AND h.room_type_id=p_type AND h.operational_state IN ('clean','dirty','inspecting')
 AND NOT EXISTS(SELECT 1 FROM worthkind_flow.booking_room_nights n WHERE n.property_id=a.property_id AND n.room_id=h.id AND n.night>=r.arrival AND n.night<r.departure)
 ORDER BY h.label,h.id LIMIT r.room_count FOR UPDATE)x;
 IF COALESCE(cardinality(picked),0)<>r.room_count THEN RAISE EXCEPTION 'Insufficient inventory' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.native_bookings(property_id,intent_id,room_type_id,rate_id,arrival,departure,room_count,adults,children,currency,
 nightly_total_minor,total_minor,policy_reference,request_key,expires_at,created_by)
 VALUES(a.property_id,r.id,p_type,p_rate,r.arrival,r.departure,r.room_count,r.adults,r.children,rate.currency,
 rate.nightly_total_minor,rate.nightly_total_minor*r.room_count*(r.departure-r.arrival),rate.policy_reference,p_key,now()+interval '15 minutes',a.member_id)
 RETURNING * INTO b;
 FOREACH room IN ARRAY picked LOOP
 INSERT INTO worthkind_flow.booking_room_nights(property_id,booking_id,room_id,night)
 SELECT a.property_id,b.id,room,r.arrival+d FROM generate_series(0,r.departure-r.arrival-1)d;
 END LOOP;
 INSERT INTO worthkind_flow.native_booking_events(property_id,booking_id,actor,action) VALUES(a.property_id,b.id,a.member_id,'held');
 RETURN to_jsonb(b)-'created_by'-'property_id';
END $$;

CREATE FUNCTION worthkind_flow.confirm_native_booking(p_slug text,p_case uuid,p_hash text,p_booking uuid,p_expected_total bigint)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid; b worthkind_flow.native_bookings%ROWTYPE;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 PERFORM 1 FROM worthkind_flow.properties WHERE id=v_property FOR UPDATE;
 SELECT x.* INTO b FROM worthkind_flow.native_bookings x JOIN worthkind_flow.reservation_intents r ON r.id=x.intent_id AND r.property_id=x.property_id
 WHERE x.id=p_booking AND x.property_id=v_property AND r.case_id=p_case AND r.state='under_review' FOR UPDATE OF x;
 IF NOT FOUND THEN RAISE EXCEPTION 'Booking unavailable' USING ERRCODE='P0002'; END IF;
 IF p_expected_total IS DISTINCT FROM b.total_minor THEN RAISE EXCEPTION 'Quote mismatch' USING ERRCODE='23514'; END IF;
 IF b.state='confirmed' THEN RETURN to_jsonb(b)-'created_by'-'property_id'; END IF;
 IF b.state<>'held' OR b.expires_at<=now() OR NOT EXISTS(SELECT 1 FROM worthkind_flow.native_booking_accounts WHERE property_id=v_property AND enabled)
 OR EXISTS(SELECT 1 FROM worthkind_flow.booking_room_nights n JOIN worthkind_flow.hotel_rooms h ON h.id=n.room_id AND h.property_id=n.property_id
 WHERE n.booking_id=b.id AND h.operational_state NOT IN ('clean','dirty','inspecting')) THEN
 RAISE EXCEPTION 'Hold unavailable' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.native_bookings SET state='confirmed',confirmed_at=now(),revision=revision+1 WHERE id=b.id RETURNING * INTO b;
 INSERT INTO worthkind_flow.native_booking_events(property_id,booking_id,action) VALUES(v_property,b.id,'guest_confirmed_pay_at_property');
 RETURN to_jsonb(b)-'created_by'-'property_id';
END $$;

CREATE FUNCTION worthkind_flow.cancel_native_booking(p_subject text,p_slug text,p_booking uuid,p_revision bigint,p_reason text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; b worthkind_flow.native_bookings%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF length(btrim(p_reason)) NOT BETWEEN 8 AND 240 THEN RAISE EXCEPTION 'Reason required' USING ERRCODE='22023'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO b FROM worthkind_flow.native_bookings WHERE id=p_booking AND property_id=a.property_id FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Booking unavailable' USING ERRCODE='P0002'; END IF;
 IF b.state='cancelled' THEN RETURN to_jsonb(b)-'created_by'-'property_id'; END IF;
 IF b.state NOT IN ('held','confirmed') OR b.revision<>p_revision OR b.arrival<(SELECT (now() AT TIME ZONE p.time_zone)::date FROM worthkind_flow.properties p WHERE p.id=a.property_id) THEN
 RAISE EXCEPTION 'Booking conflict' USING ERRCODE='23514'; END IF;
 DELETE FROM worthkind_flow.booking_room_nights WHERE booking_id=b.id AND property_id=a.property_id;
 UPDATE worthkind_flow.native_bookings SET state='cancelled',revision=revision+1 WHERE id=b.id RETURNING * INTO b;
 INSERT INTO worthkind_flow.native_booking_events(property_id,booking_id,actor,action,details) VALUES(a.property_id,b.id,a.member_id,'cancelled',jsonb_build_object('reason',p_reason));
 RETURN to_jsonb(b)-'created_by'-'property_id';
END $$;

CREATE FUNCTION worthkind_flow.guest_native_bookings(p_slug text,p_case uuid,p_hash text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE v_property uuid;
BEGIN
 v_property:=worthkind_flow.verified_guest_case(p_slug,p_case,p_hash);
 RETURN COALESCE((SELECT jsonb_agg((to_jsonb(x)-'created_by'-'property_id')||jsonb_build_object('state',CASE WHEN x.state='held' AND x.expires_at<=now() THEN 'expired' ELSE x.state END))
 FROM worthkind_flow.native_bookings x JOIN worthkind_flow.reservation_intents r ON r.id=x.intent_id AND r.property_id=x.property_id
 WHERE x.property_id=v_property AND r.case_id=p_case),'[]'::jsonb);
END $$;
CREATE FUNCTION worthkind_flow.staff_native_bookings(p_subject text,p_slug text)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN COALESCE((SELECT jsonb_agg(to_jsonb(x)) FROM (SELECT b.id,b.intent_id,b.arrival,b.departure,b.room_count,b.currency,b.total_minor,b.revision,b.expires_at,
 CASE WHEN b.state='held' AND b.expires_at<=now() THEN 'expired' ELSE b.state END AS state,
 EXISTS(SELECT 1 FROM worthkind_flow.booking_room_nights n JOIN worthkind_flow.hotel_rooms h ON h.id=n.room_id AND h.property_id=n.property_id WHERE n.booking_id=b.id AND h.operational_state NOT IN ('clean','dirty','inspecting')) AS room_conflict
 FROM worthkind_flow.native_bookings b WHERE b.property_id=a.property_id ORDER BY b.created_at DESC LIMIT 200)x),'[]'::jsonb);
END $$;
-- Avoid contradictory intent withdrawal/decline after a valid hold or confirmation.
CREATE FUNCTION worthkind_flow.guard_native_intent_state()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF NEW.state<>OLD.state AND NEW.state IN ('withdrawn','declined') AND EXISTS(
 SELECT 1 FROM worthkind_flow.native_bookings b WHERE b.intent_id=NEW.id AND b.property_id=NEW.property_id
 AND (b.state='confirmed' OR b.state='held' AND b.expires_at>now())) THEN
 RAISE EXCEPTION 'Cancel booking before closing intent' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_native_intent_guard BEFORE UPDATE OF state ON worthkind_flow.reservation_intents FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_native_intent_state();
REVOKE ALL ON FUNCTION worthkind_flow.configure_native_bookings(text,text,boolean),worthkind_flow.guard_external_inventory(),worthkind_flow.save_bookable_rate(text,text,uuid,text,text,bigint,date,date,text,boolean,bigint),
 worthkind_flow.expire_native_holds(uuid),worthkind_flow.hold_native_booking(text,text,uuid,uuid,uuid,text),worthkind_flow.confirm_native_booking(text,uuid,text,uuid,bigint),
 worthkind_flow.cancel_native_booking(text,text,uuid,bigint,text),worthkind_flow.guest_native_bookings(text,uuid,text),worthkind_flow.staff_native_bookings(text,text),worthkind_flow.guard_native_intent_state() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.configure_native_bookings(text,text,boolean) TO wf_hotel_provisioner;
GRANT EXECUTE ON FUNCTION worthkind_flow.save_bookable_rate(text,text,uuid,text,text,bigint,date,date,text,boolean,bigint),
 worthkind_flow.hold_native_booking(text,text,uuid,uuid,uuid,text),worthkind_flow.cancel_native_booking(text,text,uuid,bigint,text),worthkind_flow.staff_native_bookings(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.confirm_native_booking(text,uuid,text,uuid,bigint),worthkind_flow.guest_native_bookings(text,uuid,text) TO wf_guest_api;
COMMIT;
