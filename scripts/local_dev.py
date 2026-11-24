#!/usr/bin/env python3
"""Local-only Worthkind Flow runner. Never contacts real hotel/AI/payment providers.

Usage (from repository root):
  python projects/worthkind-flow/scripts/local_dev.py start --seed-demo
  python projects/worthkind-flow/scripts/local_dev.py seed
  python projects/worthkind-flow/scripts/local_dev.py doctor

Local records and development keys live in projects/worthkind-flow/.local/
which is gitignored. This is not intended for network or production exposure.
"""
import argparse
import json
import os
from pathlib import Path
import secrets
import stat
import sys


PROJECT = Path(__file__).resolve().parents[1]
API = PROJECT / "apps" / "api"
DEFAULT_STATE = PROJECT / ".local"
PROPERTIES = ("demo-hotel", "demo-hotel-two")
CATEGORIES = ("booking", "human", "food", "events", "careers", "supplier", "support", "general")
DETAILS = {
    "booking": "Please explain the booking options for the requested dates; this is not a confirmed room.",
    "human": "I want to speak with reception directly, without any AI assistance.",
    "food": "Please show me the restaurant options and connect me with hotel dining staff.",
    "events": "I want to ask the events team about a meeting venue and dates.",
    "careers": "I want to enquire about potential job vacancies and the application process.",
    "supplier": "I would like to introduce my company to the hotel procurement team.",
    "support": "Please help with an unanswered guest service question.",
    "general": "I have a question for the hotel and would appreciate a human response.",
}


def ensure_safe_environment():
    if os.environ.get("WF_ENV", "development") != "development":
        raise RuntimeError("Local runner refuses non-development WF_ENV.")
    if os.environ.get("WF_DATABASE_PATH"):
        raise RuntimeError(
            "Local runner refuses WF_DATABASE_PATH override; unset it to use the isolated .local folder."
        )


def local_settings(state_dir=DEFAULT_STATE):
    """Generate strong per-property development secrets once, not on every start."""
    ensure_safe_environment()
    state_dir = Path(state_dir)
    if state_dir.is_symlink():
        raise RuntimeError("Refusing symlinked local state directory.")
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    if os.name == "posix":
        os.chmod(state_dir, 0o700)

    key_file = state_dir / "staff-keys.json"
    if key_file.is_symlink():
        raise RuntimeError("Refusing symlinked staff key file.")
    if key_file.exists():
        if not key_file.is_file():
            raise RuntimeError("Staff key location is not a regular file.")
        if os.name == "posix" and stat.S_IMODE(key_file.stat().st_mode) & 0o077:
            raise RuntimeError("Staff key file is too permissive; restrict it to owner-only.")
        keys = json.loads(key_file.read_text(encoding="utf-8"))
        if set(keys) != set(PROPERTIES) or not all(
            isinstance(keys[p], str) and len(keys[p]) >= 32 for p in PROPERTIES
        ):
            raise RuntimeError("Invalid local staff key file. Do not overwrite it silently.")
    else:
        keys = {property_slug: secrets.token_urlsafe(32) for property_slug in PROPERTIES}
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        fd = os.open(key_file, flags, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(keys, stream, indent=2, sort_keys=True)
            stream.write("\n")

    database_file = state_dir / "worthkind-flow-dev.sqlite3"
    if database_file.is_symlink():
        raise RuntimeError("Refusing symlinked local SQLite file.")
    os.environ["WF_ENV"] = "development"
    os.environ["WF_DATABASE_PATH"] = str(database_file)
    os.environ["WF_DEV_STAFF_KEYS_JSON"] = json.dumps(keys)
    return database_file, keys


def import_api():
    if str(API) not in sys.path:
        sys.path.insert(0, str(API))
    try:
        import main  # pylint: disable=import-outside-toplevel
    except ImportError as exc:
        raise RuntimeError(
            "Install local Python dependencies first: "
            "python -m pip install -r projects/worthkind-flow/apps/api/requirements-dev.txt"
        ) from exc
    return main


def seed_synthetic_cases():
    """Populate ONLY local SQLite with a repeatable, clearly synthetic request queue."""
    from fastapi.testclient import TestClient

    main = import_api()
    inserted = 0
    with TestClient(main.app) as client:
        keys = json.loads(os.environ["WF_DEV_STAFF_KEYS_JSON"])
        for slug in PROPERTIES:
            for category in CATEGORIES:
                # Stable seed keys make multiple runs idempotent. All emails are .invalid.
                seed_key = f"seed_{slug}_{category}_20261119"
                proof = ("synthetic-local-receipt-" + slug + "-" + category).ljust(40, "Z")
                result = client.post(
                    f"/api/properties/{slug}/enquiries",
                    json={
                        "request_key": seed_key, "receipt_token": proof,
                        "kind": category, "name": f"Demo {category.title()} Visitor",
                        "contact": "example@guest.invalid", "details": DETAILS[category],
                    },
                )
                if result.status_code != 201:
                    raise RuntimeError(f"Cannot seed {slug}/{category}: {result.status_code}")
                payload = result.json()
                if not payload.get("duplicate"):
                    inserted += 1
                case_id = payload["case_id"]
                if category in ("food", "events") and payload["status"] == "queued":
                    base = f"/api/properties/{slug}/staff/enquiries/{case_id}"
                    headers = {"X-Staff-Key": keys[slug]}
                    claim = client.post(base + "/claim", headers=headers)
                    if claim.status_code != 200:
                        raise RuntimeError(f"Unable to seed claimed case: {claim.status_code}")
                    if category == "events":
                        reply = client.post(
                            base + "/respond",
                            headers=headers,
                            json={"message": "Synthetic response recorded for local UI testing. No external message was sent."},
                        )
                        if reply.status_code != 200:
                            raise RuntimeError(f"Unable to seed replied case: {reply.status_code}")
    return inserted


def display_keys(keys):
    print("\nLOCAL DEVELOPMENT STAFF KEYS (never use with real hotel data):")
    for property_slug in PROPERTIES:
        print(f"  {property_slug}: {keys[property_slug]}")
    print("Use the displayed key on http://127.0.0.1:8765/staff (or your selected port).")
    print("These secrets are saved only to gitignored .local/staff-keys.json.")


def main():
    parser = argparse.ArgumentParser(description="Worthkind Flow SQLite development server (the product remains a connected web app).")
    commands = parser.add_subparsers(dest="command", required=True)
    start = commands.add_parser("start", help="Run the local app bound to 127.0.0.1 only.")
    start.add_argument("--port", type=int, default=8765)
    start.add_argument("--seed-demo", action="store_true", help="Add 16 synthetic enquiries once.")
    commands.add_parser("seed", help="Seed synthetic SQLite enquiries without starting a server.")
    commands.add_parser("doctor", help="Validate and show the local development configuration.")
    for command in commands.choices.values():
        command.add_argument("--state-dir", type=Path, default=DEFAULT_STATE,
                             help="Isolated SQLite database and generated demo key directory")
    args = parser.parse_args()

    if args.command == "start" and not 1024 <= args.port <= 65535:
        parser.error("--port must be between 1024 and 65535")

    database_file, keys = local_settings(args.state_dir)
    print(f"Local SQLite: {database_file}")
    if args.command in ("seed", "start") and (args.command == "seed" or args.seed_demo):
        count = seed_synthetic_cases()
        print(f"Added {count} new synthetic cases; repeated runs do not duplicate existing cases.")
    display_keys(keys)
    if args.command == "doctor":
        import_api()
        print("API import successful. No external API, database or payment provider connected.")
    elif args.command == "start":
        import uvicorn
        api = import_api()
        print(f"\nGuest demo: http://127.0.0.1:{args.port}/")
        print(f"Staff demo: http://127.0.0.1:{args.port}/staff")
        print("Local machine only; not suitable for customers, open internet or production.")
        uvicorn.run(api.app, host="127.0.0.1", port=args.port, reload=False, access_log=False)


if __name__ == "__main__":
    main()
