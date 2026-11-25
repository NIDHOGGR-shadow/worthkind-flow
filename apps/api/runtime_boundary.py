"""Fail-closed runtime boundaries for the existing SQLite development service."""
import hmac
import json
from pathlib import Path
import sqlite3


class StaffConfigurationError(ValueError):
    """Invalid configuration; never include key material in the message."""


def validate_environment(raw):
    mode = raw.strip().casefold()
    if mode not in {"development", "test"}:
        raise RuntimeError("Unsupported WF_ENV: production readiness is not verified")
    return mode


def staff_key_matches(raw_config, slug, presented):
    try:
        config = json.loads(raw_config)
    except (ValueError, TypeError):
        raise StaffConfigurationError("Invalid staff key configuration") from None
    if not isinstance(config, dict) or any(
        not isinstance(k, str) or not k or not isinstance(v, str) or not v
        for k, v in config.items()
    ):
        raise StaffConfigurationError("Invalid staff key configuration")
    if len(set(config.values())) != len(config):
        raise StaffConfigurationError("Staff keys must be distinct across properties")
    expected = config.get(slug)
    if not expected or not isinstance(presented, str) or not presented:
        return False
    return hmac.compare_digest(expected.encode("utf-8"), presented.encode("utf-8"))


def sqlite_ready(database_path):
    """Read-only dependency probe; never create a database or expose its path."""
    required = {"properties", "cases", "audit", "outbox", "public_facts",
                "service_tickets", "dev_provider_delivery_state"}
    try:
        uri = Path(database_path).resolve().as_uri() + "?mode=ro"
        conn = sqlite3.connect(uri, uri=True, timeout=1)
        try:
            tables = {row[0] for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            )}
            return required.issubset(tables)
        finally:
            conn.close()
    except (OSError, ValueError, sqlite3.Error):
        return False
