BEGIN;
-- Verified provider identity only; invited memberships are discoverable but confer no access.
CREATE FUNCTION worthkind_flow.list_staff_properties(p_subject text,p_after text,p_limit integer)
RETURNS TABLE(property_id uuid,slug text,display_name text,time_zone text,membership_role text,membership_state text)
LANGUAGE plpgsql STABLE SECURITY DEFINER SET search_path=pg_catalog,pg_temp AS $$
BEGIN
 IF p_subject IS NULL OR length(p_subject) NOT BETWEEN 8 AND 255 OR p_limit IS NULL OR p_limit NOT BETWEEN 1 AND 101
 OR (p_after IS NOT NULL AND p_after !~ '^[a-z0-9][a-z0-9-]{1,79}$') THEN
  RAISE EXCEPTION 'Invalid property discovery request' USING ERRCODE='22023';
 END IF;
 RETURN QUERY SELECT p.id,p.slug,p.display_name,p.time_zone,m.role,m.state
 FROM worthkind_flow.staff_identities i
 JOIN worthkind_flow.staff_memberships m ON m.identity_id=i.id
 JOIN worthkind_flow.properties p ON p.id=m.property_id AND p.organization_id=m.organization_id
 JOIN worthkind_flow.organizations o ON o.id=p.organization_id
 WHERE i.provider_subject=p_subject AND i.state='active' AND m.state IN ('active','invited')
 AND p.status='active' AND o.status='verified' AND (p_after IS NULL OR p.slug>p_after)
 ORDER BY p.slug LIMIT p_limit;
END $$;
REVOKE ALL ON FUNCTION worthkind_flow.list_staff_properties(text,text,integer) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.list_staff_properties(text,text,integer) TO wf_operations;
COMMIT;
