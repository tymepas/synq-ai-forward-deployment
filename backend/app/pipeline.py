from __future__ import annotations

import json
from datetime import date, datetime
from typing import Any

from .db import ContextStore
from .decision import Candidate, ReplacementDecision, select_origin_hub_replacement
from .rules import (
    RuleResult,
    RuleStatus,
    driver_night_rule,
    monsoon_eta_rule,
    replacement_source_rule,
    shakti_sla_rule,
    vertex_cutoff_rule,
)


DELHI_NCR = {"Delhi", "Gurgaon", "Faridabad", "Noida"}


def _source_id(store: ContextStore, relative_path: str) -> str:
    rows = store.read_rows("SELECT source_id FROM sources WHERE relative_path = ? ORDER BY source_id", (relative_path,))
    return rows[0]["source_id"] if rows else "SOURCE_UNAVAILABLE"


def _rule_citations(store: ContextStore, relative_path: str) -> list[str]:
    return [_source_id(store, relative_path)]


def _parse_date(value: str) -> date:
    return datetime.fromisoformat(value.replace("Z", "+00:00")).date()


def _maintenance_dates(store: ContextStore, vehicle_reg: str, ticket_date: date, feature: str) -> list[date]:
    rows = store.read_rows(
        """SELECT event_date FROM maintenance_events
           WHERE vehicle_reg = ? AND event_date <= ? AND notes_redacted LIKE ? ORDER BY event_date""",
        (vehicle_reg, ticket_date.isoformat(), f"%{feature}%"),
    )
    return [date.fromisoformat(row["event_date"][:10]) for row in rows]


def _candidate_rows(store: ContextStore, origin_hub: str, ticket_date: date) -> list[Candidate]:
    rows = store.read_rows("SELECT * FROM vehicles WHERE home_hub = ? ORDER BY vehicle_reg", (origin_hub,))
    candidates: list[Candidate] = []
    for row in rows:
        temporary_dates = _maintenance_dates(store, row["vehicle_reg"], ticket_date, "temporary_fix")
        candidates.append(Candidate(
            vehicle_reg=row["vehicle_reg"], home_hub=row["home_hub"], fleet_status=row["fleet_status"],
            # Fleet status is not a live availability feed. Keep this intentionally unknown.
            available=None, reserved=False, year=row["year"], bs_stage=row["bs_stage"],
            engine_heater=row["engine_heater"], days_past_due=None,
            brake_work_dates=tuple(_maintenance_dates(store, row["vehicle_reg"], ticket_date, "brake_work")),
            temporary_fix_date=max(temporary_dates) if temporary_dates else None,
            permanent_repair_confirmed=None, within_home_region=None,
            apex_previous_incident=None, overnight_wait=None, refrigerated_evidence=None,
        ))
    return candidates


def _result_payload(results: list[RuleResult] | tuple[RuleResult, ...]) -> list[dict[str, Any]]:
    return [{"rule_id": result.rule_id, "status": result.status.value, "reason_code": result.reason_code,
             "citations": list(result.citations), "details": result.details} for result in results]


def _recipient(client: str) -> str:
    return {
        "Shakti Cement": "client_ops:shakti",
        "Vertex Retail": "client_ops:vertex",
        "Apex Chemicals": "client_ops:apex",
        "Orion Pharma": "client_ops:orion",
    }.get(client, "internal_ops")


def process_tickets(store: ContextStore) -> dict[str, int]:
    """Create one work order and one approval-gated draft for each valid canonical ticket."""
    rows = store.read_rows(
        """SELECT t.ticket_id, t.normalized_vehicle, t.created_at, t.normalized_json, tr.source_record_id
           FROM tickets t JOIN ticket_records tr ON tr.source_record_id=t.source_record_id
           WHERE NOT EXISTS (SELECT 1 FROM work_orders wo WHERE wo.ticket_id=t.ticket_id)
           ORDER BY t.ticket_id"""
    )
    counts = {"processed": 0, "manual_holds": 0, "replacements": 0}
    dispatcher_citation = _rule_citations(store, "dispatcher_interview.txt")
    shakti_citations = dispatcher_citation + _rule_citations(store, "emails/thread_01_shakti_sla.txt")
    vertex_citations = dispatcher_citation + _rule_citations(store, "emails/thread_09_vertex_gate.txt")

    for row in rows:
        ticket = json.loads(row["normalized_json"])
        ticket_date = _parse_date(ticket["created_at"])
        ticket_citation = f"{row['source_record_id']}"
        client = ticket["client"]
        route_touches = True if ticket["origin_hub"] in DELHI_NCR or ticket["destination"] in DELHI_NCR else None
        hill_route = True if ticket["destination"] == "Rudrapur" else None

        common_results = [
            shakti_sla_rule(client, shakti_citations),
            vertex_cutoff_rule(client, ticket["destination"], None, vertex_citations),
            monsoon_eta_rule(ticket_date, None, dispatcher_citation),
        ]
        driver_rows = store.read_rows("SELECT night_solo_eligible_after, source_citation FROM drivers WHERE driver_id=?", (ticket["driver_id"],))
        driver_eligible_after = date.fromisoformat(driver_rows[0]["night_solo_eligible_after"]) if driver_rows else None
        common_results.append(driver_night_rule(ticket_date, None, None, driver_eligible_after, dispatcher_citation))
        source_result = replacement_source_rule(float(ticket["km_from_origin_hub"]), False, dispatcher_citation)
        common_results.append(source_result)

        citations = sorted({ticket_citation, *dispatcher_citation, *shakti_citations, *vertex_citations})
        store.audit(row["ticket_id"], "enrichment", "PASS", row["created_at"], citations,
                    {"trip_context": "historical_trips_not_used_for_live_availability", "vehicle": ticket["vehicle_normalized"]})
        store.audit(row["ticket_id"], "rules", "EVALUATED", row["created_at"], citations,
                    {"results": _result_payload(common_results)}, rule_id="RULE_ENGINE_V1")

        common_blocks = [result.reason_code for result in common_results if result.status != RuleStatus.PASS]
        if common_blocks:
            decision = ReplacementDecision("MANUAL_HOLD", None, {}, tuple(sorted(set(common_blocks))))
        elif source_result.status == RuleStatus.PASS and source_result.details.get("source_strategy") == "ORIGIN_HUB":
            decision = select_origin_hub_replacement(
                _candidate_rows(store, ticket["origin_hub"], ticket_date), ticket_date=ticket_date, client=client,
                origin_hub=ticket["origin_hub"], route_touches_delhi_ncr=route_touches,
                is_hill_route=hill_route, citations=tuple(citations),
            )
        else:
            decision = ReplacementDecision("MANUAL_HOLD", None, {}, (source_result.reason_code,))

        decision_payload = {
            "status": decision.status, "selected_vehicle_reg": decision.selected_vehicle_reg,
            "reason_codes": list(decision.reason_codes),
            "candidate_results": {key: _result_payload(value) for key, value in decision.candidate_results.items()},
        }
        store.audit(row["ticket_id"], "replacement_decision", decision.status, row["created_at"], citations,
                    decision_payload, rule_id="REPLACEMENT_SELECTION_V1")

        # The README requires a work order for every valid ticket. For a manual hold, the only
        # evidenced vehicle is the failed vehicle, so the work order is safely a repair/dispatch-review order.
        work_vehicle = decision.selected_vehicle_reg or ticket["vehicle_normalized"]
        work_order_id, _ = store.create_work_order(row["ticket_id"], work_vehicle, row["created_at"], citations)
        body = (
            f"Ticket {row['ticket_id']} requires manual dispatch review; no replacement has been automatically assigned."
            if decision.status == "MANUAL_HOLD" else
            f"Ticket {row['ticket_id']} has a replacement assignment pending human approval."
        )
        message_id, _ = store.create_pending_message(
            row["ticket_id"], _recipient(client), body,
            {"decision_status": decision.status, "reason_codes": list(decision.reason_codes), "work_order_id": work_order_id},
            citations,
        )
        store.audit(row["ticket_id"], "outbox", "PENDING_APPROVAL", row["created_at"], citations,
                    {"work_order_id": work_order_id, "message_id": message_id, "decision_status": decision.status})
        counts["processed"] += 1
        counts["manual_holds" if decision.status == "MANUAL_HOLD" else "replacements"] += 1
    return counts
