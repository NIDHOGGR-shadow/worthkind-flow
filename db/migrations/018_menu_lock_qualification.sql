BEGIN;
CREATE OR REPLACE FUNCTION worthkind_flow.save_menu_item(p_subject text,p_slug text,p_code text,p_name text,p_description text,p_price bigint,p_currency text,p_available boolean,p_revision bigint)
RETURNS TABLE(id uuid,revision bigint)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE a record; m worthkind_flow.menu_items%ROWTYPE;
BEGIN
 SELECT * INTO a FROM worthkind_flow.ops_actor(p_subject,p_slug);
 IF NOT FOUND OR a.member_role NOT IN ('owner','manager') THEN RAISE EXCEPTION 'Access denied' USING ERRCODE='42501'; END IF;
 PERFORM 1 FROM worthkind_flow.properties p WHERE p.id=a.property_id FOR UPDATE;
 IF p_revision=0 THEN
 INSERT INTO worthkind_flow.menu_items(property_id,code,name,description,price_minor,currency,available)
 VALUES(a.property_id,p_code,p_name,p_description,p_price,p_currency,p_available) RETURNING * INTO m;
 ELSE
 UPDATE worthkind_flow.menu_items x SET name=p_name,description=p_description,price_minor=p_price,currency=p_currency,available=p_available,revision=x.revision+1
 WHERE x.property_id=a.property_id AND x.code=p_code AND x.revision=p_revision RETURNING * INTO m;
 IF NOT FOUND THEN RAISE EXCEPTION 'Revision conflict' USING ERRCODE='40001'; END IF;
 END IF;
 RETURN QUERY SELECT m.id,m.revision;
END $$;

COMMIT;
