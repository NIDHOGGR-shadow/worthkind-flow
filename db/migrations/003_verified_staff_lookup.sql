-- M1 staff login bridge. Provider-neutral; issuer/audience/signature are verified
-- in the FastAPI layer BEFORE this lookup. Not production-applied.
BEGIN;

DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wf_auth_lookup') THEN
    CREATE ROLE wf_auth_lookup NOLOGIN;
  END IF;
END
$role$;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_auth_lookup;

-- A deliberately narrow source for the verified provider subject. The role has
-- no direct table access; this function belongs to the trusted DB migration
-- owner and must be reviewed under a dedicated, restricted owner for production.
CREATE FUNCTION worthkind_flow.resolve_staff_session(
  p_provider_subject text,
  p_property_slug text,
  p_action text
)
RETURNS TABLE (actor_id uuid, membership_id uuid, property_id uuid, membership_role text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  IF p_provider_subject IS NULL
    OR length(p_provider_subject) NOT BETWEEN 8 AND 255
    OR p_property_slug IS NULL
    OR p_action NOT IN ('case:read', 'case:claim', 'case:reply')
  THEN
    RAISE EXCEPTION 'Invalid staff permission lookup' USING ERRCODE = '22023';
  END IF;

  RETURN QUERY
    SELECT si.id, m.id, p.id, m.role
      FROM worthkind_flow.staff_identities AS si
      JOIN worthkind_flow.staff_memberships AS m ON m.identity_id = si.id
      JOIN worthkind_flow.properties AS p ON p.id = m.property_id
      JOIN worthkind_flow.organizations AS o ON o.id = p.organization_id
     WHERE si.provider_subject = p_provider_subject
       AND si.state = 'active'
       AND m.state = 'active'
       AND m.activated_at IS NOT NULL
       AND m.revoked_at IS NULL
       AND p.slug = p_property_slug
       AND p.status = 'active'
       AND o.status = 'verified'
       AND m.role IN ('owner', 'manager', 'reception');
  IF NOT FOUND THEN
    -- Do not reveal whether the subject or hotel exists to the caller.
    RAISE EXCEPTION 'Staff access denied' USING ERRCODE = '42501';
  END IF;
END;
$$;
REVOKE ALL ON FUNCTION worthkind_flow.resolve_staff_session(text,text,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.resolve_staff_session(text,text,text)
  TO wf_auth_lookup;
COMMIT;
