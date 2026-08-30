from __future__ import annotations

import shutil
import tempfile
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from app.api import create_app
from app.config import Settings
from app.db import ContextStore


class DemoSeedTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "backend"
        self.root.mkdir()
        shutil.copytree(Path(__file__).resolve().parents[1] / "demo_data", self.root / "demo_data")
        self.settings = Settings(root=self.root)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def test_empty_store_seeds_once_and_restart_is_stable(self) -> None:
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/tickets").json()["count"], 2)
            self.assertEqual(client.get("/vehicles").json()["count"], 2)
            self.assertEqual(client.get("/approvals/pending").json()["count"], 2)
            self.assertEqual(client.get("/quarantine").json()["count"], 1)

        store = ContextStore(self.settings.database_path)
        before = {
            "sources": len(store.read_rows("SELECT * FROM sources")),
            "tickets": len(store.read_rows("SELECT * FROM tickets")),
            "work_orders": len(store.read_rows("SELECT * FROM work_orders")),
            "pending": len(store.read_rows("SELECT * FROM pending_messages")),
            "audit": len(store.read_rows("SELECT * FROM audit_events")),
            "exports": {path.name: path.read_bytes() for path in sorted(self.settings.outputs_dir.glob("*.jsonl"))},
        }

        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/tickets").json()["count"], 2)

        after = {
            "sources": len(store.read_rows("SELECT * FROM sources")),
            "tickets": len(store.read_rows("SELECT * FROM tickets")),
            "work_orders": len(store.read_rows("SELECT * FROM work_orders")),
            "pending": len(store.read_rows("SELECT * FROM pending_messages")),
            "audit": len(store.read_rows("SELECT * FROM audit_events")),
            "exports": {path.name: path.read_bytes() for path in sorted(self.settings.outputs_dir.glob("*.jsonl"))},
        }
        self.assertEqual(before, after)

    def test_existing_operational_data_is_not_overwritten(self) -> None:
        store = ContextStore(self.settings.database_path)
        store.initialize()
        store.upsert_source("existing-production-record", "existing-hash", 1)
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/tickets").json()["count"], 0)
        self.assertEqual(len(store.read_rows("SELECT * FROM sources")), 1)

    def test_partial_operational_store_is_not_seeded(self) -> None:
        store = ContextStore(self.settings.database_path)
        store.initialize()
        store.audit(
            ticket_id=None,
            step="existing_operation",
            outcome="PASS",
            event_time="2026-03-01T00:00:00Z",
            citations=[],
            details={},
        )
        with TestClient(create_app(self.settings)) as client:
            self.assertEqual(client.get("/tickets").json()["count"], 0)
        self.assertEqual(len(store.read_rows("SELECT * FROM audit_events")), 1)
