from __future__ import annotations

import json

from .db import ContextStore
from .normalization import normalize_ticket_id, normalize_vehicle_registration
from .models import safe_ticket_context


def query_ticket(store: ContextStore, ticket_id: str) -> dict[str, object]:
    canonical_id = normalize_ticket_id(ticket_id)
    rows = store.read_rows(
        """SELECT t.ticket_id, t.normalized_vehicle, t.created_at, t.normalized_json,
                  tr.source_record_id, wo.work_order_id, pm.message_id
           FROM tickets t
           JOIN ticket_records tr ON tr.source_record_id=t.source_record_id
           LEFT JOIN work_orders wo ON wo.ticket_id=t.ticket_id
           LEFT JOIN pending_messages pm ON pm.ticket_id=t.ticket_id
           WHERE t.ticket_id=?""",
        (canonical_id,),
    )
    if not rows:
        return {"status": "INSUFFICIENT_DATA", "reason": "ticket_not_found", "citations": []}
    row = rows[0]
    audits = store.read_rows(
        "SELECT outcome, details_json, citations_json FROM audit_events WHERE ticket_id=? ORDER BY step, event_id",
        (canonical_id,),
    )
    citations = sorted({row["source_record_id"], *(citation for audit in audits for citation in json.loads(audit["citations_json"]))})
    decision = next((json.loads(audit["details_json"]) for audit in audits if audit["outcome"] in {"MANUAL_HOLD", "REPLACEMENT_SELECTED"}), None)
    return {
        "status": "FOUND",
        "ticket": safe_ticket_context(json.loads(row["normalized_json"])),
        "work_order_id": row["work_order_id"],
        "pending_message_id": row["message_id"],
        "decision": decision or {"status": "INSUFFICIENT_DATA", "reason": "not_processed"},
        "citations": citations,
    }


def query_vehicle(store: ContextStore, vehicle_reg: str) -> dict[str, object]:
    canonical_reg = normalize_vehicle_registration(vehicle_reg)
    rows = store.read_rows(
        """SELECT vehicle_reg, vehicle_id, model, year, bs_stage, engine_heater, home_hub,
                  capacity_tonnes, fleet_status, resolution_status, source_citation
           FROM vehicles WHERE vehicle_reg=?""",
        (canonical_reg,),
    )
    if not rows:
        return {"status": "INSUFFICIENT_DATA", "reason": "vehicle_not_found", "citations": []}
    vehicle = rows[0]
    conflicts = store.read_rows(
        """SELECT field_name, material, resolution_status, citations_json FROM entity_conflicts
           WHERE entity_type='vehicle' AND entity_key=? ORDER BY field_name""",
        (canonical_reg,),
    )
    citations = sorted({vehicle.pop("source_citation"), *(citation for conflict in conflicts for citation in json.loads(conflict["citations_json"]))})
    return {
        "status": "FOUND" if vehicle["resolution_status"] == "RESOLVED" else "INSUFFICIENT_DATA",
        "vehicle": vehicle,
        "conflicts": [{"field_name": item["field_name"], "material": bool(item["material"]),
                       "resolution_status": item["resolution_status"]} for item in conflicts],
        "citations": citations,
    }
