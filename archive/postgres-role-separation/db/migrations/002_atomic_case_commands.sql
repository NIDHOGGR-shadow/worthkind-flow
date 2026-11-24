-- Worthkind Flow M1: provider-independent transactional case command functions.
-- Development review only. Apply 001 first, and never run on production without
-- an authorized migration and backup/rollback rehearsal.
BEGIN;

DO $role$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wf_guest_api') THEN
    CREATE ROLE wf_guest_api NOLOGIN;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'wf_staff_commands') THEN
    CREATE ROLE wf_staff_commands NOLOGIN;
  END IF;
END
$role$;

GRANT USAGE ON SCHEMA worthkind_flow TO wf_guest_api, wf_staff_commands;
-- No base-table reads/writes granted to these roles: only reviewed commands.
ALTER TABLE worthkind_flow.guest_cases
  ADD COLUMN encrypted_reply bytea,
  ADD COLUMN reply_hash text
  CHECK (reply_hash IS NULL OR reply_hash ~ '^[0-9a-f]{64}$');

-- Guest submission is accepted only for a source-verified active property.
-- Payload/receipt are hashed before this call; raw PII must not be passed in.
-- The normal guest API must first enforce input/rate/abuse limits.
CREATE FUNCTION worthkind_flow.create_guest_case(
  p_slug text,
  p_request_key text,
  p_payload_hash text,
  p_receipt_hash text,
  p_kind text
)
RETURNS TABLE (case_id uuid, case_state text, duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  v_property uuid;
  v_created uuid;
  v_existing record;
BEGIN
  SELECT p.id INTO v_property
    FROM worthkind_flow.properties AS p
    JOIN worthkind_flow.organizations AS o ON o.id = p.organization_id
   WHERE p.slug = p_slug AND p.status = 'active' AND o.status = 'verified';
  IF v_property IS NULL THEN
    RAISE EXCEPTION 'Property unavailable' USING ERRCODE = 'P0002';
  END IF;
  IF p_request_key IS NULL OR length(p_request_key) NOT BETWEEN 8 AND 100
     OR p_payload_hash IS NULL OR p_payload_hash !~ '^[0-9a-f]{64}$'
     OR p_receipt_hash IS NULL OR p_receipt_hash !~ '^[0-9a-f]{64}$'
     OR p_kind IS NULL OR p_kind NOT IN
       ('booking','human','food','careers','supplier','events','support','general')
  THEN
    RAISE EXCEPTION 'Invalid enquiry metadata' USING ERRCODE = '22023';
  END IF;

  INSERT INTO worthkind_flow.guest_cases (
    property_id, request_key, payload_hash, receipt_hash, kind
  ) VALUES (
    v_property, p_request_key, p_payload_hash, p_receipt_hash, p_kind
  )
  ON CONFLICT (property_id, request_key) DO NOTHING
  RETURNING id INTO v_created;

  IF v_created IS NULL THEN
    SELECT c.id, c.state, c.payload_hash, c.receipt_hash, c.kind
      INTO v_existing FROM worthkind_flow.guest_cases AS c
     WHERE c.property_id = v_property AND c.request_key = p_request_key;
    IF v_existing.id IS NULL THEN
      RAISE EXCEPTION 'Could not resolve concurrent request' USING ERRCODE = '40001';
    END IF;
    IF v_existing.payload_hash <> p_payload_hash
       OR v_existing.receipt_hash <> p_receipt_hash
       OR v_existing.kind <> p_kind
    THEN
      RAISE EXCEPTION 'Idempotency key already used with different proof'
      USING ERRCODE = '23505';
    END IF;
    RETURN QUERY SELECT v_existing.id, v_existing.state::text, TRUE;
    RETURN;
  END IF;

  INSERT INTO worthkind_flow.case_audit_events(property_id, case_id, action)
  VALUES (v_property, v_created, 'case_created');
  INSERT INTO worthkind_flow.event_outbox(property_id, case_id, event_type)
  VALUES (v_property, v_created, 'case_created');

  RETURN QUERY SELECT v_created, 'queued'::text, FALSE;
END;
$$;

-- Staff context is asserted by the trusted backend only AFTER JWT verification.
-- A public HTTP client must never choose wf.actor_id or obtain the DB password.
CREATE FUNCTION worthkind_flow.claim_guest_case(
  p_property_id uuid,
  p_case_id uuid
)
RETURNS TABLE (case_id uuid, case_state text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  v_membership uuid;
  v_changed uuid;
BEGIN
  SELECT m.id INTO v_membership
    FROM worthkind_flow.staff_memberships AS m
    JOIN worthkind_flow.staff_identities AS si ON si.id = m.identity_id
    JOIN worthkind_flow.properties AS p ON p.id = m.property_id
    JOIN worthkind_flow.organizations AS o ON o.id = p.organization_id
   WHERE m.property_id = p_property_id
     AND m.identity_id = worthkind_flow.current_actor_id()
     AND m.state = 'active'
     AND si.state = 'active'
     AND p.status = 'active'
     AND o.status = 'verified'
     AND m.role IN ('owner','manager','reception');
  IF v_membership IS NULL THEN
    RAISE EXCEPTION 'Not authorized for this hotel'
      USING ERRCODE = '42501';
  END IF;

  UPDATE worthkind_flow.guest_cases AS c
     SET state = 'claimed',
         assigned_membership_id = v_membership,
         updated_at = now()
   WHERE c.property_id = p_property_id
     AND c.id = p_case_id
     AND c.state = 'queued'
  RETURNING c.id INTO v_changed;
  IF v_changed IS NULL THEN
    RAISE EXCEPTION 'Case unavailable for claim'
      USING ERRCODE = 'P0002';
  END IF;

  INSERT INTO worthkind_flow.case_audit_events
    (property_id, case_id, actor_membership_id, action)
  VALUES (p_property_id, v_changed, v_membership, 'case_claimed');
  INSERT INTO worthkind_flow.event_outbox
    (property_id, case_id, event_type)
  VALUES (p_property_id, v_changed, 'case_claimed');
  RETURN QUERY SELECT v_changed, 'claimed'::text;
END;
$$;

-- Reply contents must be encrypted by the API before this command.
-- The DB only validates envelope non-emptiness, NOT cryptographic correctness.
-- No provider-delivery state is implied by committing this reply.
CREATE FUNCTION worthkind_flow.record_case_reply(
  p_property_id uuid,
  p_case_id uuid,
  p_encrypted_reply bytea,
  p_reply_hash text
)
RETURNS TABLE (case_id uuid, case_state text)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  v_membership uuid;
  v_changed uuid;
BEGIN
  IF p_encrypted_reply IS NULL OR length(p_encrypted_reply) < 16
     OR p_reply_hash IS NULL OR p_reply_hash !~ '^[0-9a-f]{64}$'
  THEN
    RAISE EXCEPTION 'Invalid encrypted reply metadata'
      USING ERRCODE = '22023';
  END IF;
  SELECT m.id INTO v_membership
    FROM worthkind_flow.staff_memberships AS m
    JOIN worthkind_flow.staff_identities AS si ON si.id = m.identity_id
    JOIN worthkind_flow.properties AS p ON p.id = m.property_id
    JOIN worthkind_flow.organizations AS o ON o.id = p.organization_id
   WHERE m.property_id = p_property_id
     AND m.identity_id = worthkind_flow.current_actor_id()
     AND m.state = 'active'
     AND si.state = 'active'
     AND p.status = 'active' AND o.status = 'verified'
     AND m.role IN ('owner','manager','reception');
  IF v_membership IS NULL THEN
    RAISE EXCEPTION 'Not authorized for this hotel'
      USING ERRCODE = '42501';
  END IF;

  UPDATE worthkind_flow.guest_cases AS c
     SET state = 'responded',
         encrypted_reply = p_encrypted_reply,
         reply_hash = p_reply_hash,
         updated_at = now()
   WHERE c.property_id = p_property_id
     AND c.id = p_case_id
     AND c.state = 'claimed'
     AND c.assigned_membership_id = v_membership
  RETURNING c.id INTO v_changed;
  IF v_changed IS NULL THEN
    RAISE EXCEPTION 'Case not owned or no longer claimable'
      USING ERRCODE = 'P0002';
  END IF;

  INSERT INTO worthkind_flow.case_audit_events
    (property_id, case_id, actor_membership_id, action)
  VALUES (p_property_id, v_changed, v_membership, 'case_responded');
  INSERT INTO worthkind_flow.event_outbox
    (property_id, case_id, event_type)
  VALUES (p_property_id, v_changed, 'case_responded');
  RETURN QUERY SELECT v_changed, 'responded'::text;
END;
$$;

REVOKE ALL ON FUNCTION worthkind_flow.create_guest_case(text,text,text,text,text) FROM PUBLIC;
REVOKE ALL ON FUNCTION worthkind_flow.claim_guest_case(uuid,uuid) FROM PUBLIC;
REVOKE ALL ON FUNCTION worthkind_flow.record_case_reply(uuid,uuid,bytea,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.create_guest_case(text,text,text,text,text)
  TO wf_guest_api;
GRANT EXECUTE ON FUNCTION worthkind_flow.claim_guest_case(uuid,uuid),
  worthkind_flow.record_case_reply(uuid,uuid,bytea,text)
  TO wf_staff_commands;

COMMIT;
