"""Private operator CLI for verified hotel onboarding and identity registration."""
import argparse
import os
import sys
import psycopg

COMMANDS = {
    "register": "SELECT worthkind_flow.register_hotel(%s,%s,%s,%s,%s)",
    "activate": "SELECT worthkind_flow.activate_hotel(%s,%s,%s,%s)",
    "identity": "SELECT worthkind_flow.register_staff_identity(%s,%s,%s)",
    "payments": "SELECT worthkind_flow.configure_hotel_payments(%s,%s,%s,%s,%s::boolean)",
    "cloudbeds": "SELECT worthkind_flow.configure_cloudbeds(%s,%s,%s,%s,%s::boolean)",
    "native-booking": "SELECT worthkind_flow.configure_native_bookings(%s,%s,%s::boolean)",
}


def run_command(dsn, command, values):
    with psycopg.connect(dsn, connect_timeout=5) as conn:
        with conn.transaction():
            conn.execute("SET LOCAL ROLE wf_hotel_provisioner")
            return conn.execute(COMMANDS[command], values).fetchone()[0]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, fields in (
        ("register", ["legal_name","slug","display_name","timezone","operator"]),
        ("activate", ["slug","owner_subject","operator","evidence"]),
        ("identity", ["subject","operator","evidence"]),
        ("payments", ["slug","alias","mode","evidence","enabled"]),
        ("cloudbeds", ["slug","external_property_id","alias","evidence","enabled"]),
        ("native-booking", ["slug","evidence","enabled"]),
    ):
        p = sub.add_parser(name)
        for field in fields:
            p.add_argument(field)
        p.set_defaults(fields=fields)
    args = parser.parse_args()
    dsn = os.getenv("WF_HOTEL_PROVISIONER_POSTGRES_DSN")
    if not dsn:
        parser.error("Provisioner database connection is required")
    try:
        print(run_command(dsn, args.command, [getattr(args, f) for f in args.fields]))
    except psycopg.Error:
        print("Provisioning failed; no changes committed", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
