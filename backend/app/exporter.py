from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from .db import ContextStore
from .redaction import contains_raw_pii


def _decode_json_fields(row: dict[str, Any], fields: tuple[str, ...]) -> dict[str, Any]:
    result = dict(row)
    for field in fields:
        if field in result:
            result[field] = json.loads(result[field])
    return result


def _write_jsonl_atomically(path: Path, records: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if contains_raw_pii(records):
        raise ValueError(f"PII export gate blocked {path.name}")
    body = "".join(json.dumps(record, ensure_ascii=True, sort_keys=True, separators=(",", ":")) + "\n" for record in records)
    temp_path = path.with_suffix(path.suffix + ".tmp")
    temp_path.write_text(body, encoding="utf-8", newline="\n")
    os.replace(temp_path, path)


def export_all(store: ContextStore, outputs_dir: Path, audit_dir: Path) -> None:
    work_orders = [_decode_json_fields(row, ("citations_json",)) for row in store.read_rows(
        "SELECT work_order_id, ticket_id, vehicle_reg, created_at, citations_json FROM work_orders ORDER BY ticket_id"
    )]
    work_orders = [{**row, "citations": row.pop("citations_json")} for row in work_orders]

    pending = [_decode_json_fields(row, ("approval_context_json", "citations_json")) for row in store.read_rows(
        "SELECT message_id, ticket_id, recipient, body, approval_context_json, citations_json FROM pending_messages ORDER BY ticket_id"
    )]
    pending = [{**row, "approval_context": row.pop("approval_context_json"), "citations": row.pop("citations_json")} for row in pending]

    sent = store.read_rows(
        "SELECT message_id, ticket_id, recipient, body, approved_by, sent_at FROM sent_messages ORDER BY ticket_id"
    )

    quarantine = [_decode_json_fields(row, ("reasons_json", "sanitized_summary_json")) for row in store.read_rows(
        """SELECT quarantine_id, entity_key AS ticket_id, reasons_json, sanitized_summary_json
           FROM quarantine WHERE entity_type='ticket' ORDER BY entity_key, quarantine_id"""
    )]
    quarantine = [{**row, "reasons": row.pop("reasons_json"), "summary": row.pop("sanitized_summary_json")} for row in quarantine]
    file_quarantine = [_decode_json_fields(row, ("reasons_json", "safe_summary_json")) for row in store.read_rows(
        "SELECT quarantine_id, reasons_json, safe_summary_json FROM file_quarantine ORDER BY quarantine_id"
    )]
    quarantine.extend({"quarantine_id": row["quarantine_id"], "ticket_id": None, "reasons": row["reasons_json"],
                       "summary": row["safe_summary_json"]} for row in file_quarantine)
    quarantine.sort(key=lambda row: (str(row["ticket_id"] or ""), row["quarantine_id"]))

    audit = [_decode_json_fields(row, ("citations_json", "details_json")) for row in store.read_rows(
        """SELECT event_id, ticket_id, step, outcome, event_time, actor, rule_id, citations_json, details_json
           FROM audit_events ORDER BY COALESCE(ticket_id, ''), step, event_id"""
    )]
    audit = [{**row, "citations": row.pop("citations_json"), "details": row.pop("details_json")} for row in audit]

    _write_jsonl_atomically(outputs_dir / "work_orders.jsonl", work_orders)
    _write_jsonl_atomically(outputs_dir / "comms_pending.jsonl", pending)
    _write_jsonl_atomically(outputs_dir / "comms_sent.jsonl", sent)
    _write_jsonl_atomically(outputs_dir / "quarantine.jsonl", quarantine)
    _write_jsonl_atomically(audit_dir / "audit.jsonl", audit)
