from __future__ import annotations

import hashlib
import json
import sqlite3
from collections.abc import Iterable, Mapping
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator


def stable_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=True, sort_keys=True, separators=(",", ":"))


def stable_id(prefix: str, *parts: object) -> str:
    payload = "\x1f".join(str(part) for part in parts).encode("utf-8")
    return f"{prefix}-{hashlib.sha256(payload).hexdigest()[:20]}"


class ContextStore:
    """SQLite-backed, append-safe state for deterministic local processing."""

    def __init__(self, database_path: Path) -> None:
        self.database_path = database_path

    @contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            connection.execute("PRAGMA foreign_keys = ON")
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.transaction() as conn:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS sources (
                    source_id TEXT PRIMARY KEY,
                    relative_path TEXT NOT NULL,
                    content_hash TEXT NOT NULL,
                    record_count INTEGER,
                    UNIQUE(relative_path, content_hash)
                );

                CREATE TABLE IF NOT EXISTS ticket_records (
                    source_record_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES sources(source_id),
                    record_index INTEGER NOT NULL,
                    canonical_ticket_id TEXT,
                    record_fingerprint TEXT NOT NULL,
                    sanitized_record_json TEXT NOT NULL,
                    validation_json TEXT NOT NULL,
                    UNIQUE(source_id, record_index)
                );

                CREATE TABLE IF NOT EXISTS tickets (
                    ticket_id TEXT PRIMARY KEY,
                    source_record_id TEXT NOT NULL REFERENCES ticket_records(source_record_id),
                    normalized_vehicle TEXT,
                    created_at TEXT NOT NULL,
                    normalized_json TEXT NOT NULL,
                    canonical_fingerprint TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS ticket_duplicates (
                    ticket_id TEXT NOT NULL,
                    source_record_id TEXT NOT NULL REFERENCES ticket_records(source_record_id),
                    duplicate_kind TEXT NOT NULL,
                    PRIMARY KEY(ticket_id, source_record_id)
                );

                CREATE TABLE IF NOT EXISTS quarantine (
                    quarantine_id TEXT PRIMARY KEY,
                    source_record_id TEXT NOT NULL REFERENCES ticket_records(source_record_id),
                    entity_type TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    reasons_json TEXT NOT NULL,
                    sanitized_summary_json TEXT NOT NULL,
                    UNIQUE(source_record_id, entity_type)
                );

                CREATE TABLE IF NOT EXISTS file_quarantine (
                    quarantine_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES sources(source_id),
                    reasons_json TEXT NOT NULL,
                    safe_summary_json TEXT NOT NULL,
                    UNIQUE(source_id)
                );

                CREATE TABLE IF NOT EXISTS audit_events (
                    event_id TEXT PRIMARY KEY,
                    ticket_id TEXT,
                    step TEXT NOT NULL,
                    outcome TEXT NOT NULL,
                    event_time TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    rule_id TEXT,
                    citations_json TEXT NOT NULL,
                    details_json TEXT NOT NULL,
                    event_hash TEXT NOT NULL,
                    UNIQUE(ticket_id, step, event_hash)
                );

                CREATE TABLE IF NOT EXISTS work_orders (
                    work_order_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL UNIQUE REFERENCES tickets(ticket_id),
                    vehicle_reg TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    citations_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS pending_messages (
                    message_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL UNIQUE REFERENCES tickets(ticket_id),
                    recipient TEXT NOT NULL,
                    body TEXT NOT NULL,
                    approval_context_json TEXT NOT NULL,
                    citations_json TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS sent_messages (
                    message_id TEXT PRIMARY KEY,
                    ticket_id TEXT NOT NULL UNIQUE REFERENCES tickets(ticket_id),
                    recipient TEXT NOT NULL,
                    body TEXT NOT NULL,
                    approved_by TEXT NOT NULL,
                    sent_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS entity_conflicts (
                    conflict_id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_key TEXT NOT NULL,
                    field_name TEXT NOT NULL,
                    claims_json TEXT NOT NULL,
                    material INTEGER NOT NULL,
                    resolution_status TEXT NOT NULL,
                    citations_json TEXT NOT NULL,
                    UNIQUE(entity_type, entity_key, field_name)
                );

                CREATE TABLE IF NOT EXISTS documents (
                    document_id TEXT PRIMARY KEY,
                    source_id TEXT NOT NULL REFERENCES sources(source_id),
                    document_type TEXT NOT NULL,
                    classification TEXT NOT NULL,
                    safe_summary TEXT NOT NULL,
                    UNIQUE(source_id)
                );

                CREATE TABLE IF NOT EXISTS vehicle_claims (
                    claim_id TEXT PRIMARY KEY,
                    vehicle_reg TEXT NOT NULL,
                    source_id TEXT NOT NULL REFERENCES sources(source_id),
                    record_index INTEGER NOT NULL,
                    claim_json TEXT NOT NULL,
                    source_priority INTEGER NOT NULL,
                    UNIQUE(source_id, record_index)
                );

                CREATE TABLE IF NOT EXISTS vehicles (
                    vehicle_reg TEXT PRIMARY KEY,
                    vehicle_id TEXT,
                    model TEXT,
                    year INTEGER,
                    bs_stage TEXT,
                    engine_heater TEXT,
                    home_hub TEXT,
                    capacity_tonnes REAL,
                    fleet_status TEXT,
                    resolution_status TEXT NOT NULL,
                    source_citation TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS drivers (
                    driver_id TEXT PRIMARY KEY,
                    home_hub TEXT,
                    night_solo_eligible_after TEXT,
                    source_citation TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS maintenance_events (
                    maintenance_id TEXT PRIMARY KEY,
                    vehicle_reg TEXT NOT NULL,
                    event_date TEXT NOT NULL,
                    odometer_km REAL NOT NULL,
                    notes_redacted TEXT NOT NULL,
                    source_citation TEXT NOT NULL,
                    UNIQUE(source_citation)
                );

                CREATE TABLE IF NOT EXISTS trips (
                    trip_id TEXT PRIMARY KEY,
                    created_at TEXT NOT NULL,
                    route_type TEXT NOT NULL,
                    origin_center TEXT NOT NULL,
                    origin_name TEXT,
                    dest_center TEXT NOT NULL,
                    dest_name TEXT,
                    dispatch_time TEXT NOT NULL,
                    delivery_time TEXT NOT NULL,
                    osrm_distance_km REAL NOT NULL,
                    osrm_time_min REAL NOT NULL,
                    actual_time_min REAL NOT NULL,
                    vehicle_reg TEXT NOT NULL,
                    driver_id TEXT NOT NULL,
                    client TEXT NOT NULL,
                    trip_status TEXT NOT NULL,
                    billed_amount REAL NOT NULL,
                    source_citation TEXT NOT NULL
                );
                """
            )

    def upsert_source(self, relative_path: str, content_hash: str, record_count: int | None) -> str:
        source_id = stable_id("SRC", relative_path, content_hash)
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO sources(source_id, relative_path, content_hash, record_count)
                   VALUES (?, ?, ?, ?)
                   ON CONFLICT(relative_path, content_hash) DO UPDATE SET record_count=excluded.record_count""",
                (source_id, relative_path, content_hash, record_count),
            )
        return source_id

    def persist_ticket_record(
        self,
        source_id: str,
        record_index: int,
        canonical_ticket_id: str | None,
        sanitized_record: Mapping[str, Any],
        validation: Mapping[str, Any],
    ) -> str:
        record_json = stable_json(sanitized_record)
        record_fingerprint = hashlib.sha256(record_json.encode("utf-8")).hexdigest()
        source_record_id = stable_id("REC", source_id, record_index, record_fingerprint)
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO ticket_records(
                     source_record_id, source_id, record_index, canonical_ticket_id,
                     record_fingerprint, sanitized_record_json, validation_json)
                   VALUES (?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(source_id, record_index) DO UPDATE SET
                     canonical_ticket_id=excluded.canonical_ticket_id,
                     record_fingerprint=excluded.record_fingerprint,
                     sanitized_record_json=excluded.sanitized_record_json,
                     validation_json=excluded.validation_json""",
                (
                    source_record_id,
                    source_id,
                    record_index,
                    canonical_ticket_id,
                    record_fingerprint,
                    record_json,
                    stable_json(validation),
                ),
            )
            stored = conn.execute(
                "SELECT source_record_id FROM ticket_records WHERE source_id=? AND record_index=?",
                (source_id, record_index),
            ).fetchone()
        return str(stored["source_record_id"])

    def ticket_record_exists(self, source_id: str, record_index: int) -> bool:
        rows = self.read_rows(
            "SELECT 1 AS present FROM ticket_records WHERE source_id = ? AND record_index = ?",
            (source_id, record_index),
        )
        return bool(rows)

    def persist_valid_ticket(
        self,
        ticket_id: str,
        source_record_id: str,
        normalized_vehicle: str | None,
        created_at: str,
        normalized: Mapping[str, Any],
    ) -> str:
        normalized_json = stable_json(normalized)
        fingerprint = hashlib.sha256(normalized_json.encode("utf-8")).hexdigest()
        with self.transaction() as conn:
            existing = conn.execute(
                "SELECT canonical_fingerprint FROM tickets WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if existing is None:
                conn.execute(
                    """INSERT INTO tickets(ticket_id, source_record_id, normalized_vehicle, created_at,
                       normalized_json, canonical_fingerprint)
                       VALUES (?, ?, ?, ?, ?, ?)""",
                    (ticket_id, source_record_id, normalized_vehicle, created_at, normalized_json, fingerprint),
                )
                return "new"
            duplicate_kind = "exact" if existing["canonical_fingerprint"] == fingerprint else "conflicting"
            conn.execute(
                """INSERT INTO ticket_duplicates(ticket_id, source_record_id, duplicate_kind)
                   VALUES (?, ?, ?) ON CONFLICT(ticket_id, source_record_id) DO NOTHING""",
                (ticket_id, source_record_id, duplicate_kind),
            )
            return duplicate_kind

    def refresh_ticket_projection(
        self,
        ticket_id: str,
        normalized_vehicle: str | None,
        created_at: str,
        normalized: Mapping[str, Any],
    ) -> None:
        normalized_json = stable_json(normalized)
        fingerprint = hashlib.sha256(normalized_json.encode("utf-8")).hexdigest()
        with self.transaction() as conn:
            conn.execute(
                """UPDATE tickets SET normalized_vehicle=?, created_at=?, normalized_json=?, canonical_fingerprint=?
                   WHERE ticket_id=?""",
                (normalized_vehicle, created_at, normalized_json, fingerprint, ticket_id),
            )

    def persist_quarantine(
        self,
        source_record_id: str,
        entity_key: str,
        reasons: Iterable[str],
        summary: Mapping[str, Any],
    ) -> str:
        quarantine_id = stable_id("QRN", source_record_id, "ticket")
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO quarantine(quarantine_id, source_record_id, entity_type, entity_key,
                   reasons_json, sanitized_summary_json)
                   VALUES (?, ?, 'ticket', ?, ?, ?)
                   ON CONFLICT(source_record_id, entity_type) DO NOTHING""",
                (quarantine_id, source_record_id, entity_key, stable_json(sorted(reasons)), stable_json(summary)),
            )
        return quarantine_id

    def persist_file_quarantine(self, source_id: str, reasons: Iterable[str], summary: Mapping[str, Any]) -> str:
        quarantine_id = stable_id("FQRN", source_id)
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO file_quarantine(quarantine_id, source_id, reasons_json, safe_summary_json)
                   VALUES (?, ?, ?, ?) ON CONFLICT(source_id) DO UPDATE SET
                     reasons_json=excluded.reasons_json, safe_summary_json=excluded.safe_summary_json""",
                (quarantine_id, source_id, stable_json(sorted(reasons)), stable_json(summary)),
            )
        return quarantine_id

    def audit(
        self,
        ticket_id: str | None,
        step: str,
        outcome: str,
        event_time: str,
        citations: Iterable[str],
        details: Mapping[str, Any],
        rule_id: str | None = None,
        actor: str = "system",
    ) -> str:
        citations_json = stable_json(sorted(set(citations)))
        details_json = stable_json(details)
        event_hash = hashlib.sha256(
            stable_json({"outcome": outcome, "time": event_time, "rule": rule_id,
                         "citations": json.loads(citations_json), "details": json.loads(details_json)}).encode("utf-8")
        ).hexdigest()
        event_id = stable_id("AUD", ticket_id or "none", step, event_hash)
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO audit_events(event_id, ticket_id, step, outcome, event_time, actor,
                   rule_id, citations_json, details_json, event_hash)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                   ON CONFLICT(ticket_id, step, event_hash) DO NOTHING""",
                (event_id, ticket_id, step, outcome, event_time, actor, rule_id,
                 citations_json, details_json, event_hash),
            )
        return event_id

    def upsert_document(
        self, source_id: str, document_type: str, classification: str, safe_summary: str
    ) -> str:
        document_id = stable_id("DOC", source_id)
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO documents(document_id, source_id, document_type, classification, safe_summary)
                   VALUES (?, ?, ?, ?, ?)
                   ON CONFLICT(source_id) DO UPDATE SET
                     document_type=excluded.document_type, classification=excluded.classification,
                     safe_summary=excluded.safe_summary""",
                (document_id, source_id, document_type, classification, safe_summary),
            )
        return document_id

    def upsert_conflict(
        self,
        entity_type: str,
        entity_key: str,
        field_name: str,
        claims: list[dict[str, Any]],
        material: bool,
        citations: list[str],
    ) -> str:
        conflict_id = stable_id("CNF", entity_type, entity_key, field_name)
        with self.transaction() as conn:
            conn.execute(
                """INSERT INTO entity_conflicts(conflict_id, entity_type, entity_key, field_name,
                   claims_json, material, resolution_status, citations_json)
                   VALUES (?, ?, ?, ?, ?, ?, 'MANUAL_HOLD' , ?)
                   ON CONFLICT(entity_type, entity_key, field_name) DO UPDATE SET
                     claims_json=excluded.claims_json, material=excluded.material,
                     resolution_status=excluded.resolution_status, citations_json=excluded.citations_json""",
                (conflict_id, entity_type, entity_key, field_name, stable_json(claims), int(material), stable_json(citations)),
            )
        return conflict_id

    def create_work_order(
        self, ticket_id: str, vehicle_reg: str, created_at: str, citations: list[str]
    ) -> tuple[str, bool]:
        work_order_id = stable_id("WO", ticket_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO work_orders(work_order_id, ticket_id, vehicle_reg, created_at, citations_json)
                   VALUES (?, ?, ?, ?, ?) ON CONFLICT(ticket_id) DO NOTHING""",
                (work_order_id, ticket_id, vehicle_reg, created_at, stable_json(sorted(set(citations)))),
            )
        return work_order_id, cursor.rowcount == 1

    def create_pending_message(
        self,
        ticket_id: str,
        recipient: str,
        body: str,
        approval_context: Mapping[str, Any],
        citations: list[str],
    ) -> tuple[str, bool]:
        message_id = stable_id("MSG", ticket_id)
        with self.transaction() as conn:
            cursor = conn.execute(
                """INSERT INTO pending_messages(message_id, ticket_id, recipient, body, approval_context_json, citations_json)
                   VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(ticket_id) DO NOTHING""",
                (message_id, ticket_id, recipient, body, stable_json(approval_context), stable_json(sorted(set(citations)))),
            )
        return message_id, cursor.rowcount == 1

    def create_sent_message(
        self, ticket_id: str, approved_by: str, approved_at: str
    ) -> tuple[str, bool]:
        with self.transaction() as conn:
            pending = conn.execute(
                "SELECT message_id, recipient, body FROM pending_messages WHERE ticket_id = ?", (ticket_id,)
            ).fetchone()
            if pending is None:
                raise ValueError("no pending message for ticket")
            cursor = conn.execute(
                """INSERT INTO sent_messages(message_id, ticket_id, recipient, body, approved_by, sent_at)
                   VALUES (?, ?, ?, ?, ?, ?) ON CONFLICT(ticket_id) DO NOTHING""",
                (pending["message_id"], ticket_id, pending["recipient"], pending["body"], approved_by, approved_at),
            )
        return pending["message_id"], cursor.rowcount == 1

    def read_rows(self, query: str, params: tuple[object, ...] = ()) -> list[dict[str, Any]]:
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        conn = sqlite3.connect(self.database_path)
        try:
            conn.row_factory = sqlite3.Row
            return [dict(row) for row in conn.execute(query, params).fetchall()]
        finally:
            conn.close()
