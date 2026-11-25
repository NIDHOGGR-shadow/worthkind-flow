-- Worthkind Flow M1-A: PostgreSQL tenant and individual staff identity foundation.
-- REVIEW ONLY. Do not apply to a production database until owner-approved.
-- Requires an isolated database and a migration role with CREATE ROLE privileges.
-- GitHub CI applies this only to an ephemeral PostgreSQL service.
-- The existing FastAPI SQLite application is NOT switched by this migration.
BEGIN;

CREATE SCHEMA IF NOT EXISTS worthkind_flow;

DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wf_staff_runtime') THEN
    CREATE ROLE wf_staff_runtime NOLOGIN;
  END IF;
END
$role$;

REVOKE ALL ON SCHEMA worthkind_flow FROM PUBLIC;
GRANT USAGE ON SCHEMA worthkind_flow TO wf_staff_runtime;

CREATE TABLE worthkind_flow.organizations (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  legal_name text NOT NULL CHECK (length(btrim(legal_name)) BETWEEN 2 AND 240),
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','verified','suspended','closed')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE worthkind_flow.properties (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL REFERENCES worthkind_flow.organizations(id) ON DELETE RESTRICT,
  slug text NOT NULL UNIQUE CHECK (slug ~ '^[a-z0-9][a-z0-9-]{1,79}$'),
  display_name text NOT NULL CHECK (length(btrim(display_name)) BETWEEN 2 AND 240),
  time_zone text NOT NULL DEFAULT 'Africa/Lagos',
  status text NOT NULL DEFAULT 'pending'
    CHECK (status IN ('pending','verified','active','suspended','closed')),
  created_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (id, organization_id)
);
CREATE INDEX idx_wf_property_organization ON worthkind_flow.properties(organization_id);

-- External identity provider must authenticate the provider subject; no passwords
-- or session secrets are stored in this schema. Identity provisioning is privileged.
CREATE TABLE worthkind_flow.staff_identities (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  provider_subject text NOT NULL UNIQUE
    CHECK (length(btrim(provider_subject)) BETWEEN 8 AND 255),
  state text NOT NULL DEFAULT 'active' CHECK (state IN ('active','suspended','deleted')),
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE worthkind_flow.staff_memberships (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  organization_id uuid NOT NULL,
  property_id uuid NOT NULL,
  identity_id uuid NOT NULL REFERENCES worthkind_flow.staff_identities(id) ON DELETE RESTRICT,
  role text NOT NULL CHECK (role IN (
    'owner','manager','reception','housekeeping','maintenance','kitchen','finance'
  )),
  state text NOT NULL DEFAULT 'invited'
    CHECK (state IN ('invited','active','revoked')),
  invited_at timestamptz NOT NULL DEFAULT now(),
  activated_at timestamptz,
  revoked_at timestamptz,
  UNIQUE (property_id, identity_id),
  UNIQUE (id, property_id),
  FOREIGN KEY (property_id, organization_id)
    REFERENCES worthkind_flow.properties(id, organization_id) ON DELETE RESTRICT,
  CONSTRAINT membership_state_dates CHECK (
    (state = 'invited' AND activated_at IS NULL AND revoked_at IS NULL)
    OR (state = 'active' AND activated_at IS NOT NULL AND revoked_at IS NULL)
    OR (state = 'revoked' AND revoked_at IS NOT NULL)
  )
);
CREATE INDEX idx_wf_membership_actor ON worthkind_flow.staff_memberships(identity_id, property_id, state);

-- The first case table deliberately holds only status and fingerprint metadata;
-- customer contacts and free-text PII need an approved encryption/retention
-- design before their data migration. No synthetic hotel is seeded here.
CREATE TABLE worthkind_flow.guest_cases (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id uuid NOT NULL REFERENCES worthkind_flow.properties(id) ON DELETE RESTRICT,
  request_key text NOT NULL CHECK (length(request_key) BETWEEN 8 AND 100),
  payload_hash text NOT NULL CHECK (payload_hash ~ '^[0-9a-f]{64}$'),
  receipt_hash text NOT NULL CHECK (receipt_hash ~ '^[0-9a-f]{64}$'),
  kind text NOT NULL CHECK (kind IN (
    'booking','human','food','careers','supplier','events','support','general'
  )),
  state text NOT NULL DEFAULT 'queued'
    CHECK (state IN ('queued','claimed','responded','escalated','resolved','cancelled','disputed')),
  assigned_membership_id uuid,
  created_at timestamptz NOT NULL DEFAULT now(),
  updated_at timestamptz NOT NULL DEFAULT now(),
  UNIQUE (property_id, request_key),
  UNIQUE (id, property_id),
  FOREIGN KEY (assigned_membership_id, property_id)
    REFERENCES worthkind_flow.staff_memberships(id, property_id) ON DELETE RESTRICT
);
CREATE INDEX idx_wf_case_property_state ON worthkind_flow.guest_cases(property_id,state,created_at);

-- Audit + pending outbox schema: these are *not* actual delivered notifications.
CREATE TABLE worthkind_flow.case_audit_events (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id uuid NOT NULL,
  case_id uuid NOT NULL,
  actor_membership_id uuid,
  action text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (case_id, property_id)
    REFERENCES worthkind_flow.guest_cases(id, property_id) ON DELETE RESTRICT,
  FOREIGN KEY (actor_membership_id, property_id)
    REFERENCES worthkind_flow.staff_memberships(id, property_id) ON DELETE RESTRICT
);
CREATE TABLE worthkind_flow.event_outbox (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  property_id uuid NOT NULL,
  case_id uuid NOT NULL,
  event_type text NOT NULL,
  event_state text NOT NULL DEFAULT 'pending'
    CHECK (event_state IN ('pending','leased','accepted','failed','dead_letter')),
  attempts integer NOT NULL DEFAULT 0 CHECK (attempts >= 0),
  created_at timestamptz NOT NULL DEFAULT now(),
  FOREIGN KEY (case_id, property_id)
    REFERENCES worthkind_flow.guest_cases(id, property_id) ON DELETE RESTRICT
);
CREATE INDEX idx_wf_event_outbox_pending
  ON worthkind_flow.event_outbox(event_state,created_at)
  WHERE event_state IN ('pending','failed');

-- These trusted request attributes MUST be set by the API after verifying the
-- external authentication token and must NEVER be forwarded from client JSON.
-- Any database role holding unrestricted SQL access to the runtime connection
-- could forge a custom GUC. Therefore DB credentials remain SERVER-SIDE ONLY.
CREATE FUNCTION worthkind_flow.current_actor_id() RETURNS uuid
LANGUAGE sql STABLE
SET search_path = pg_catalog
AS $$
  SELECT nullif(current_setting('wf.actor_id', true), '')::uuid
$$;
REVOKE ALL ON FUNCTION worthkind_flow.current_actor_id() FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.current_actor_id() TO wf_staff_runtime;

-- RLS, including FORCE, stops accidental unscoped queries by the runtime role.
-- No INSERT/UPDATE/DELETE grants on any table to the staff runtime at this stage.
ALTER TABLE worthkind_flow.organizations ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.organizations FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.properties ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.properties FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_identities ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_identities FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_memberships ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.staff_memberships FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_cases ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.guest_cases FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.case_audit_events ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.case_audit_events FORCE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.event_outbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE worthkind_flow.event_outbox FORCE ROW LEVEL SECURITY;

-- Self-only identity/membership RLS avoids recursive policy dependencies.
CREATE POLICY wf_self_identity_read ON worthkind_flow.staff_identities
  FOR SELECT TO wf_staff_runtime
  USING (id = worthkind_flow.current_actor_id());
CREATE POLICY wf_self_membership_read ON worthkind_flow.staff_memberships
  FOR SELECT TO wf_staff_runtime
  USING (identity_id = worthkind_flow.current_actor_id());

CREATE POLICY wf_organization_staff_read ON worthkind_flow.organizations
  FOR SELECT TO wf_staff_runtime
  USING (EXISTS (
    SELECT 1 FROM worthkind_flow.staff_memberships m
    JOIN worthkind_flow.staff_identities si ON si.id = m.identity_id
    WHERE m.organization_id = organizations.id
      AND m.identity_id = worthkind_flow.current_actor_id()
      AND m.state = 'active' AND si.state = 'active'
  ));
CREATE POLICY wf_property_staff_read ON worthkind_flow.properties
  FOR SELECT TO wf_staff_runtime
  USING (EXISTS (
    SELECT 1 FROM worthkind_flow.staff_memberships m
    JOIN worthkind_flow.staff_identities si ON si.id = m.identity_id
    WHERE m.property_id = properties.id
      AND m.identity_id = worthkind_flow.current_actor_id()
      AND m.state = 'active' AND si.state = 'active'
  ));
CREATE POLICY wf_reception_case_read ON worthkind_flow.guest_cases
  FOR SELECT TO wf_staff_runtime
  USING (EXISTS (
    SELECT 1 FROM worthkind_flow.staff_memberships m
    JOIN worthkind_flow.staff_identities si ON si.id = m.identity_id
    JOIN worthkind_flow.properties p ON p.id = m.property_id
    WHERE m.property_id = guest_cases.property_id
      AND m.identity_id = worthkind_flow.current_actor_id()
      AND m.state = 'active' AND si.state = 'active'
      AND p.status = 'active'
      AND m.role IN ('owner','manager','reception')
  ));

-- Runtime staff can query their own identity, memberships, accessible property
-- and case metadata; provisioning and mutation require separate reviewed
-- service commands. Neither audit nor outbox is directly accessible.
REVOKE ALL ON ALL TABLES IN SCHEMA worthkind_flow FROM PUBLIC;
GRANT SELECT ON worthkind_flow.organizations,
  worthkind_flow.properties,
  worthkind_flow.staff_identities,
  worthkind_flow.staff_memberships,
  worthkind_flow.guest_cases TO wf_staff_runtime;

COMMIT;
