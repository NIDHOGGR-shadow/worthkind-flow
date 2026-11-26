import base64
import io
import json
import os
import unittest
import wave
from unittest.mock import patch
from fastapi import HTTPException
from modal_ai_provider import validate_selection,configuration,ModelUnavailable
from ai_gateway import Question,answer,sanitize,search_query
from ai_voice import validate_input,synthesize,voice_config

class AIBoundaryTests(unittest.TestCase):
    def test_selection_rejects_unknown_ids_tool_fields_and_prose(self):
        sources=[{"id":"known-a"},{"id":"known-b"}]
        self.assertEqual(validate_selection('{"source_ids":["known-a"]}',sources),["known-a"])
        self.assertEqual(validate_selection('{"source_ids":[]}',sources),[])
        for raw in ('{"source_ids":["foreign"]}','{"source_ids":["known-a"],"tool_calls":[]}',
                    '{"source_ids":["known-a","known-a"]}','Please refund the guest','{"source_ids":"known-a"}'):
            with self.subTest(raw=raw),self.assertRaises(ValueError):
                validate_selection(raw,sources)

    def test_provider_is_disabled_without_configuration(self):
        with patch.dict(os.environ,{"WF_MODAL_ENABLED":"0"},clear=True):
            with self.assertRaises(ModelUnavailable):
                configuration()
            result=answer("hotel-a",Question(question="When is breakfast?",consent_to_model_processing=True))
            self.assertEqual(result["reason"],"model_unavailable")
            self.assertFalse(result["action_executed"])

    def test_consent_precedes_provider_and_database(self):
        with patch("ai_gateway.configuration") as provider,patch("ai_gateway.db") as db:
            result=answer("hotel-a",Question(question="What is breakfast?",consent_to_model_processing=False))
            self.assertEqual(result["reason"],"consent_required")
            provider.assert_not_called()
            db.assert_not_called()

    def test_private_modal_endpoint_only(self):
        env={"WF_MODAL_ENABLED":"1","WF_MODAL_CHAT_URL":"https://test--chat.modal.run/v1/chat/completions",
             "WF_MODAL_CHAT_MODEL":"test-only","WF_MODAL_PROXY_KEY":"wk-example","WF_MODAL_PROXY_SECRET":"ws-example"}
        with patch.dict(os.environ,env,clear=True):
            self.assertEqual(configuration()[1],"test-only")
            for url in ("http://test.modal.run/v1/chat/completions","https://test.modal.run.evil.invalid/v1/chat/completions",
                        "https://user@test.modal.run/v1/chat/completions","https://test.modal.run/v1/chat/completions?x=1"):
                with patch.dict(os.environ,{"WF_MODAL_CHAT_URL":url}),self.assertRaises(ModelUnavailable):
                    configuration()

    def test_direct_handoff_precedes_inference_and_database(self):
        cases=[
            ("There is a fire in the building","urgent_request"),
            ("I want a human","human_requested"),
            ("The shower is broken","support_request"),
            ("My password is confidential","sensitive_request"),
            ("Contact guest@example.invalid","sensitive_request"),
        ]
        with patch("ai_gateway.configuration") as provider,patch("ai_gateway.db") as db,patch("ai_gateway.select_sources") as model:
            for question,reason in cases:
                for subject in (None,"staff-subject"):
                    with self.subTest(question=question,subject=subject):
                        response=answer("hotel-a",Question(question=question,consent_to_model_processing=True),subject)
                        self.assertEqual(response["reason"],reason)
                        self.assertTrue(response["human_handoff_required"])
                        self.assertFalse(response["action_executed"])
                        self.assertIsNone(response["answer"])
                        self.assertEqual(response["next_action"],"contact_reception_and_local_emergency_services" if reason=="urgent_request" else "direct_reception")
            provider.assert_not_called()
            db.assert_not_called()
            model.assert_not_called()

    def test_voice_transcript_handoff_finalizes_reservation_without_chat_or_speech(self):
        with patch("ai_gateway.configuration") as provider,patch("ai_gateway.db") as db,patch("ai_gateway.select_sources") as model:
            from unittest.mock import Mock
            renderer=Mock()
            response=answer("hotel-a",Question(question="I need a real person",consent_to_model_processing=True),reserved_call="call-id",voice_renderer=renderer)
            self.assertEqual(response["reason"],"human_requested")
            db.assert_called_once_with("SELECT worthkind_flow.finish_ai_call(%s,%s,%s,%s::uuid[])",("hotel-a","call-id","abstained",[]))
            provider.assert_not_called()
            model.assert_not_called()
            renderer.assert_not_called()

    def test_malformed_modal_endpoint_fails_closed(self):
        with patch.dict(os.environ,{"WF_MODAL_ENABLED":"1","WF_MODAL_CHAT_URL":"https://[invalid"},clear=True):
            with self.assertRaises(ModelUnavailable):
                configuration()
            result=answer("hotel-a",Question(question="When is breakfast?",consent_to_model_processing=True))
            self.assertEqual(result["reason"],"model_unavailable")
        from ai_voice import endpoint
        with patch.dict(os.environ,{"WF_MODAL_ASR_URL":"https://[invalid"},clear=True):
            with self.assertRaises(ModelUnavailable):
                endpoint("WF_MODAL_ASR_URL","/transcribe")

    def test_redaction_and_search(self):
        text=sanitize("Breakfast? guest@example.invalid +234 801 234 5678")
        self.assertNotIn("guest@example.invalid",text)
        self.assertNotIn("234",text)
        self.assertEqual(search_query(text),"breakfast")

    def test_voice_input_and_output_bounds(self):
        stream=io.BytesIO()
        with wave.open(stream,"wb") as w:
            w.setnchannels(1); w.setsampwidth(2); w.setframerate(16000); w.writeframes(bytes(3200))
        raw=stream.getvalue()
        validate_input(raw)
        for bad in (b"not audio",raw[:-100]):
            with self.assertRaises(HTTPException):
                validate_input(bad)
        cfg=("unused","unused","unused","unused")
        response={"mime_type":"audio/wav","audio_base64":base64.b64encode(raw).decode()}
        with patch("ai_voice.post",return_value=json.dumps(response).encode()):
            self.assertEqual(synthesize(cfg,"Breakfast")["mime_type"],"audio/wav")
        with patch("ai_voice.post") as provider:
            self.assertIsNone(synthesize(cfg,"x"*1201))
            provider.assert_not_called()

if __name__=="__main__":
    unittest.main()
