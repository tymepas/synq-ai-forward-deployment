from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.db import ContextStore
from app.exporter import export_all
from app.pipeline import process_tickets
from app.redaction import contains_raw_pii


class PipelineTests(unittest.TestCase):
    def test_valid_ticket_creates_one_manual_hold_outbox_and_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ContextStore(root / "data" / "state.db")
            store.initialize()
            source_ids = {
                path: store.upsert_source(path, f"hash-{index}", 1)
                for index, path in enumerate((
                    "tickets.json", "dispatcher_interview.txt", "emails/thread_01_shakti_sla.txt",
                    "emails/thread_09_vertex_gate.txt",
                ))
            }
            record_id = store.persist_ticket_record(
                source_ids["tickets.json"], 1, "TKT-100", {"ticket_id": "TKT-100"}, {"valid": True}
            )
            store.persist_valid_ticket(
                "TKT-100", record_id, "UP86CM7252", "2026-08-01T12:00:00",
                {"ticket_id": "TKT-100", "created_at": "2026-08-01T12:00:00", "vehicle_normalized": "UP86CM7252",
                 "driver_id": "DRV-001", "origin_hub": "Kanpur", "km_from_origin_hub": 10.0,
                 "destination": "Ludhiana", "issue": "radiator leak", "severity": "HIGH",
                 "client": "Shakti Cement", "status": "OPEN"},
            )
            first = process_tickets(store)
            second = process_tickets(store)
            self.assertEqual(first, {"processed": 1, "manual_holds": 1, "replacements": 0})
            self.assertEqual(second, {"processed": 0, "manual_holds": 0, "replacements": 0})
            self.assertEqual(len(store.read_rows("SELECT * FROM work_orders")), 1)
            self.assertEqual(len(store.read_rows("SELECT * FROM pending_messages")), 1)
            export_all(store, root / "outputs", root / "audit")
            self.assertFalse(contains_raw_pii((root / "outputs" / "comms_pending.jsonl").read_text()))

