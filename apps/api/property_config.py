"""Hotel configuration API, with verified identity and optimistic concurrency."""
import os
import psycopg
from psycopg import errors
from fastapi import Header, HTTPException
from pydantic import BaseModel, Field, StrictBool
from staff_oidc import verified_provider_subject, StaffTokenRejected, StaffAuthConfigurationError


class SettingsUpdate(BaseModel):
    revision: int = Field(ge=1)
    guest_enquiries_enabled: StrictBool


def property_settings(slug, authorization, revision=None, enabled=None):
    try:
        subject = verified_provider_subject(authorization)
    except StaffTokenRejected:
        raise HTTPException(401, "Bearer token rejected", headers={"WWW-Authenticate":"Bearer"}) from None
    except StaffAuthConfigurationError:
        raise HTTPException(503, "Identity unavailable") from None
    dsn = os.getenv("WF_PROPERTY_CONFIG_POSTGRES_DSN")
    if not dsn:
        raise HTTPException(503, "Property configuration unavailable")
    try:
        with psycopg.connect(dsn, connect_timeout=5) as conn:
            with conn.transaction():
                conn.execute("SET LOCAL ROLE wf_property_config")
                row = conn.execute("SELECT * FROM worthkind_flow.manage_property_settings(%s,%s,%s,%s)",
                                   (subject,slug,revision,enabled)).fetchone()
        if row is None:
            raise HTTPException(404, "Property settings unavailable")
        return {"guest_enquiries_enabled": row[0], "ai_enabled": row[1], "revision": row[2]}
    except errors.InsufficientPrivilege:
        raise HTTPException(403, "Property access denied") from None
    except errors.SerializationFailure:
        raise HTTPException(409, "Settings revision conflict") from None
    except psycopg.Error:
        raise HTTPException(503, "Property configuration unavailable") from None


def install_property_config_routes(app):
    @app.get("/api/v1/properties/{slug}/staff/settings")
    def read(slug: str, authorization: str | None = Header(None)):
        return property_settings(slug,authorization)

    @app.put("/api/v1/properties/{slug}/staff/settings")
    def update(slug: str, body: SettingsUpdate, authorization: str | None = Header(None)):
        return property_settings(slug,authorization,body.revision,body.guest_enquiries_enabled)
