-- Worthkind Flow M1 encrypted synthetic guest case loop.
-- Development only. Real PII collection requires key management, retention,
-- abuse controls, privacy approval and a real hotel operator contract.
BEGIN;

ALTER TABLE worthkind_flow.guest_cases ADD COLUMN encrypted_guest_payload bytea;

CREATE FUNCTION worthkind_flow.create_encrypted_guest_case(
  p_slug text,
  p_request_key text,
  p_payload_hash text,
  p_receipt_hash text,
  p_kind text,
  p_encrypted_payload bytea
)
RETURNS TABLE (case_id uuid, case_state text, duplicate boolean)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
DECLARE
  v_id uuid;
  v_state text;
  v_duplicate boolean;
  v_stored_payload bytea;
BEGIN
  -- AES-GCM ciphertext contains nonce (12 bytes), tag (16 bytes) and data.
  -- Actual cryptographic validity is enforced in the application.
  IF p_encrypted_payload IS NULL OR length(p_encrypted_payload) < 29 THEN
    RAISE EXCEPTION 'Encrypted guest content required' USING ERRCODE = '22023';
  END IF;
  SELECT c.case_id,c.case_state,c.duplicate
    INTO v_id,v_state,v_duplicate
    FROM worthkind_flow.create_guest_case(
      p_slug,p_request_key,p_payload_hash,p_receipt_hash,p_kind
    ) AS c;

  IF NOT v_duplicate THEN
    UPDATE worthkind_flow.guest_cases AS gc
       SET encrypted_guest_payload = p_encrypted_payload
     WHERE gc.id = v_id AND gc.encrypted_guest_payload IS NULL;
  ELSE
    SELECT gc.encrypted_guest_payload INTO v_stored_payload
      FROM worthkind_flow.guest_cases AS gc WHERE gc.id = v_id;
    IF v_stored_payload IS NULL THEN
      RAISE EXCEPTION 'Existing request requires manual migration'
        USING ERRCODE = 'P0002';
    END IF;
  END IF;
  RETURN QUERY SELECT v_id,v_state,v_duplicate;
END;
$$;
REVOKE ALL ON FUNCTION worthkind_flow.create_encrypted_guest_case(
  text,text,text,text,text,bytea
) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.create_encrypted_guest_case(
  text,text,text,text,text,bytea
) TO wf_guest_api;

-- Proof-aware guest status. Never exposes receipt hashes, contact or source
-- ciphertext from another case without possessing that specific 256-bit proof.
CREATE FUNCTION worthkind_flow.read_case_with_receipt(
  p_slug text,
  p_case_id uuid,
  p_receipt_hash text
)
RETURNS TABLE (case_id uuid, case_state text, case_kind text, encrypted_reply bytea)
LANGUAGE plpgsql SECURITY DEFINER
SET search_path = pg_catalog, pg_temp
AS $$
BEGIN
  IF p_receipt_hash IS NULL OR p_receipt_hash !~ '^[0-9a-f]{64}$' THEN
    RAISE EXCEPTION 'Case not found' USING ERRCODE = 'P0002';
  END IF;

  RETURN QUERY
    SELECT c.id,c.state,c.kind,c.encrypted_reply
      FROM worthkind_flow.guest_cases AS c
      JOIN worthkind_flow.properties AS p ON p.id = c.property_id
     WHERE c.id = p_case_id AND p.slug = p_slug
       AND c.receipt_hash = p_receipt_hash;
  IF NOT FOUND THEN
    RAISE EXCEPTION 'Case not found' USING ERRCODE = 'P0002';
  END IF;
END;
$$;
REVOKE ALL ON FUNCTION worthkind_flow.read_case_with_receipt(text,uuid,text) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION worthkind_flow.read_case_with_receipt(text,uuid,text)
  TO wf_guest_api;

COMMIT;
