BEGIN;
CREATE OR REPLACE FUNCTION worthkind_flow.save_display_rate(p_subject text,p_slug text,p_type uuid,p_code text,p_currency text,p_minor bigint,p_start date,p_end date,p_revision bigint)
RETURNS TABLE(id uuid,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; r worthkind_flow.display_rates%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager','finance') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 IF NOT EXISTS(SELECT 1 FROM worthkind_flow.room_types rt WHERE rt.id=p_type AND rt.property_id=a.property_id) THEN RAISE EXCEPTION 'Room type unavailable' USING ERRCODE='P0002'; END IF;
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

COMMIT;
