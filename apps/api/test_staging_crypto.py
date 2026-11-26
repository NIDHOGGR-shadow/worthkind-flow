import base64
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
import main
from guest_postgres import encrypt_json,decrypt_json,GuestStorageError,GuestStorageNotConfigured


class StagingCryptoTests(unittest.TestCase):
    def test_key_rotation_preserves_old_records(self):
        k1=base64.b64encode(b"a"*32).decode()
        k2=base64.b64encode(b"b"*32).decode()
        with patch.dict(os.environ,{"WF_DATA_KEY_B64":k1,"WF_DATA_KEYS_JSON":"","WF_DATA_ACTIVE_KEY_ID":""}):
            legacy=encrypt_json({"a":1},associated_data="hotel-a")
            with patch.dict(os.environ,{"WF_DATA_KEYS_JSON":json.dumps({"key00001":k1,"key00002":k2}),"WF_DATA_ACTIVE_KEY_ID":"key00001"}):
                old=encrypt_json({"a":2},associated_data="hotel-a")
                with patch.dict(os.environ,{"WF_DATA_ACTIVE_KEY_ID":"key00002"}):
                    new=encrypt_json({"a":3},associated_data="hotel-a")
                    for i,blob in enumerate((legacy,old,new),1):
                        self.assertEqual(decrypt_json(blob,associated_data="hotel-a"),{"a":i})
                        with self.assertRaises(GuestStorageError):
                            decrypt_json(blob,associated_data="hotel-b")
                    with patch.dict(os.environ,{"WF_DATA_KEYS_JSON":json.dumps({"key00002":k2})}):
                        with self.assertRaises(GuestStorageNotConfigured):
                            decrypt_json(old,associated_data="hotel-a")

    def test_staging_blocks_legacy_and_never_initializes_sqlite(self):
        with tempfile.TemporaryDirectory() as folder:
            p=Path(folder)/"never.sqlite"
            with patch.object(main,"APP_ENV","staging"),patch.dict(os.environ,{"WF_DATABASE_PATH":str(p)}),patch.object(main,"staging_ready",return_value=False):
                with TestClient(main.app) as client:
                    self.assertEqual(client.get("/health").json()["stage"],"postgres-staging")
                    self.assertEqual(client.get("/ready").status_code,503)
                    for path in ("/","/staff","/static/app.js","/api/properties/demo-hotel","/openapi.json"):
                        self.assertEqual(client.get(path).status_code,404)
                    self.assertFalse(p.exists())

if __name__=="__main__":
    unittest.main()
