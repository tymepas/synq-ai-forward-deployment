from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from app.db import ContextStore
from app.exporter import export_all
from app.surprise import adapt_ticket_file


class SurpriseAdapterTests(unittest.TestCase):
    def test_maps_documented_aliases(self) -> None:
        record = {
            "ticketId": "TKT-1", "timestamp": "2026-08-01T00:00:00", "vehicleReg": "UP86CM7252",
            "driver": "DRV-1", "origin": "Kanpur", "distance_from_origin_km": 5, "dest": "Delhi",
            "problem": "radiator leak", "priority": "HIGH", "customer": "Internal", "state": "OPEN",
        }
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "surprise.json"
            path.write_text(json.dumps([record]), encoding="utf-8")
            result = adapt_ticket_file(path)
        self.assertTrue(result.safe)
        self.assertEqual(result.records[0]["ticket_id"], "TKT-1")

    def test_refuses_ambiguous_or_missing_schema(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "bad.json"
            path.write_text(json.dumps([{"ticket_id": "TKT-1", "id": "TKT-OTHER"}]), encoding="utf-8")
            result = adapt_ticket_file(path)
        self.assertFalse(result.safe)
        self.assertTrue(result.reasons)

    def test_unmappable_file_quarantine_exports_without_actions(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            store = ContextStore(root / "state.db")
            store.initialize()
            source_id = store.upsert_source("surprise/bad.json", "hash", None)
            store.persist_file_quarantine(source_id, ["missing_required_mapping_vehicle"], {"source_id": source_id})
            export_all(store, root / "outputs", root / "audit")
            self.assertEqual((root / "outputs" / "work_orders.jsonl").read_text(), "")
            self.assertIn("missing_required_mapping_vehicle", (root / "outputs" / "quarantine.jsonl").read_text())
