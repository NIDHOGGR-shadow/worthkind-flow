BEGIN;
ALTER TABLE worthkind_flow.staff_memberships DROP CONSTRAINT staff_memberships_role_check;
ALTER TABLE worthkind_flow.staff_memberships ADD CONSTRAINT staff_memberships_role_check CHECK(role IN ('owner','manager','reception','housekeeping','maintenance','kitchen','finance','it','hr','events','procurement'));
CREATE OR REPLACE FUNCTION worthkind_flow.change_staff_membership(
  p_actor text, p_slug text, p_action text, p_target_subject text, p_role text
) RETURNS TABLE(membership_id uuid, membership_state text, membership_role text)
LANGUAGE plpgsql SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
DECLARE
  v_property uuid; v_org uuid; v_actor uuid; v_actor_role text;
  v_target uuid; v_member uuid; v_state text; v_role text;
BEGIN
  IF p_action IS NULL OR p_action NOT IN ('invite','accept','revoke')
     OR p_actor IS NULL OR length(p_actor) NOT BETWEEN 8 AND 255 THEN
    RAISE EXCEPTION 'Invalid membership command' USING ERRCODE='22023';
  END IF;
  SELECT p.id,p.organization_id INTO v_property,v_org
    FROM worthkind_flow.properties p
    JOIN worthkind_flow.organizations o ON o.id=p.organization_id
    WHERE p.slug=p_slug AND p.status='active' AND o.status='verified'
    FOR UPDATE OF p;
  SELECT i.id INTO v_actor FROM worthkind_flow.staff_identities i
    WHERE i.provider_subject=p_actor AND i.state='active';
  IF v_property IS NULL OR v_actor IS NULL THEN
    RAISE EXCEPTION 'Membership access denied' USING ERRCODE='42501';
  END IF;
  IF p_action='accept' THEN
    IF p_target_subject IS NOT NULL OR p_role IS NOT NULL THEN
      RAISE EXCEPTION 'Invalid acceptance' USING ERRCODE='22023';
    END IF;
    UPDATE worthkind_flow.staff_memberships m SET state='active',activated_at=now()
      WHERE m.property_id=v_property AND m.identity_id=v_actor AND m.state='invited'
      RETURNING m.id,m.state,m.role INTO v_member,v_state,v_role;
  ELSE
    SELECT m.role INTO v_actor_role FROM worthkind_flow.staff_memberships m
      WHERE m.property_id=v_property AND m.identity_id=v_actor AND m.state='active';
    IF v_actor_role IS NULL OR v_actor_role NOT IN ('owner','manager') THEN
      RAISE EXCEPTION 'Membership access denied' USING ERRCODE='42501';
    END IF;
    SELECT i.id INTO v_target FROM worthkind_flow.staff_identities i
      WHERE i.provider_subject=p_target_subject AND (i.state='active' OR p_action='revoke');
    IF v_target IS NULL OR v_target=v_actor THEN
      RAISE EXCEPTION 'Membership access denied' USING ERRCODE='42501';
    END IF;
    IF p_action='invite' THEN
      IF p_role IS NULL OR p_role NOT IN ('manager','reception','housekeeping','maintenance','kitchen','finance','it','hr','events','procurement')
         OR (p_role='manager' AND v_actor_role<>'owner') THEN
        RAISE EXCEPTION 'Membership access denied' USING ERRCODE='42501';
      END IF;
      INSERT INTO worthkind_flow.staff_memberships AS m
        (organization_id,property_id,identity_id,role)
        VALUES(v_org,v_property,v_target,p_role)
        ON CONFLICT(property_id,identity_id) DO NOTHING
        RETURNING m.id,m.state,m.role INTO v_member,v_state,v_role;
    ELSE
      IF p_role IS NOT NULL THEN RAISE EXCEPTION 'Invalid revocation' USING ERRCODE='22023'; END IF;
      UPDATE worthkind_flow.staff_memberships m SET state='revoked',revoked_at=now()
        WHERE m.property_id=v_property AND m.identity_id=v_target
          AND m.state IN ('active','invited') AND m.role<>'owner'
          AND (m.role<>'manager' OR v_actor_role='owner')
        RETURNING m.id,m.state,m.role INTO v_member,v_state,v_role;
    END IF;
  END IF;
  IF v_member IS NULL THEN RAISE EXCEPTION 'Membership change unavailable' USING ERRCODE='P0002'; END IF;
  INSERT INTO worthkind_flow.staff_membership_events(property_id,membership_id,actor_identity_id,action)
    VALUES(v_property,v_member,v_actor,
      CASE p_action WHEN 'invite' THEN 'invited' WHEN 'accept' THEN 'activated' ELSE 'revoked' END);
  RETURN QUERY SELECT v_member,v_state,v_role;
END $$;

CREATE OR REPLACE FUNCTION worthkind_flow.ops_category_allowed(p_role text,p_category text)
RETURNS boolean LANGUAGE sql IMMUTABLE SET search_path=pg_catalog AS $$
 SELECT COALESCE(p_role IN ('owner','manager') OR
 (p_role='reception' AND p_category IN ('reception','general')) OR
 (p_role='housekeeping' AND p_category='housekeeping') OR
 (p_role='maintenance' AND p_category='maintenance') OR
 (p_role='it' AND p_category='it') OR
 (p_role='kitchen' AND p_category='kitchen') OR
 (p_role='finance' AND p_category='billing'),false)
$$;
COMMIT;
