"""Development-only encrypted guest enquiry storage in PostgreSQL.

The data encryption key stays on the server. No raw guest content is placed
in the database, audit table, event outbox or logs. Not production-ready:
key rotation, KMS, retention, abuse limits and real hotel approvals are gated.
"""
import base64
from hashlib import sha256
import json
import os
import secrets
from uuid import UUID

from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import psycopg
from psycopg import errors


class GuestStorageNotConfigured(RuntimeError):
    pass


class GuestRecordUnavailable(LookupError):
    pass


class GuestRequestConflict(ValueError):
    pass


class GuestStorageError(RuntimeError):
    pass


def _configured_key() -> bytes:
    encoded = os.getenv("WF_DATA_KEY_B64")
    if not encoded:
        raise GuestStorageNotConfigured("Encryption key is not configured")
    try:
        key = base64.b64decode(encoded, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise GuestStorageNotConfigured("Encryption key is invalid") from exc
    if len(key) != 32:
        raise GuestStorageNotConfigured("Encryption key must be exactly 32 bytes")
    return key


def encrypt_json(value: dict, *, associated_data: str) -> bytes:
    nonce = secrets.token_bytes(12)
    plaintext = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return nonce + AESGCM(_configured_key()).encrypt(
        nonce, plaintext, associated_data.encode("utf-8")
    )


def decrypt_json(blob: bytes | None, *, associated_data: str) -> dict | None:
    if blob is None:
        return None
    if len(blob) < 29:
        raise GuestStorageError("Stored payload is unavailable")
    try:
        data = AESGCM(_configured_key()).decrypt(
            blob[:12], blob[12:], associated_data.encode("utf-8")
        )
        result = json.loads(data)
    except GuestStorageNotConfigured:
        raise
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        raise GuestStorageError("Stored payload could not be authenticated") from exc
    except Exception as exc:
        # Includes AES-GCM InvalidTag; never include ciphertext or guest data.
        raise GuestStorageError("Stored payload could not be authenticated") from exc
    if not isinstance(result, dict):
        raise GuestStorageError("Stored payload has invalid format")
    return result


def _guest_dsn() -> str:
    if os.getenv("WF_ENABLE_PG_GUEST_API") != "1":
        raise GuestStorageNotConfigured("Guest PostgreSQL path not enabled")
    dsn = os.getenv("WF_GUEST_POSTGRES_DSN")
    if not dsn:
        raise GuestStorageNotConfigured("Guest PostgreSQL database not configured")
    return dsn


def submit_guest_enquiry(slug: str, body: dict) -> dict:
    receipt = body["receipt_token"]
    key = body["request_key"]
    data = {k: body[k] for k in ("request_key", "kind", "name", "contact", "details")}
    fingerprint = sha256(json.dumps(data, sort_keys=True).encode()).hexdigest()
    proof_hash = sha256(receipt.encode()).hexdigest()
    encrypted = encrypt_json(
        {k: body[k] for k in ("name", "contact", "details")},
        associated_data=f"wf:guest:{slug}:{key}",
    )
    try:
        with psycopg.connect(_guest_dsn(), connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_guest_api")
                case_id, state, duplicate = conn.execute(
                    "SELECT * FROM worthkind_flow.create_encrypted_guest_case(%s,%s,%s,%s,%s,%s)",
                    (slug, key, fingerprint, proof_hash, body["kind"], encrypted),
                ).fetchone()
        return {
            "case_id": str(case_id),
            "receipt_token": receipt,
            "status": state,
            "duplicate": duplicate,
            "source": "worthkind_postgres_enquiry",
            "message": "Hotel enquiry recorded; no room, order, payment or staff reply is confirmed.",
        }
    except errors.UniqueViolation as exc:
        raise GuestRequestConflict("This request key was reused with different details") from exc
    except errors.NoDataFound as exc:
        raise GuestRecordUnavailable("Hotel or request unavailable") from exc
    except (psycopg.Error, psycopg.InterfaceError) as exc:
        raise GuestStorageError("Unable to store enquiry") from exc


def guest_case_status(slug: str, case_id: UUID, receipt_token: str) -> dict:
    proof_hash = sha256(receipt_token.encode()).hexdigest()
    try:
        with psycopg.connect(_guest_dsn(), connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_guest_api")
                row = conn.execute(
                    "SELECT * FROM worthkind_flow.read_case_with_receipt(%s,%s,%s)",
                    (slug, case_id, proof_hash),
                ).fetchone()
        if row is None:
            raise GuestRecordUnavailable("Case not found")
        recorded_reply = decrypt_json(
            row[3],
            associated_data=f"wf:reply:{slug}:{case_id}",
        )
        return {
            "case_id": str(row[0]),
            "status": row[1],
            "kind": row[2],
            "staff_reply": recorded_reply.get("message") if recorded_reply else None,
            "delivery_state": "not_connected",
            "booking_confirmed": False,
        }
    except errors.NoDataFound as exc:
        raise GuestRecordUnavailable("Case not found") from exc
    except (psycopg.Error, psycopg.InterfaceError) as exc:
        raise GuestStorageError("Unable to check enquiry") from exc
