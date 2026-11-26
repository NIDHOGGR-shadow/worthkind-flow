"""Verified OIDC bearer identity + PostgreSQL property-scoped staff operations.

Development integration boundary only. No identity provider is provisioned here.
The issuer, audience and trusted public JWKS are configured server-side.
No untrusted JWT property/role claim is used for database authorization.
"""
import json
import os
from hashlib import sha256
from uuid import UUID

import jwt
import psycopg
from psycopg import errors
from guest_postgres import encrypt_json, decrypt_json
from supabase_identity import verified_supabase_subject, IdentityRejected, IdentityUnavailable


class StaffTokenRejected(ValueError):
    """Bearer token is absent, invalid, expired or untrusted."""


class StaffAuthConfigurationError(RuntimeError):
    """Trusted identity/database infrastructure has not been configured."""


class StaffPermissionDenied(PermissionError):
    """Identity has no current permission for the requested hotel."""


class StaffStorageUnavailable(RuntimeError):
    """Database could not give an authoritative result."""


def verified_provider_subject(authorization: str | None) -> str:
    """Verify RS256 signed token with pinned server-side public keys.

    Rejects unsigned/HMAC tokens, unknown kid, remote key URLs and untrusted
    claims. Never accepts roles or tenant authorization from token payload.
    """
    mode = os.getenv("WF_IDENTITY_PROVIDER", "oidc")
    if mode == "supabase":
        try:
            return verified_supabase_subject(authorization)
        except IdentityRejected:
            raise StaffTokenRejected("Bearer token rejected") from None
        except IdentityUnavailable:
            raise StaffAuthConfigurationError("Supabase identity unavailable") from None
    if mode != "oidc":
        raise StaffAuthConfigurationError("Unknown identity provider")
    if not authorization or not authorization.startswith("Bearer "):
        raise StaffTokenRejected("Bearer token required")
    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer" or not parts[1]:
        raise StaffTokenRejected("Bearer token required")

    issuer = os.getenv("WF_OIDC_ISSUER")
    audience = os.getenv("WF_OIDC_AUDIENCE")
    encoded_keys = os.getenv("WF_OIDC_JWKS_JSON")
    if not issuer or not audience or not encoded_keys:
        raise StaffAuthConfigurationError("Trusted OIDC issuer not configured")

    token = parts[1]
    try:
        header = jwt.get_unverified_header(token)
        if header.get("alg") != "RS256" or not isinstance(header.get("kid"), str):
            raise StaffTokenRejected("Untrusted token algorithm or key")
        jwks = json.loads(encoded_keys)
        if not isinstance(jwks, dict) or not isinstance(jwks.get("keys"), list):
            raise StaffAuthConfigurationError("Invalid trusted public key set")
        matches = [
            candidate for candidate in jwks["keys"]
            if isinstance(candidate, dict)
            and candidate.get("kid") == header["kid"]
            and candidate.get("kty") == "RSA"
            and candidate.get("alg", "RS256") == "RS256"
            and candidate.get("use", "sig") == "sig"
        ]
        if len(matches) != 1:
            raise StaffTokenRejected("Unrecognized trusted signing key")
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(matches[0]))
        claims = jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            issuer=issuer,
            audience=audience,
            options={"require": ["sub", "exp", "iat", "iss", "aud"]},
            leeway=15,
        )
        subject = claims.get("sub")
        if not isinstance(subject, str) or not 8 <= len(subject) <= 255:
            raise StaffTokenRejected("Invalid provider identity")
        return subject
    except StaffTokenRejected:
        raise
    except StaffAuthConfigurationError:
        raise
    except (jwt.PyJWTError, ValueError, KeyError, TypeError) as exc:
        raise StaffTokenRejected("Bearer token rejected") from exc


def staff_case_operation(
    provider_subject: str,
    slug: str,
    *,
    action: str,
    case_id: UUID | None = None,
    reply_message: str | None = None,
) -> dict:
    """Authorize from PostgreSQL and perform one permitted read/claim.

    Connection login must be a SERVER-ONLY role allowed to SET ROLE to the
    two narrowly scoped NOLOGIN roles; it must not be a browser credential.
    """
    dsn = os.getenv("WF_STAFF_POSTGRES_DSN")
    if not dsn:
        raise StaffAuthConfigurationError("Staff PostgreSQL connection not configured")
    if action not in {"case:read", "case:claim", "case:reply"}:
        raise StaffPermissionDenied("Unsupported staff action")
    if action in {"case:claim", "case:reply"} and case_id is None:
        raise StaffPermissionDenied("Case ID required")
    if action == "case:reply" and (not reply_message or not 2 <= len(reply_message) <= 3000):
        raise StaffPermissionDenied("Valid reply text required")
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_auth_lookup")
                verified = conn.execute(
                    "SELECT actor_id,membership_id,property_id,membership_role "
                    "FROM worthkind_flow.resolve_staff_session(%s,%s,%s)",
                    (provider_subject, slug, action),
                ).fetchone()
                if verified is None:
                    raise StaffPermissionDenied("Staff access denied")
                identity_id, member_id, property_id, role = verified
                if action == "case:read":
                    conn.execute("SET LOCAL ROLE wf_staff_runtime")
                    conn.execute(
                        "SELECT set_config('wf.actor_id', %s, true)",
                        (str(identity_id),),
                    )
                    records = conn.execute(
                        "SELECT id,kind,state,created_at,request_key,encrypted_guest_payload "
                        "FROM worthkind_flow.guest_cases "
                        "WHERE property_id=%s ORDER BY created_at DESC,id DESC LIMIT 100",
                        (property_id,),
                    ).fetchall()
                    cases = []
                    for row in records:
                        private = decrypt_json(
                            row[5], associated_data=f"wf:guest:{slug}:{row[4]}"
                        )
                        cases.append({
                            "id": str(row[0]), "kind": row[1],
                            "status": row[2], "created_at": row[3].isoformat(),
                            "customer_name": private.get("name") if private else None,
                            "contact": private.get("contact") if private else None,
                            "details": private.get("details") if private else None,
                        })
                    return {
                        "property": slug,
                        "staff_role": role,
                        "source": "postgres_case_metadata",
                        "cases": cases,
                        "case_contents_available": any(row[5] is not None for row in records),
                        "live_notifications": False,
                        "live_bookings": False,
                    }

                conn.execute("SET LOCAL ROLE wf_staff_commands")
                conn.execute(
                    "SELECT set_config('wf.actor_id', %s, true)",
                    (str(identity_id),),
                )
                if action == "case:claim":
                    changed = conn.execute(
                        "SELECT case_id,case_state FROM worthkind_flow.claim_guest_case(%s,%s)",
                        (property_id, case_id),
                    ).fetchone()
                else:
                    ciphertext = encrypt_json(
                        {"message": reply_message},
                        associated_data=f"wf:reply:{slug}:{case_id}",
                    )
                    changed = conn.execute(
                        "SELECT case_id,case_state "
                        "FROM worthkind_flow.record_case_reply(%s,%s,%s,%s)",
                        (property_id, case_id, ciphertext, sha256(reply_message.encode()).hexdigest()),
                    ).fetchone()
                return {
                    "case_id": str(changed[0]), "status": changed[1],
                    "property": slug, "source": "postgres_case_metadata",
                    "notification_delivery": "not_connected",
                }
    except errors.InsufficientPrivilege as exc:
        raise StaffPermissionDenied("Staff not authorized for this property") from exc
    except (errors.NoDataFound, errors.CheckViolation) as exc:
        raise StaffPermissionDenied("Case unavailable for this action") from exc
    except (psycopg.OperationalError, psycopg.InterfaceError) as exc:
        raise StaffStorageUnavailable("Staff database is unavailable") from exc
    except psycopg.Error as exc:
        raise StaffStorageUnavailable("Staff database could not process request") from exc
