"""Staff membership endpoints; provider identity creation/email delivery are separate."""
import os

import psycopg
from psycopg import errors
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field
from typing import Literal
from staff_oidc import verified_provider_subject, StaffTokenRejected, StaffAuthConfigurationError


class Invite(BaseModel):
    provider_subject: str = Field(min_length=8, max_length=255)
    role: Literal["manager", "reception", "housekeeping", "maintenance", "kitchen", "finance", "it", "hr", "events", "procurement"]


class Revoke(BaseModel):
    provider_subject: str = Field(min_length=8, max_length=255)


def change_membership(slug, authorization, action, target=None, role=None):
    try:
        subject = verified_provider_subject(authorization)
    except StaffTokenRejected:
        raise HTTPException(401, "Bearer token rejected", headers={"WWW-Authenticate": "Bearer"}) from None
    except StaffAuthConfigurationError:
        raise HTTPException(503, "Staff identity not configured") from None
    dsn = os.getenv("WF_STAFF_LIFECYCLE_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503, "Staff lifecycle not configured")
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_staff_lifecycle")
                row = conn.execute(
                    "SELECT * FROM worthkind_flow.change_staff_membership(%s,%s,%s,%s,%s)",
                    (subject, slug, action, target, role)
                ).fetchone()
        return {"membership_id": str(row[0]), "state": row[1], "role": row[2]}
    except errors.InsufficientPrivilege:
        raise HTTPException(403, "Membership access denied") from None
    except errors.NoDataFound:
        raise HTTPException(409, "Membership change unavailable") from None
    except errors.InvalidParameterValue:
        raise HTTPException(422, "Invalid membership command") from None
    except psycopg.Error:
        raise HTTPException(503, "Staff lifecycle unavailable") from None


def install_staff_lifecycle_routes(app):
    @app.post("/api/v1/properties/{slug}/staff/memberships/invite", status_code=201)
    def invite(slug: str, body: Invite, authorization: str | None = Header(None)):
        return change_membership(slug, authorization, "invite", body.provider_subject, body.role)

    @app.post("/api/v1/properties/{slug}/staff/memberships/accept")
    def accept(slug: str, authorization: str | None = Header(None)):
        return change_membership(slug, authorization, "accept")

    @app.post("/api/v1/properties/{slug}/staff/memberships/revoke")
    def revoke(slug: str, body: Revoke, authorization: str | None = Header(None)):
        return change_membership(slug, authorization, "revoke", body.provider_subject)
