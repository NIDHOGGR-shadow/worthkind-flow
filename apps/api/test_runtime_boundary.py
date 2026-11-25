import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from runtime_boundary import (
    StaffConfigurationError, sqlite_ready, staff_key_matches, validate_environment,
)


class RuntimeBoundaryTests(unittest.TestCase):
    def test_environment_fail_closed(self):
        for value in ("production", " Production ", "PRODUCTION", "staging", "", "prod"):
            with self.subTest(value=value), self.assertRaises(RuntimeError):
                validate_environment(value)
        self.assertEqual(validate_environment(" DEVELOPMENT "), "development")
        self.assertEqual(validate_environment("test"), "test")

    def test_staff_isolation_and_unicode(self):
        config = json.dumps({"hotel-a": "secret-a", "hotel-b": "secret-b"})
        self.assertTrue(staff_key_matches(config, "hotel-a", "secret-a"))
        for slug, key in (("hotel-b", "secret-a"), ("missing", "secret-a"),
                          ("hotel-a", None), ("hotel-a", "é")):
            self.assertFalse(staff_key_matches(config, slug, key))
        self.assertTrue(staff_key_matches('{"hotel-a":"é"}', "hotel-a", "é"))

    def test_staff_invalid_configuration(self):
        for config in ("[]", "null", "1", "{", '{"hotel-a":1}',
                       '{"hotel-a":""}', '{"a":"same","b":"same"}'):
            with self.subTest(config=config), self.assertRaises(StaffConfigurationError):
                staff_key_matches(config, "hotel-a", "secret")

    def test_readiness_does_not_create_missing_database(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "missing.sqlite"
            self.assertFalse(sqlite_ready(path))
            self.assertFalse(path.exists())

    def test_readiness_requires_schema(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "database.sqlite"
            conn = sqlite3.connect(path)
            try:
                conn.execute("CREATE TABLE properties (id TEXT)")
                conn.commit()
                self.assertFalse(sqlite_ready(path))
                for name in ("cases", "audit", "outbox", "public_facts",
                             "service_tickets", "dev_provider_delivery_state"):
                    conn.execute(f"CREATE TABLE {name} (id TEXT)")
                conn.commit()
                self.assertTrue(sqlite_ready(path))
            finally:
                conn.close()

    def test_corrupt_database_is_not_ready(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "corrupt.sqlite"
            path.write_bytes(b"not sqlite")
            self.assertFalse(sqlite_ready(path))


if __name__ == "__main__":
    unittest.main()
