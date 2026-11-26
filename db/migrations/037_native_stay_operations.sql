BEGIN;
CREATE TABLE worthkind_flow.native_stays(
 booking_id uuid PRIMARY KEY,property_id uuid NOT NULL,
 state text NOT NULL CHECK(state IN ('checked_in','checked_out','no_show')),
 checked_in_at timestamptz,checked_out_at timestamptz,revision bigint NOT NULL DEFAULT 1,
 FOREIGN KEY(booking_id,property_id) REFERENCES worthkind_flow.native_bookings(id,property_id),
 UNIQUE(booking_id,property_id)
);
CREATE TABLE worthkind_flow.occupied_rooms(
 property_id uuid NOT NULL,room_id uuid NOT NULL,booking_id uuid NOT NULL,
 PRIMARY KEY(property_id,room_id),
 FOREIGN KEY(room_id,property_id) REFERENCES worthkind_flow.hotel_rooms(id,property_id),
 FOREIGN KEY(booking_id,property_id) REFERENCES worthkind_flow.native_stays(booking_id,property_id)
);
CREATE TABLE worthkind_flow.stay_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,booking_id uuid NOT NULL,actor uuid NOT NULL,
 action text NOT NULL,encrypted_note bytea,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(booking_id,property_id) REFERENCES worthkind_flow.native_bookings(id,property_id),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
DO $$ DECLARE t text; BEGIN
 FOREACH t IN ARRAY ARRAY['native_stays','occupied_rooms','stay_events'] LOOP
 EXECUTE format('ALTER TABLE worthkind_flow.%I ENABLE ROW LEVEL SECURITY',t);
 EXECUTE format('ALTER TABLE worthkind_flow.%I FORCE ROW LEVEL SECURITY',t);
 EXECUTE format('REVOKE ALL ON worthkind_flow.%I FROM PUBLIC',t);
 END LOOP;
END $$;
CREATE FUNCTION worthkind_flow.transition_native_stay(p_subject text,p_slug text,p_booking uuid,p_action text,p_revision bigint,p_note bytea)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; b worthkind_flow.native_bookings%ROWTYPE; s worthkind_flow.native_stays%ROWTYPE; today date; rooms uuid[];
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties WHERE id=a.property_id FOR UPDATE;
 SELECT * INTO b FROM worthkind_flow.native_bookings WHERE id=p_booking AND property_id=a.property_id AND state='confirmed' FOR UPDATE;
 IF NOT FOUND THEN RAISE EXCEPTION 'Stay unavailable' USING ERRCODE='P0002'; END IF;
 SELECT (now() AT TIME ZONE p.time_zone)::date INTO today FROM worthkind_flow.properties p WHERE p.id=a.property_id;
 SELECT * INTO s FROM worthkind_flow.native_stays WHERE booking_id=b.id AND property_id=a.property_id FOR UPDATE;
 IF p_action='check_in' THEN
 IF s.state='checked_in' THEN RETURN to_jsonb(s)-'property_id'; END IF;
 IF s.booking_id IS NOT NULL OR p_revision<>0 OR today<b.arrival OR today>=b.departure THEN RAISE EXCEPTION 'Arrival unavailable' USING ERRCODE='23514'; END IF;
 SELECT array_agg(h.id ORDER BY h.id) INTO rooms FROM worthkind_flow.hotel_rooms h
 WHERE h.property_id=a.property_id AND h.operational_state='clean' AND EXISTS(
 SELECT 1 FROM worthkind_flow.booking_room_nights n WHERE n.property_id=a.property_id AND n.booking_id=b.id AND n.room_id=h.id AND n.night=today);
 IF COALESCE(cardinality(rooms),0)<>b.room_count OR EXISTS(SELECT 1 FROM worthkind_flow.occupied_rooms WHERE property_id=a.property_id AND room_id=ANY(rooms)) THEN
 RAISE EXCEPTION 'Assigned room unavailable or not clean' USING ERRCODE='23514'; END IF;
 PERFORM 1 FROM worthkind_flow.hotel_rooms WHERE property_id=a.property_id AND id=ANY(rooms) ORDER BY id FOR UPDATE;
 IF EXISTS(SELECT 1 FROM worthkind_flow.hotel_rooms WHERE property_id=a.property_id AND id=ANY(rooms) AND operational_state<>'clean') THEN RAISE EXCEPTION 'Assigned room no longer clean' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.native_stays(booking_id,property_id,state,checked_in_at) VALUES(b.id,a.property_id,'checked_in',now()) RETURNING * INTO s;
 INSERT INTO worthkind_flow.occupied_rooms(property_id,room_id,booking_id) SELECT a.property_id,unnest(rooms),b.id;
 ELSIF p_action='check_out' THEN
 IF s.state='checked_out' THEN RETURN to_jsonb(s)-'property_id'; END IF;
 IF s.state IS DISTINCT FROM 'checked_in' OR s.revision<>p_revision OR p_note IS NULL THEN RAISE EXCEPTION 'Checkout requires active stay and note' USING ERRCODE='23514'; END IF;
 UPDATE worthkind_flow.hotel_rooms h SET operational_state='dirty',revision=h.revision+1
 WHERE h.property_id=a.property_id AND h.operational_state<>'out_of_service' AND EXISTS(SELECT 1 FROM worthkind_flow.occupied_rooms o WHERE o.room_id=h.id AND o.property_id=h.property_id AND o.booking_id=b.id);
 DELETE FROM worthkind_flow.occupied_rooms WHERE property_id=a.property_id AND booking_id=b.id;
 UPDATE worthkind_flow.native_stays SET state='checked_out',checked_out_at=now(),revision=revision+1 WHERE booking_id=b.id RETURNING * INTO s;
 -- Preserve charged nights and booking history; early checkout requires separate financial adjustment.
 ELSIF p_action='no_show' THEN
 IF a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Manager required' USING ERRCODE='42501'; END IF;
 IF s.booking_id IS NOT NULL OR p_revision<>0 OR today<=b.arrival OR p_note IS NULL THEN RAISE EXCEPTION 'No-show unavailable' USING ERRCODE='23514'; END IF;
 INSERT INTO worthkind_flow.native_stays(booking_id,property_id,state) VALUES(b.id,a.property_id,'no_show') RETURNING * INTO s;
 -- No automatic cancellation or financial waiver: contracted nights remain reserved pending review.
 ELSE RAISE EXCEPTION 'Invalid stay action' USING ERRCODE='22023'; END IF;
 INSERT INTO worthkind_flow.stay_events(property_id,booking_id,actor,action,encrypted_note) VALUES(a.property_id,b.id,a.member_id,p_action,p_note);
 RETURN to_jsonb(s)-'property_id';
END $$;
CREATE FUNCTION worthkind_flow.guard_active_native_stay()
RETURNS trigger LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF (NEW.state IS DISTINCT FROM OLD.state OR NEW.arrival IS DISTINCT FROM OLD.arrival OR NEW.departure IS DISTINCT FROM OLD.departure)
 AND EXISTS(SELECT 1 FROM worthkind_flow.native_stays WHERE booking_id=OLD.id AND property_id=OLD.property_id AND state IN ('checked_in','checked_out','no_show')) THEN
 RAISE EXCEPTION 'Stay history requires dedicated adjustment' USING ERRCODE='23514'; END IF;
 RETURN NEW;
END $$;
CREATE TRIGGER wf_stay_booking_guard BEFORE UPDATE ON worthkind_flow.native_bookings FOR EACH ROW EXECUTE FUNCTION worthkind_flow.guard_active_native_stay();

CREATE FUNCTION worthkind_flow.native_stay_folio(p_subject text,p_slug text,p_booking uuid)
RETURNS jsonb LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; b worthkind_flow.native_bookings%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 SELECT * INTO b FROM worthkind_flow.native_bookings WHERE id=p_booking AND property_id=a.property_id;
 IF NOT FOUND THEN RAISE EXCEPTION 'Booking unavailable' USING ERRCODE='P0002'; END IF;
 RETURN jsonb_build_object('booking_id',b.id,'booking_state',b.state,'arrival',b.arrival,'departure',b.departure,'currency',b.currency,'contract_total_minor',b.total_minor,
 'stay',(SELECT to_jsonb(s)-'property_id' FROM worthkind_flow.native_stays s WHERE s.booking_id=b.id AND s.property_id=a.property_id),
 'rooms',COALESCE((SELECT jsonb_agg(jsonb_build_object('id',h.id,'label',h.label,'operational_state',h.operational_state) ORDER BY h.label)
 FROM worthkind_flow.hotel_rooms h WHERE h.property_id=a.property_id AND EXISTS(SELECT 1 FROM worthkind_flow.booking_room_nights n WHERE n.booking_id=b.id AND n.property_id=h.property_id AND n.room_id=h.id)),'[]'::jsonb),
 'invoice',(SELECT jsonb_build_object('id',i.id,'amount_minor',i.amount_minor,'state',i.state,'currency',i.currency,
 'live_verified_minor',COALESCE((SELECT CASE WHEN p.mode='live' AND p.state IN ('verified','refunded') THEN p.amount_minor ELSE 0 END FROM worthkind_flow.hotel_payment_intents p WHERE p.invoice_id=i.id AND p.property_id=i.property_id),0),
 'live_refunded_minor',COALESCE((SELECT sum(r.amount_minor) FROM worthkind_flow.hotel_refunds r JOIN worthkind_flow.hotel_payment_intents p ON p.id=r.payment_id AND p.property_id=r.property_id WHERE p.invoice_id=i.id AND p.property_id=i.property_id AND p.mode='live' AND r.state='processed'),0))
 FROM worthkind_flow.hotel_invoices i WHERE i.native_booking_id=b.id AND i.property_id=a.property_id),
 'unlinked_service_charges_excluded',true);
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.transition_native_stay(text,text,uuid,text,bigint,bytea),worthkind_flow.guard_active_native_stay(),worthkind_flow.native_stay_folio(text,text,uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.transition_native_stay(text,text,uuid,text,bigint,bytea),worthkind_flow.native_stay_folio(text,text,uuid) TO wf_operations;
COMMIT;
