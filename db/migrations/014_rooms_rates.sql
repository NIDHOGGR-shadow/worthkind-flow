BEGIN;
CREATE TABLE worthkind_flow.room_types(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 code text NOT NULL CHECK(code ~ '^[A-Za-z0-9_-]{2,40}$'),name text NOT NULL CHECK(length(btrim(name)) BETWEEN 2 AND 100),
 description text NOT NULL CHECK(length(description)<=2000), max_guests integer NOT NULL CHECK(max_guests BETWEEN 1 AND 30),
 published boolean NOT NULL DEFAULT false, revision bigint NOT NULL DEFAULT 1, created_at timestamptz NOT NULL DEFAULT now(),
 UNIQUE(property_id,code), UNIQUE(id,property_id)
);
CREATE TABLE worthkind_flow.hotel_rooms(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,room_type_id uuid NOT NULL,
 label text NOT NULL CHECK(length(btrim(label)) BETWEEN 1 AND 40),
 operational_state text NOT NULL DEFAULT 'unknown' CHECK(operational_state IN ('unknown','clean','dirty','inspecting','out_of_service')),
 revision bigint NOT NULL DEFAULT 1,
 UNIQUE(property_id,label),UNIQUE(id,property_id),
 FOREIGN KEY(room_type_id,property_id) REFERENCES worthkind_flow.room_types(id,property_id)
);
CREATE TABLE worthkind_flow.display_rates(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL,room_type_id uuid NOT NULL,
 code text NOT NULL CHECK(code ~ '^[A-Za-z0-9_-]{2,40}$'),currency text NOT NULL CHECK(currency ~ '^[A-Z]{3}$'),
 amount_minor bigint NOT NULL CHECK(amount_minor BETWEEN 0 AND 1000000000000),
 start_date date NOT NULL,end_date date NOT NULL CHECK(end_date>start_date),
 revision bigint NOT NULL DEFAULT 1,
 UNIQUE(property_id,room_type_id,code),
 FOREIGN KEY(room_type_id,property_id) REFERENCES worthkind_flow.room_types(id,property_id)
);
CREATE TABLE worthkind_flow.room_catalog_events(
 id uuid PRIMARY KEY DEFAULT gen_random_uuid(),property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id),
 actor uuid NOT NULL,resource_id uuid NOT NULL,action text NOT NULL,created_at timestamptz NOT NULL DEFAULT now(),
 FOREIGN KEY(actor,property_id) REFERENCES worthkind_flow.staff_memberships(id,property_id)
);
ALTER TABLE worthkind_flow.room_types ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.room_types FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.hotel_rooms ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.hotel_rooms FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.display_rates ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.display_rates FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.room_catalog_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.room_catalog_events FORCE ROW LEVEL SECURITY;
REVOKE ALL ON worthkind_flow.room_types,worthkind_flow.hotel_rooms,worthkind_flow.display_rates,worthkind_flow.room_catalog_events FROM PUBLIC;

CREATE FUNCTION worthkind_flow.manage_room_type(p_subject text,p_slug text,p_code text,p_name text,p_description text,p_max integer,p_published boolean,p_revision bigint)
RETURNS TABLE(id uuid,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; r worthkind_flow.room_types%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF p_revision=0 THEN
  INSERT INTO worthkind_flow.room_types(property_id,code,name,description,max_guests,published)
  VALUES(a.property_id,p_code,p_name,p_description,p_max,p_published) RETURNING * INTO r;
 ELSE
  UPDATE worthkind_flow.room_types t SET name=p_name,description=p_description,max_guests=p_max,published=p_published,revision=t.revision+1
  WHERE t.property_id=a.property_id AND t.code=p_code AND t.revision=p_revision RETURNING * INTO r;
  IF NOT FOUND THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
 END IF;
 INSERT INTO worthkind_flow.room_catalog_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,r.id,'room_type_saved');
 RETURN QUERY SELECT r.id,r.revision;
END $$;
CREATE FUNCTION worthkind_flow.create_room(p_subject text,p_slug text,p_type uuid,p_label text)
RETURNS uuid LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_id uuid;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.room_types WHERE property_id=a.property_id AND id=p_type) THEN RAISE EXCEPTION 'Room type unavailable' USING ERRCODE='P0002'; END IF;
 INSERT INTO worthkind_flow.hotel_rooms(property_id,room_type_id,label) VALUES(a.property_id,p_type,p_label) RETURNING id INTO v_id;
 INSERT INTO worthkind_flow.room_catalog_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,v_id,'room_created');
 RETURN v_id;
END $$;
CREATE FUNCTION worthkind_flow.change_room_state(p_subject text,p_slug text,p_room uuid,p_state text,p_revision bigint)
RETURNS bigint LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; v_revision bigint;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','housekeeping','maintenance') OR
 (a.member_role='housekeeping' AND p_state NOT IN ('clean','dirty','inspecting')) OR
 (a.member_role='maintenance' AND p_state NOT IN ('out_of_service','inspecting')) THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 UPDATE worthkind_flow.hotel_rooms SET operational_state=p_state,revision=revision+1
 WHERE property_id=a.property_id AND id=p_room AND revision=p_revision
 AND (a.member_role<>'housekeeping' OR operational_state<>'out_of_service')
 RETURNING revision INTO v_revision;
 IF NOT FOUND THEN RAISE EXCEPTION 'Room unavailable or revision conflict' USING ERRCODE='40001'; END IF;
 INSERT INTO worthkind_flow.room_catalog_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,p_room,'room_state_changed');
 RETURN v_revision;
END $$;
CREATE FUNCTION worthkind_flow.save_display_rate(p_subject text,p_slug text,p_type uuid,p_code text,p_currency text,p_minor bigint,p_start date,p_end date,p_revision bigint)
RETURNS TABLE(id uuid,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; r worthkind_flow.display_rates%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.room_types WHERE id=p_type AND property_id=a.property_id) THEN RAISE EXCEPTION 'Room type unavailable' USING ERRCODE='P0002'; END IF;
 IF p_revision=0 THEN
  INSERT INTO worthkind_flow.display_rates(property_id,room_type_id,code,currency,amount_minor,start_date,end_date)
  VALUES(a.property_id,p_type,p_code,p_currency,p_minor,p_start,p_end) RETURNING * INTO r;
 ELSE
  UPDATE worthkind_flow.display_rates t SET currency=p_currency,amount_minor=p_minor,start_date=p_start,end_date=p_end,revision=t.revision+1
  WHERE t.property_id=a.property_id AND t.room_type_id=p_type AND t.code=p_code AND t.revision=p_revision RETURNING * INTO r;
  IF NOT FOUND THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
 END IF;
 INSERT INTO worthkind_flow.room_catalog_events(property_id,actor,resource_id,action) VALUES(a.property_id,a.member_id,r.id,'display_rate_saved');
 RETURN QUERY SELECT r.id,r.revision;
END $$;
CREATE FUNCTION worthkind_flow.list_room_catalog(p_slug text)
RETURNS TABLE(id uuid,code text,name text,description text,max_guests integer,display_rates jsonb)
LANGUAGE sql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
 SELECT t.id,t.code,t.name,t.description,t.max_guests,
 COALESCE((SELECT jsonb_agg(jsonb_build_object('code',r.code,'currency',r.currency,'amount_minor',r.amount_minor,'start_date',r.start_date,'end_date',r.end_date) ORDER BY r.code)
 FROM worthkind_flow.display_rates r WHERE r.room_type_id=t.id AND r.property_id=t.property_id AND r.end_date>current_date),'[]'::jsonb)
 FROM worthkind_flow.room_types t JOIN worthkind_flow.properties p ON p.id=t.property_id JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE p.slug=p_slug AND p.status='active' AND o.status='verified' AND t.published ORDER BY t.code
$$;
CREATE FUNCTION worthkind_flow.list_internal_rooms(p_subject text,p_slug text)
RETURNS TABLE(id uuid,label text,room_type_id uuid,operational_state text,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','reception','housekeeping','maintenance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 RETURN QUERY SELECT r.id,r.label,r.room_type_id,r.operational_state,r.revision FROM worthkind_flow.hotel_rooms r
 WHERE r.property_id=a.property_id ORDER BY r.label LIMIT 500;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.manage_room_type(text,text,text,text,text,integer,boolean,bigint),worthkind_flow.create_room(text,text,uuid,text),
 worthkind_flow.change_room_state(text,text,uuid,text,bigint),worthkind_flow.save_display_rate(text,text,uuid,text,text,bigint,date,date,bigint),
 worthkind_flow.list_room_catalog(text),worthkind_flow.list_internal_rooms(text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.manage_room_type(text,text,text,text,text,integer,boolean,bigint),worthkind_flow.create_room(text,text,uuid,text),
 worthkind_flow.change_room_state(text,text,uuid,text,bigint),worthkind_flow.save_display_rate(text,text,uuid,text,text,bigint,date,date,bigint),
 worthkind_flow.list_internal_rooms(text,text) TO wf_operations;
GRANT EXECUTE ON FUNCTION worthkind_flow.list_room_catalog(text) TO wf_public_content;
COMMIT;
