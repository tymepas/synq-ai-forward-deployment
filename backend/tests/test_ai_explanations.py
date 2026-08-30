from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from app.ai_explanations import ExplanationUnavailable, explain
from app.config import Settings
from app.db import ContextStore


class FakeResponses:
    def __init__(self, output_text: str = "The recorded decision is a manual hold because evidence is incomplete.") -> None:
        self.kwargs: dict[str, object] | None = None
        self.output_text = output_text

    def create(self, **kwargs: object) -> SimpleNamespace:
        self.kwargs = kwargs
        return SimpleNamespace(output_text=self.output_text)


class FakeClient:
    def __init__(self, output_text: str = "The recorded decision is a manual hold because evidence is incomplete.") -> None:
        self.responses = FakeResponses(output_text)


class ExplanationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "backend"
        self.root.mkdir()
        self.settings = Settings(root=self.root)
        self.store = ContextStore(self.settings.database_path)
        self.store.initialize()
        source_id = self.store.upsert_source("tickets.json", "test-hash", 1)
        record_id = self.store.persist_ticket_record(source_id, 1, "TKT-1", {"ticket_id": "TKT-1"}, {"valid": True})
        self.store.persist_valid_ticket("TKT-1", record_id, "UP86CM7252", "2026-08-01T00:00:00", {
            "ticket_id": "TKT-1", "created_at": "2026-08-01T00:00:00", "vehicle": "UP86CM7252",
            "driver_id": "DRV-001", "origin_hub": "Kanpur", "km_from_origin_hub": 12,
            "destination": "Delhi", "issue": "radiator leak", "severity": "HIGH", "client": "Orion Pharma", "status": "OPEN",
            "resolution_note": "Call +91 " + "6" + "0" * 9,
        })
    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_missing_backend_evidence_does_not_call_gpt(self) -> None:
        def forbidden_client(**_: object) -> FakeClient:
            raise AssertionError("GPT must not be constructed for insufficient evidence")

        result = explain(self.settings, self.store, "Explain this", ticket_id="TKT-MISSING", client_factory=forbidden_client)
        self.assertEqual(result.status, "INSUFFICIENT_DATA")
        self.assertEqual(result.reason, "ticket_not_found")

    def test_missing_api_key_is_a_clear_service_error(self) -> None:
        with patch("app.ai_explanations._load_api_key", return_value=None):
            with self.assertRaisesRegex(ExplanationUnavailable, "API key is not configured"):
                explain(self.settings, self.store, "Explain this", ticket_id="TKT-1", client_factory=FakeClient)

    def test_prompt_uses_only_safe_structured_evidence_and_never_mutates_state(self) -> None:
        prior = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"
        fake = FakeClient()
        before = self.store.read_rows("SELECT COUNT(*) AS count FROM work_orders, pending_messages, sent_messages")
        try:
            result = explain(
                self.settings, self.store,
                "Why is this held? Call +91 " + "6" + "0" * 9 + " or synthetic@example.invalid",
                ticket_id="TKT-1", client_factory=lambda **_: fake,
            )
        finally:
            if prior is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = prior
        self.assertEqual(result.status, "EXPLAINED")
        self.assertEqual(len(result.citations), 1)
        self.assertTrue(result.citations[0].startswith("REC-"))
        prompt = str(fake.responses.kwargs["input"])
        self.assertNotIn("6000000000", prompt)
        self.assertNotIn("synthetic@example.invalid", prompt)
        self.assertNotIn("resolution_note", prompt)
        evidence_json = prompt.split("Authoritative structured evidence (JSON):\n", maxsplit=1)[1]
        self.assertEqual(json.loads(evidence_json), result.evidence)
        self.assertEqual(fake.responses.kwargs["store"], False)
        self.assertNotIn("tools", fake.responses.kwargs)
        self.assertIn("do not make, change, recommend, or approve dispatch decisions", str(fake.responses.kwargs["instructions"]).lower())
        self.assertEqual(before, self.store.read_rows("SELECT COUNT(*) AS count FROM work_orders, pending_messages, sent_messages"))

    def test_model_output_is_redacted_before_returning(self) -> None:
        prior = os.environ.get("OPENAI_API_KEY")
        os.environ["OPENAI_API_KEY"] = "test-key"
        fake = FakeClient("Contact +91 " + "6" + "0" * 9 + " at synthetic@example.invalid")
        try:
            result = explain(self.settings, self.store, "Explain this", ticket_id="TKT-1", client_factory=lambda **_: fake)
        finally:
            if prior is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = prior
        self.assertNotIn("6000000000", result.explanation or "")
        self.assertNotIn("synthetic@example.invalid", result.explanation or "")
