import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

with patch.dict(os.environ, {"WF_ENV": "test"}):
    from main import app


class RuntimeAPITests(unittest.TestCase):
    def test_readiness_and_staff_boundary(self):
        with tempfile.TemporaryDirectory() as folder:
            path = str(Path(folder) / "test.sqlite")
            with patch.dict(os.environ, {
                "WF_ENV": "test", "WF_DATABASE_PATH": path,
                "WF_DEV_STAFF_KEYS_JSON": '{"demo-hotel":"test-one","demo-hotel-two":"test-two"}',
            }):
                with TestClient(app) as client:
                    ready = client.get("/ready")
                    self.assertEqual(ready.status_code, 200)
                    self.assertFalse(ready.json()["production_ready"])
                    self.assertEqual(ready.headers["cache-control"], "no-store")
                    self.assertEqual(client.get("/health").status_code, 200)
                    route = "/api/properties/demo-hotel/staff/enquiries"
                    denied = client.get(route, headers={"x-staff-key": "test-two"})
                    self.assertEqual(denied.status_code, 401)
                    self.assertEqual(denied.headers["cache-control"], "no-store")
                    self.assertEqual(client.get(route, headers={"x-staff-key": "test-one"}).status_code, 200)
                    with patch.dict(os.environ, {"WF_DEV_STAFF_KEYS_JSON": "[]"}):
                        self.assertEqual(client.get(route).status_code, 503)
                    with patch.dict(os.environ, {"WF_DATABASE_PATH": path + ".missing"}):
                        self.assertEqual(client.get("/ready").status_code, 503)
                        self.assertFalse(Path(path + ".missing").exists())
                    invalid = client.post("/api/properties/demo-hotel/enquiries", json={})
                    self.assertEqual(invalid.status_code, 422)
                    self.assertEqual(invalid.headers["cache-control"], "no-store")


if __name__ == "__main__":
    unittest.main()
