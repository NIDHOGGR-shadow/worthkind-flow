import io
import json
import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from supabase_identity import verified_supabase_subject,IdentityRejected,IdentityUnavailable

class Response(io.BytesIO):
    pass

class SupabaseIdentityTests(unittest.TestCase):
    def setUp(self):
        self.env=patch.dict(os.environ,{"WF_SUPABASE_URL":"https://abcdefghijklmnopqrst.supabase.co","WF_SUPABASE_PUBLISHABLE_KEY":"sb_publishable_test_only"})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_confirmed_identity(self):
        user={"id":"12345678-1234-4321-8234-123456789012","role":"authenticated","is_anonymous":False,"email_confirmed_at":"2026-01-01"}
        with patch("supabase_identity.build_opener") as opener:
            opener.return_value.open.return_value=Response(json.dumps(user).encode())
            self.assertEqual(verified_supabase_subject("Bearer signed.test.token"),user["id"])
            req=opener.return_value.open.call_args.args[0]
            self.assertEqual(req.full_url,"https://abcdefghijklmnopqrst.supabase.co/auth/v1/user")
            self.assertEqual(req.get_header("Authorization"),"Bearer signed.test.token")

    def test_unconfirmed_or_anonymous_identity_rejected(self):
        user={"id":"12345678-1234-4321-8234-123456789012","role":"authenticated","is_anonymous":True}
        with patch("supabase_identity.build_opener") as opener:
            opener.return_value.open.return_value=Response(json.dumps(user).encode())
            with self.assertRaises(IdentityRejected):
                verified_supabase_subject("Bearer signed.test.token")
            user["is_anonymous"]=False
            opener.return_value.open.return_value=Response(json.dumps(user).encode())
            with self.assertRaises(IdentityRejected):
                verified_supabase_subject("Bearer signed.test.token")

    def test_reject_untrusted_endpoint_and_secret_key(self):
        with patch.dict(os.environ,{"WF_SUPABASE_URL":"https://example.invalid"}):
            with self.assertRaises(IdentityUnavailable):
                verified_supabase_subject("Bearer signed.test.token")
        with patch.dict(os.environ,{"WF_SUPABASE_PUBLISHABLE_KEY":"sb_secret_test_only"}):
            with self.assertRaises(IdentityUnavailable):
                verified_supabase_subject("Bearer signed.test.token")

    def test_provider_rejection_and_outage(self):
        with patch("supabase_identity.build_opener") as opener:
            for code,expected in ((401,IdentityRejected),(503,IdentityUnavailable)):
                opener.return_value.open.side_effect=HTTPError("https://abcdefghijklmnopqrst.supabase.co/auth/v1/user",code,"test",{},None)
                with self.assertRaises(expected):
                    verified_supabase_subject("Bearer signed.test.token")

if __name__=="__main__":
    unittest.main()
