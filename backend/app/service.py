from __future__ import annotations

from pathlib import Path
from typing import Any

from .config import Settings
from .context import ingest_context
from .db import ContextStore
from .exporter import export_all
from .ingest import file_sha256, ingest_tickets
from .pipeline import process_tickets
from .redaction import PIIRedactor
from .surprise import adapt_ticket_file


def get_store(settings: Settings) -> ContextStore:
    store = ContextStore(settings.database_path)
    store.initialize()
    return store


def _safe_input_path(settings: Settings, input_path: str) -> Path:
    resolved = Path(input_path).resolve()
    allowed_root = settings.root.parent.resolve()
    if resolved != allowed_root and allowed_root not in resolved.parents:
        raise ValueError("input_path must be inside the deployment workspace")
    return resolved


def ingest_selected_input(
    settings: Settings, store: ContextStore, input_path: str | None
) -> tuple[dict[str, int] | None, dict[str, Any] | None]:
    if not input_path:
        return ingest_tickets(settings, store, PIIRedactor()), None
    path = _safe_input_path(settings, input_path)
    adapted = adapt_ticket_file(path)
    if not adapted.safe:
        source_id = store.upsert_source(f"surprise/{path.name}", file_sha256(path), None)
        store.persist_file_quarantine(source_id, adapted.reasons, {"source_id": source_id, "input_kind": "surprise_file"})
        return None, {"status": "QUARANTINED", "reasons": list(adapted.reasons), "source_id": source_id}
    return ingest_tickets(settings, store, PIIRedactor(), path, adapted.records), {
        "status": "VALID", "mapping": adapted.mapping, "records": len(adapted.records)
    }


def run_pipeline(settings: Settings, input_path: str | None = None) -> dict[str, Any]:
    store = get_store(settings)
    context = ingest_context(settings, store)
    ingestion, input_status = ingest_selected_input(settings, store, input_path)
    processing = process_tickets(store) if ingestion is not None else {
        "processed": 0, "manual_holds": 0, "replacements": 0
    }
    export_all(store, settings.outputs_dir, settings.audit_dir)
    return {"context": context, "ingestion": ingestion, "input": input_status, "processing": processing, "status": "PASS"}

