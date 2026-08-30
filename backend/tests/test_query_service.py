from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from app.db import ContextStore
from app.query_service import query_ticket, query_vehicle


class QueryServiceTests(unittest.TestCase):
    def test_returns_citations_and_insufficient_data(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ContextStore(Path(temp) / "state.db")
            store.initialize()
            source_id = store.upsert_source("tickets.json", "hash", 1)
            record_id = store.persist_ticket_record(source_id, 1, "TKT-1", {"ticket_id": "TKT-1"}, {"valid": True})
            store.persist_valid_ticket("TKT-1", record_id, "AB12CD3456", "2026-08-01T00:00:00",
                                       {"ticket_id": "TKT-1", "created_at": "2026-08-01T00:00:00"})
            found = query_ticket(store, "tkt-1")
            missing = query_vehicle(store, "XX00XX0000")
            self.assertEqual(found["status"], "FOUND")
            self.assertTrue(found["citations"])
            self.assertEqual(found["citation_details"], [{
                "label": "Breakdown ticket", "kind": "breakdown_ticket", "citation": record_id,
            }])
            self.assertEqual(missing["status"], "INSUFFICIENT_DATA")
