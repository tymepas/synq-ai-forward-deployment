from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.config import Settings
from app.db import ContextStore
from app.exporter import export_all
from app.ingest import ingest_tickets
from app.models import validate_ticket
from app.normalization import normalize_vehicle_registration
from app.redaction import PIIRedactor, contains_raw_pii


VALID = {
    "ticket_id": "tkt-100",
    "created_at": "2026-08-01T12:00:00",
    "vehicle": "UP-86 CM 7252",
    "driver_id": "DRV-001",
    "origin_hub": "Kanpur",
    "km_from_origin_hub": 12,
    "destination": "Delhi",
    "issue": "radiator leak",
    "severity": "HIGH",
    "client": "Orion Pharma",
    "status": "OPEN",
    "resolution_note": "Call +91 9876543210",
}


class FoundationTests(unittest.TestCase):
    def test_vehicle_normalization(self) -> None:
        self.assertEqual(normalize_vehicle_registration("up-86 CM 7252"), "UP86CM7252")
        self.assertIsNone(normalize_vehicle_registration(" --- "))

    def test_validation_reasons_are_explicit(self) -> None:
        record = {"ticket_id": "TKT-BAD", "created_at": "not-a-date", "km_from_origin_hub": -1}
        result = validate_ticket(record)
        self.assertFalse(result.valid)
        self.assertIn("invalid_created_at", result.reasons)
        self.assertIn("negative_km_from_origin_hub", result.reasons)
        self.assertIn("missing_vehicle", result.reasons)

    def test_redaction_covers_known_sensitive_values(self) -> None:
        value = "Aadhaar 1234 5678 9012, DL HR16 20128663605, phone +91 9876543210, a@b.example"
        redacted = PIIRedactor(["Aarush Dutta"]).redact_text(value)
        self.assertFalse(contains_raw_pii(redacted))
        self.assertIn("[REDACTED_AADHAAR]", redacted)

    def test_generated_ids_do_not_false_positive_as_phones(self) -> None:
        self.assertFalse(contains_raw_pii("AUD-541b6583085920fcb8ec"))

    def test_duplicate_and_rerun_exports_are_stable(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            corpus = root / "candidate_bundle"
            corpus.mkdir()
            invalid = {"ticket_id": "TKT-BAD", "created_at": "bad"}
            (corpus / "tickets.json").write_text(json.dumps([VALID, {**VALID, "resolution_note": "sync copy"}, invalid]), encoding="utf-8")
            settings = Settings(root=root)
            store = ContextStore(settings.database_path)
            store.initialize()
            first = ingest_tickets(settings, store)
            export_all(store, settings.outputs_dir, settings.audit_dir)
            before = {p.name: p.read_bytes() for p in [
                settings.outputs_dir / "work_orders.jsonl",
                settings.outputs_dir / "comms_pending.jsonl",
                settings.outputs_dir / "comms_sent.jsonl",
                settings.outputs_dir / "quarantine.jsonl",
                settings.audit_dir / "audit.jsonl",
            ]}
            second = ingest_tickets(settings, store)
            export_all(store, settings.outputs_dir, settings.audit_dir)
            after = {p.name: p.read_bytes() for p in [
                settings.outputs_dir / "work_orders.jsonl",
                settings.outputs_dir / "comms_pending.jsonl",
                settings.outputs_dir / "comms_sent.jsonl",
                settings.outputs_dir / "quarantine.jsonl",
                settings.audit_dir / "audit.jsonl",
            ]}
            self.assertEqual(first["valid"], 1)
            self.assertEqual(first["duplicates"], 1)
            self.assertEqual(first["quarantined"], 1)
            self.assertEqual(before, after)
            self.assertEqual(second["valid"], 0)
            self.assertEqual(second["quarantined"], 0)
            self.assertFalse(contains_raw_pii((settings.outputs_dir / "quarantine.jsonl").read_text()))

    def test_ticket_free_text_is_not_persisted(self) -> None:
        from app.models import safe_ticket_context

        record = {**VALID, "issue": "Call Jane Doe about a radiator leak", "resolution_note": "Jane Doe +91 9876543210"}
        context = safe_ticket_context(validate_ticket(record).normalized)
        self.assertNotIn("Jane Doe", json.dumps(context))
        self.assertNotIn("9876543210", json.dumps(context))
