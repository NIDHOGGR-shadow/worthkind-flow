-- Close the direct staff read path when an organization is suspended.
-- All checks still depend on a verified server-side actor and private SQL roles.
BEGIN;
ALTER POLICY wf_organization_staff_read ON worthkind_flow.organizations
  USING (status = 'verified' AND EXISTS (
    SELECT 1 FROM worthkind_flow.staff_memberships m
    JOIN worthkind_flow.staff_identities si ON si.id = m.identity_id
    WHERE m.organization_id = organizations.id
      AND m.identity_id = worthkind_flow.current_actor_id()
      AND m.state = 'active' AND si.state = 'active'
  ));
ALTER POLICY wf_property_staff_read ON worthkind_flow.properties
  USING (status = 'active' AND EXISTS (
    SELECT 1 FROM worthkind_flow.staff_memberships m
    JOIN worthkind_flow.staff_identities si ON si.id = m.identity_id
    JOIN worthkind_flow.organizations o ON o.id = m.organization_id
    WHERE m.property_id = properties.id
      AND m.identity_id = worthkind_flow.current_actor_id()
      AND m.state = 'active' AND si.state = 'active'
      AND o.status = 'verified'
  ));
ALTER POLICY wf_reception_case_read ON worthkind_flow.guest_cases
  USING (EXISTS (
    SELECT 1 FROM worthkind_flow.staff_memberships m
    JOIN worthkind_flow.staff_identities si ON si.id = m.identity_id
    JOIN worthkind_flow.properties p ON p.id = m.property_id
    JOIN worthkind_flow.organizations o ON o.id = m.organization_id
    WHERE m.property_id = guest_cases.property_id
      AND m.identity_id = worthkind_flow.current_actor_id()
      AND m.state = 'active' AND si.state = 'active'
      AND p.status = 'active' AND o.status = 'verified'
      AND m.role IN ('owner','manager','reception')
  ));
COMMIT;
