from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.db import ContextStore


class ApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "backend"
        self.root.mkdir()
        self.settings = Settings(root=self.root)
        self.store = ContextStore(self.settings.database_path)
        self.store.initialize()
        source_id = self.store.upsert_source("tickets.json", "test-hash", 1)
        record_id = self.store.persist_ticket_record(source_id, 1, "TKT-1", {"ticket_id": "TKT-1"}, {"valid": True})
        self.store.persist_valid_ticket("TKT-1", record_id, "UP86CM7252", "2026-08-01T00:00:00",
                                        {"ticket_id": "TKT-1", "created_at": "2026-08-01T00:00:00"})
        self.store.create_pending_message(
            "TKT-1", "client_ops:test", "safe body", {"decision_status": "MANUAL_HOLD"}, ["test-citation"]
        )
        self.client = TestClient(create_app(self.settings))

    def tearDown(self) -> None:
        self.client.close()
        self.temp.cleanup()

    def test_health_and_safe_read_endpoints(self) -> None:
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        self.assertEqual(self.client.get("/ticket/TKT-1").json()["status"], "FOUND")
        self.assertEqual(self.client.get("/tickets").json()["count"], 1)
        self.assertEqual(self.client.get("/vehicles").json()["count"], 0)
        self.assertEqual(self.client.get("/quarantine").json()["count"], 0)
        approval = self.client.get("/approvals/pending").json()
        self.assertEqual(approval["count"], 1)
        self.assertEqual(approval["approvals"][0]["ticket_id"], "TKT-1")

    def test_query_validation_and_approval_rejection_are_safe(self) -> None:
        self.assertEqual(self.client.post("/query", json={}).status_code, 422)
        self.assertEqual(self.client.post("/approve", json={
            "ticket_id": "TKT-1", "approved_by": "Jane Doe", "approved_at": "2026-08-01T00:00:00"
        }).status_code, 422)
