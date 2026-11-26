"""Hosted staging dependency probe. Does not provision or expose secrets."""
import os
import psycopg
from psycopg.conninfo import conninfo_to_dict
from guest_postgres import _configured_key,_keyring

ROLE_CONNECTIONS = (
    ("WF_GUEST_POSTGRES_DSN", "wf_guest_api"),
    ("WF_STAFF_POSTGRES_DSN", "wf_auth_lookup"),
    ("WF_STAFF_POSTGRES_DSN", "wf_staff_runtime"),
    ("WF_STAFF_POSTGRES_DSN", "wf_staff_commands"),
    ("WF_STAFF_LIFECYCLE_POSTGRES_DSN", "wf_staff_lifecycle"),
    ("WF_GUEST_QUOTA_POSTGRES_DSN", "wf_guest_quota"),
    ("WF_PROPERTY_CONFIG_POSTGRES_DSN", "wf_property_config"),
    ("WF_DOCUMENT_POSTGRES_DSN", "wf_document_store"),
    ("WF_OPERATIONS_POSTGRES_DSN", "wf_operations"),
    ("WF_PUBLIC_CONTENT_POSTGRES_DSN", "wf_public_content"),
)


OPTIONAL_PROVIDER_ROLES = (
    ("WF_PLATFORM_CRM_POSTGRES_DSN", "wf_platform_crm"),
    ("WF_PAYMENT_PROVIDER_POSTGRES_DSN", "wf_payment_provider"),
    ("WF_POS_PROVIDER_POSTGRES_DSN", "wf_pos_provider"),
    ("WF_PMS_PROVIDER_POSTGRES_DSN", "wf_pms_provider"),
    ("WF_AI_GATEWAY_POSTGRES_DSN", "wf_ai_gateway"),
    ("WF_AI_POLICY_POSTGRES_DSN", "wf_ai_policy"),
)


def staging_ready():
    try:
        if os.getenv("WF_IDENTITY_PROVIDER") != "supabase" or not os.getenv("WF_SUPABASE_URL") or not os.getenv("WF_SUPABASE_PUBLISHABLE_KEY"):
            return False
        if os.getenv("WF_ENABLE_PG_GUEST_API") != "1" or len(os.getenv("WF_GUEST_QUOTA_SECRET","")) < 32:
            return False
        if _keyring() is None:
            _configured_key()
        # An unconfigured provider is not a dependency of the native hotel engine.
        optional = tuple((env,role) for env,role in OPTIONAL_PROVIDER_ROLES if os.getenv(env))
        for env, role in ROLE_CONNECTIONS + optional:
            dsn = os.getenv(env)
            if not dsn:
                return False
            params = conninfo_to_dict(dsn)
            if params.get("sslmode") != "verify-full":
                return False
            # SQL role is a constant from ROLE_CONNECTIONS, never user input.
            with psycopg.connect(dsn,connect_timeout=2) as conn:
                with conn.transaction():
                    conn.execute("SET LOCAL statement_timeout = '2s'")
                    login = conn.execute("SELECT session_user,rolsuper,rolcreaterole,rolcreatedb,rolbypassrls,rolreplication,rolinherit FROM pg_roles WHERE rolname=session_user").fetchone()
                    if login is None or any(login[1:]):
                        return False
                    conn.execute("SET LOCAL ROLE " + role)
                    if conn.execute("SELECT current_user").fetchone()[0] != role:
                        return False
                    if not conn.execute("SELECT has_schema_privilege(current_user,'worthkind_flow','USAGE')").fetchone()[0]:
                        return False
        return True
    except (psycopg.Error,RuntimeError,ValueError):
        return False
