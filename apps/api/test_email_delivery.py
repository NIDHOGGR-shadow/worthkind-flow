import unittest
from unittest.mock import patch
from uuid import uuid4
import email_delivery_worker as worker

class EmailProviderTests(unittest.TestCase):
    def test_send_uses_stable_key_and_no_private_data(self):
        job,provider=uuid4(),uuid4()
        with patch.object(worker,"request_json",return_value={"id":str(provider)}) as call:
            self.assertEqual(worker.send_email(job,"hotel@example.invalid","guest@example.invalid","re_test"),provider)
            args=call.call_args.args
            self.assertEqual(args[0],"/emails")
            self.assertEqual(args[3],"wf-service-"+str(job))
            self.assertEqual(args[2]["to"],["guest@example.invalid"])
            self.assertNotIn(str(job),args[2]["text"])
    def test_delivery_needs_provider_evidence(self):
        provider=uuid4()
        for state,expected in (("sent","retry"),("delivery_delayed","retry"),("delivered","delivered"),("bounced","failed"),("unknown","retry")):
            with patch.object(worker,"request_json",return_value={"id":str(provider),"last_event":state}):
                self.assertEqual(worker.read_delivery(provider,"re_test"),expected)
        with patch.object(worker,"request_json",return_value={"id":str(uuid4()),"last_event":"delivered"}):
            with self.assertRaises(ValueError):
                worker.read_delivery(provider,"re_test")
    def test_contact_is_single_address(self):
        self.assertFalse(worker.valid_email("a@example.invalid,b@example.invalid"))
        self.assertFalse(worker.valid_email("Guest <a@example.invalid>"))
        self.assertTrue(worker.valid_email("a@example.invalid"))
