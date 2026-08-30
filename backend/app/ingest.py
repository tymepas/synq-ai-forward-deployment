from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from .config import Settings
from .db import ContextStore
from .models import safe_ticket_context, validate_ticket
from .redaction import PIIRedactor


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(64 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def ingest_tickets(
    settings: Settings,
    store: ContextStore,
    redactor: PIIRedactor | None = None,
    source_path: Path | None = None,
    records: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
) -> dict[str, int]:
    """Ingest the primary queue without persisting unredacted ticket content."""
    source_path = source_path or settings.corpus_dir / "tickets.json"
    if not source_path.is_file():
        raise FileNotFoundError("tickets source is missing")
    try:
        records = records if records is not None else json.loads(source_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError("tickets source is not valid JSON") from exc
    if not isinstance(records, list):
        raise ValueError("tickets source must be a JSON array")

    redactor = redactor or PIIRedactor()
    try:
        relative_path = str(source_path.relative_to(settings.corpus_dir)).replace("\\", "/")
    except ValueError:
        relative_path = f"surprise/{source_path.name}"
    source_id = store.upsert_source(relative_path, file_sha256(source_path), len(records))
    counts = {"records": len(records), "valid": 0, "quarantined": 0, "duplicates": 0}

    for record_index, raw in enumerate(records, start=1):
        already_ingested = store.ticket_record_exists(source_id, record_index)
        if not isinstance(raw, dict):
            raw = {"raw_record_type": type(raw).__name__}
        validation = validate_ticket(raw)
        # The source queue may contain arbitrary prose. Persist an allowlisted operational
        # projection only; raw records remain solely in the supplied immutable input file.
        sanitized_record = safe_ticket_context(validation.normalized)
        validation_payload: dict[str, Any] = {
            "valid": validation.valid,
            "reasons": list(validation.reasons),
            "normalized_vehicle": validation.normalized_vehicle,
        }
        source_record_id = store.persist_ticket_record(
            source_id, record_index, validation.ticket_id, sanitized_record, validation_payload
        )
        # Refresh the PII-safe projection on every ingest, but preserve completed decisions
        # and audit history for an already-seen source record.
        if already_ingested:
            # persist_ticket_record has completed the projection update; do not add rerun audits.
            if validation.valid and validation.ticket_id:
                store.refresh_ticket_projection(
                    validation.ticket_id, validation.normalized_vehicle,
                    str(validation.normalized["created_at"]), safe_ticket_context(validation.normalized),
                )
            continue
        citation = f"{source_id}:record:{record_index}"
        event_time = str(validation.normalized.get("created_at") or "")

        if not validation.valid:
            entity_key = validation.ticket_id or f"invalid-record-{record_index}"
            store.persist_quarantine(
                source_record_id,
                entity_key,
                validation.reasons,
                {"ticket_id": validation.ticket_id, "source_record_id": source_record_id},
            )
            store.audit(
                validation.ticket_id,
                "validation",
                "QUARANTINED",
                event_time,
                [citation],
                {"reason_codes": list(validation.reasons), "source_record_id": source_record_id},
                rule_id="TICKET_VALIDATION_V1",
            )
            counts["quarantined"] += 1
            continue

        assert validation.ticket_id is not None
        disposition = store.persist_valid_ticket(
            validation.ticket_id,
            source_record_id,
            validation.normalized_vehicle,
            str(validation.normalized["created_at"]),
            safe_ticket_context(validation.normalized),
        )
        if disposition == "new":
            counts["valid"] += 1
            outcome = "PASS"
        else:
            counts["duplicates"] += 1
            outcome = "DUPLICATE_IGNORED"
        store.audit(
            validation.ticket_id,
            "validation",
            outcome,
            event_time,
            [citation],
            {"source_record_id": source_record_id, "duplicate_kind": disposition},
            rule_id="TICKET_VALIDATION_V1",
        )
    return counts


if __name__ == "__main__":
    from .cli import main

    raise SystemExit(main(default_command="ingest"))
