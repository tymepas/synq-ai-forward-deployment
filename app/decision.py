from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Iterable

from .rules import (
    RuleResult,
    RuleStatus,
    apex_rotation_rule,
    delhi_ncr_rule,
    hill_route_rule,
    jugaad_rule,
    maintenance_overdue_rule,
    orion_age_rule,
)


@dataclass(frozen=True)
class Candidate:
    vehicle_reg: str
    home_hub: str | None
    fleet_status: str | None
    available: bool | None
    reserved: bool
    year: int | None
    bs_stage: str | None
    engine_heater: str | None
    days_past_due: int | None
    brake_work_dates: tuple[date, ...] = ()
    temporary_fix_date: date | None = None
    permanent_repair_confirmed: bool | None = None
    within_home_region: bool | None = None
    apex_previous_incident: bool | None = None
    overnight_wait: bool | None = None
    refrigerated_evidence: bool | None = None


@dataclass(frozen=True)
class ReplacementDecision:
    status: str
    selected_vehicle_reg: str | None
    candidate_results: dict[str, tuple[RuleResult, ...]]
    reason_codes: tuple[str, ...]


def evaluate_candidate(
    candidate: Candidate,
    *,
    ticket_date: date,
    client: str,
    origin_hub: str,
    route_touches_delhi_ncr: bool | None,
    is_hill_route: bool | None,
    citations: Iterable[str],
) -> tuple[RuleResult, ...]:
    citations = tuple(citations)
    results: list[RuleResult] = []
    if candidate.fleet_status != "Active":
        results.append(RuleResult("FLEET_STATUS_V1", RuleStatus.FAIL, "fleet_not_active", citations, {}))
    elif candidate.available is None:
        results.append(RuleResult("LIVE_AVAILABILITY_V1", RuleStatus.INSUFFICIENT_DATA, "live_availability_unknown", citations, {}))
    elif not candidate.available or candidate.reserved:
        results.append(RuleResult("LIVE_AVAILABILITY_V1", RuleStatus.FAIL, "unavailable_or_reserved", citations, {}))
    else:
        results.append(RuleResult("LIVE_AVAILABILITY_V1", RuleStatus.PASS, "available_and_unreserved", citations, {}))

    results.extend((
        delhi_ncr_rule(ticket_date, candidate.bs_stage, route_touches_delhi_ncr, citations[0]),
        hill_route_rule(ticket_date, is_hill_route, candidate.engine_heater, candidate.brake_work_dates, citations[0]),
        maintenance_overdue_rule(candidate.days_past_due, citations),
        apex_rotation_rule(client, candidate.apex_previous_incident, citations),
        orion_age_rule(client, candidate.year, citations),
        jugaad_rule(ticket_date, candidate.temporary_fix_date, candidate.permanent_repair_confirmed,
                    candidate.within_home_region, citations),
    ))
    if client == "Orion Pharma" and candidate.overnight_wait is None:
        results.append(RuleResult("ORION_REFRIGERATION_V1", RuleStatus.INSUFFICIENT_DATA,
                                  "overnight_wait_plan_unknown", citations, {}))
    elif client == "Orion Pharma" and candidate.overnight_wait and candidate.refrigerated_evidence is not True:
        results.append(RuleResult("ORION_REFRIGERATION_V1", RuleStatus.FAIL,
                                  "unrefrigerated_overnight_wait_not_allowed", citations, {}))
    else:
        results.append(RuleResult("ORION_REFRIGERATION_V1", RuleStatus.PASS,
                                  "no_unrefrigerated_overnight_wait", citations, {}))

    if candidate.home_hub != origin_hub:
        results.append(RuleResult("REPLACEMENT_HUB_V1", RuleStatus.FAIL, "wrong_source_hub", citations,
                                  {"required_hub": origin_hub}))
    else:
        results.append(RuleResult("REPLACEMENT_HUB_V1", RuleStatus.PASS, "origin_hub_vehicle", citations, {}))
    return tuple(results)


def select_origin_hub_replacement(
    candidates: Iterable[Candidate],
    **context: object,
) -> ReplacementDecision:
    candidate_results: dict[str, tuple[RuleResult, ...]] = {}
    eligible: list[Candidate] = []
    for candidate in sorted(candidates, key=lambda item: item.vehicle_reg):
        results = evaluate_candidate(candidate, **context)
        candidate_results[candidate.vehicle_reg] = results
        if all(result.status == RuleStatus.PASS for result in results):
            eligible.append(candidate)
    if not eligible:
        reason_codes = sorted({result.reason_code for results in candidate_results.values() for result in results
                               if result.status != RuleStatus.PASS})
        return ReplacementDecision("MANUAL_HOLD", None, candidate_results, tuple(reason_codes))
    client = str(context["client"])
    selected = sorted(eligible, key=lambda item: (-(item.year or -1), item.vehicle_reg))[0] if client == "Orion Pharma" else eligible[0]
    return ReplacementDecision("REPLACEMENT_SELECTED", selected.vehicle_reg, candidate_results, ())

