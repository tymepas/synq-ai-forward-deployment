from __future__ import annotations

import json
from contextlib import asynccontextmanager
from typing import Any

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field, model_validator

from .ai_explanations import ExplanationUnavailable, explain
from .approval import approve_message
from .config import Settings, default_settings
from .db import ContextStore
from .query_service import query_ticket, query_vehicle
from .service import get_store, run_pipeline


class RunRequest(BaseModel):
    input_path: str | None = Field(default=None, max_length=500)


class ApprovalRequest(BaseModel):
    ticket_id: str = Field(min_length=1, max_length=80)
    approved_by: str = Field(min_length=1, max_length=64)
    approved_at: str = Field(min_length=1, max_length=40)


class QueryRequest(BaseModel):
    ticket_id: str | None = Field(default=None, max_length=80)
    vehicle_reg: str | None = Field(default=None, max_length=80)
    question: str | None = Field(default=None, max_length=1_000)

    @model_validator(mode="after")
    def require_one_lookup(self) -> "QueryRequest":
        if not self.ticket_id and not self.vehicle_reg:
            raise ValueError("ticket_id or vehicle_reg is required; natural-language mode is not enabled")
        if self.ticket_id and self.vehicle_reg:
            raise ValueError("supply only one lookup key")
        return self


class ExplainRequest(QueryRequest):
    question: str = Field(min_length=1, max_length=1_000)


def _decoded_quarantine(store: ContextStore) -> list[dict[str, Any]]:
    ticket_rows = store.read_rows(
        """SELECT quarantine_id, entity_key AS ticket_id, reasons_json, sanitized_summary_json
           FROM quarantine WHERE entity_type='ticket' ORDER BY entity_key, quarantine_id"""
    )
    file_rows = store.read_rows(
        "SELECT quarantine_id, reasons_json, safe_summary_json FROM file_quarantine ORDER BY quarantine_id"
    )
    result = [
        {"quarantine_id": row["quarantine_id"], "ticket_id": row["ticket_id"],
         "reasons": json.loads(row["reasons_json"]), "summary": json.loads(row["sanitized_summary_json"])}
        for row in ticket_rows
    ]
    result.extend(
        {"quarantine_id": row["quarantine_id"], "ticket_id": None,
         "reasons": json.loads(row["reasons_json"]), "summary": json.loads(row["safe_summary_json"])}
        for row in file_rows
    )
    return sorted(result, key=lambda row: (str(row["ticket_id"] or ""), row["quarantine_id"]))


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or default_settings()

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        get_store(settings)
        yield

    app = FastAPI(
        title="Meridian Freight API",
        version="0.1.0",
        description="PII-safe deterministic breakdown-to-resolution API.",
        lifespan=lifespan,
    )

    def store_dependency() -> ContextStore:
        return get_store(settings)

    @app.get("/health")
    def health(store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        return {"status": "ok", "service": "meridian-backend", "database_ready": store.database_path.exists()}

    @app.post("/run")
    def run(request: RunRequest) -> dict[str, Any]:
        try:
            return run_pipeline(settings, request.input_path)
        except (OSError, ValueError) as exc:
            raise HTTPException(status_code=422, detail="run request was rejected safely") from exc

    @app.post("/approve")
    def approve(request: ApprovalRequest, store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        try:
            result = approve_message(store, request.ticket_id, request.approved_by, request.approved_at)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="approval request was rejected safely") from exc
        from .exporter import export_all
        export_all(store, settings.outputs_dir, settings.audit_dir)
        return result

    @app.post("/query")
    def query(request: QueryRequest, store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        # `question` is intentionally ignored in Phase 1. Phase 2 can explain these cited facts,
        # but will remain unable to execute decisions or actions.
        return query_ticket(store, request.ticket_id) if request.ticket_id else query_vehicle(store, request.vehicle_reg or "")

    @app.post("/explain")
    def explain_evidence(request: ExplainRequest, store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        try:
            result = explain(settings, store, request.question, request.ticket_id, request.vehicle_reg)
        except ExplanationUnavailable as exc:
            raise HTTPException(status_code=503, detail="grounded explanation is temporarily unavailable") from exc
        return {
            "status": result.status,
            "explanation": result.explanation,
            "reason": result.reason,
            "citations": result.citations,
            "evidence": result.evidence,
        }

    @app.get("/ticket/{ticket_id}")
    def ticket(ticket_id: str, store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        return query_ticket(store, ticket_id)

    @app.get("/tickets")
    def tickets(store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        rows = store.read_rows(
            "SELECT ticket_id, normalized_vehicle, created_at FROM tickets ORDER BY ticket_id"
        )
        return {"status": "FOUND", "tickets": rows, "count": len(rows)}

    @app.get("/vehicles")
    def vehicles(store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        rows = store.read_rows(
            """SELECT vehicle_reg, year, bs_stage, engine_heater, home_hub, fleet_status, resolution_status
               FROM vehicles ORDER BY vehicle_reg"""
        )
        return {"status": "FOUND", "vehicles": rows, "count": len(rows)}

    @app.get("/quarantine")
    def quarantine(store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        rows = _decoded_quarantine(store)
        return {"status": "FOUND", "quarantine": rows, "count": len(rows)}

    @app.get("/approvals/pending")
    def pending_approvals(store: ContextStore = Depends(store_dependency)) -> dict[str, object]:
        rows = store.read_rows(
            """SELECT pm.message_id, pm.ticket_id, pm.approval_context_json, pm.citations_json
               FROM pending_messages pm
               LEFT JOIN sent_messages sm ON sm.ticket_id = pm.ticket_id
               WHERE sm.ticket_id IS NULL
               ORDER BY pm.ticket_id"""
        )
        approvals = [
            {
                "message_id": row["message_id"],
                "ticket_id": row["ticket_id"],
                "approval_context": json.loads(row["approval_context_json"]),
                "citations": json.loads(row["citations_json"]),
            }
            for row in rows
        ]
        return {"status": "FOUND", "approvals": approvals, "count": len(approvals)}

    return app


app = create_app()
