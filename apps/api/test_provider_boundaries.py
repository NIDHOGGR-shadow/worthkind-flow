import hashlib
import hmac
import json
import os
import unittest
from unittest.mock import patch
from fastapi import HTTPException
from paystack_provider import webhook_valid,account,ProviderUnavailable,initialize
from cloudbeds_pg import reservation_view

class ProviderBoundaryTests(unittest.TestCase):
    def test_timestamped_signature_and_downgrade_denial(self):
        cfg={"secret_key":"sk_test_fixture_only","webhook_secrets":{"whk_test":"whsec_fixture_only"},"allow_legacy_webhook":True}
        raw=b'{"event":"charge.success","data":{"reference":"fixture"}}'
        stamp="1800000000"
        sig=hmac.new(b"whsec_fixture_only",stamp.encode()+b"."+raw,hashlib.sha512).hexdigest()
        header=f"t={stamp},v1=whk_test:{sig}"
        self.assertTrue(webhook_valid(cfg,raw,header,None,now=int(stamp)))
        self.assertFalse(webhook_valid(cfg,raw+b" ",header,None,now=int(stamp)))
        self.assertFalse(webhook_valid(cfg,raw,header,None,now=int(stamp)+301))
        legacy=hmac.new(cfg["secret_key"].encode(),raw,hashlib.sha512).hexdigest()
        self.assertTrue(webhook_valid(cfg,raw,None,legacy))
        self.assertFalse(webhook_valid(cfg,raw,"invalid",legacy,now=int(stamp)))

    def test_live_account_explicit_gate_and_duplicate_keys(self):
        entries={"hotel-a":{"mode":"live","alias":"hotel-a-account","secret_key":"sk_live_fixture_only"}}
        with patch.dict(os.environ,{"WF_PAYSTACK_ACCOUNTS_JSON":json.dumps(entries),"WF_PAYSTACK_LIVE_ENABLED":"0"}):
            with self.assertRaises(ProviderUnavailable):
                account("hotel-a")
        entries={"hotel-a":{"mode":"test","alias":"hotel-a-account","secret_key":"sk_test_fixture_only"},"hotel-b":{"mode":"test","alias":"hotel-b-account","secret_key":"sk_test_fixture_only"}}
        with patch.dict(os.environ,{"WF_PAYSTACK_ACCOUNTS_JSON":json.dumps(entries)}):
            with self.assertRaises(ProviderUnavailable):
                account("hotel-a")

    def test_checkout_url_and_reference_validation_without_network(self):
        with patch("paystack_provider.call",return_value={"reference":"ref","authorization_url":"https://example.invalid/pay"}):
            with self.assertRaises(ProviderUnavailable):
                initialize({},"ref",100,"NGN","test@example.invalid")
        with patch("paystack_provider.call",return_value={"reference":"wrong","authorization_url":"https://checkout.paystack.com/fixture"}):
            with self.assertRaises(ProviderUnavailable):
                initialize({},"ref",100,"NGN","test@example.invalid")

    def test_pms_property_mismatch_and_guest_data_redaction(self):
        row={"propertyID":"hotel1","reservationID":"booking1","status":"confirmed","startDate":"2026-12-01","endDate":"2026-12-03","guestName":"Synthetic name","guestEmail":"test@example.invalid","sourceID":"s-1"}
        with self.assertRaises(HTTPException):
            reservation_view({"property_id":"hotel2"},row)
        result=reservation_view({"property_id":"hotel1"},row,"booking1")
        self.assertEqual(result["state"],"confirmed")
        self.assertNotIn("guestName",result)
        self.assertNotIn("guestEmail",result)

if __name__=="__main__":
    unittest.main()
