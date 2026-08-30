from __future__ import annotations

import unittest
from pathlib import Path
import tempfile

from app.approval import approve_message
from app.db import ContextStore


class ApprovalTests(unittest.TestCase):
    def test_approval_is_exactly_once_and_requires_an_opaque_handle(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            store = ContextStore(Path(temp) / "state.db")
            store.initialize()
            source_id = store.upsert_source("tickets.json", "hash", 1)
            record_id = store.persist_ticket_record(source_id, 1, "TKT-1", {"ticket_id": "TKT-1"}, {"valid": True})
            store.persist_valid_ticket("TKT-1", record_id, "AB12CD3456", "2026-08-01T00:00:00",
                                       {"ticket_id": "TKT-1"})
            store.create_pending_message("TKT-1", "client_ops:test", "safe body", {}, [source_id])
            first = approve_message(store, "tkt-1", "role-dispatch", "2026-08-01T01:00:00")
            second = approve_message(store, "TKT-1", "role-dispatch", "2026-08-01T02:00:00")
            self.assertTrue(first["created"])
            self.assertFalse(second["created"])
            sent = store.read_rows("SELECT approved_by, sent_at FROM sent_messages")
            self.assertEqual(sent[0]["sent_at"], "2026-08-01T01:00:00")
            with self.assertRaises(ValueError):
                approve_message(store, "TKT-1", "Jane Doe", "2026-08-01T01:00:00")

