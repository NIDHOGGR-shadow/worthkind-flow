"""Read-only database role preflight for Flow. No credentials are printed."""
import argparse
import json
import os
import psycopg

ROLES = ("wf_auth_lookup","wf_document_store","wf_event_projector","wf_guest_api",
         "wf_guest_quota","wf_hotel_provisioner","wf_property_config","wf_staff_commands",
         "wf_staff_lifecycle","wf_staff_runtime","wf_operations","wf_public_content","wf_payment_provider","wf_pos_provider","wf_pms_provider","wf_pos_sync","wf_ai_gateway","wf_ai_policy","wf_ai_automation")

def inspect(conn):
    result={}
    for role in ROLES:
        attrs=conn.execute("SELECT rolcanlogin,rolsuper,rolcreaterole,rolcreatedb,rolbypassrls FROM pg_roles WHERE rolname=%s",(role,)).fetchone()
        if attrs is None or any(attrs):
            result[role]="missing_or_excessive_role_privileges"
            continue
        tables=conn.execute("""SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
            WHERE n.nspname='public' AND c.relkind IN ('r','v','p','m')
            AND (has_table_privilege(%s,c.oid,'SELECT') OR has_table_privilege(%s,c.oid,'INSERT')
            OR has_table_privilege(%s,c.oid,'UPDATE') OR has_table_privilege(%s,c.oid,'DELETE'))""",(role,)*4).fetchone()[0]
        functions=conn.execute("""SELECT count(*) FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace
            WHERE n.nspname='public' AND p.prosecdef AND has_function_privilege(%s,p.oid,'EXECUTE')""",(role,)).fetchone()[0]
        result[role]="pass" if tables==0 and functions==0 else "unrelated_public_access"
    return result

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.parse_args()
    dsn=os.getenv("WF_DB_PREFLIGHT_DSN")
    if not dsn:
        parser.error("WF_DB_PREFLIGHT_DSN is required")
    try:
        with psycopg.connect(dsn,connect_timeout=5) as conn:
            conn.execute("SET TRANSACTION READ ONLY")
            result=inspect(conn)
    except psycopg.Error:
        print(json.dumps({"status":"database_unavailable"}))
        return 2
    print(json.dumps(result,indent=2))
    return 0 if all(v=="pass" for v in result.values()) else 1

if __name__=="__main__":
    raise SystemExit(main())
