from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from enum import StrEnum
from typing import Iterable


class RuleStatus(StrEnum):
    PASS = "PASS"
    FAIL = "FAIL"
    INSUFFICIENT_DATA = "INSUFFICIENT_DATA"


@dataclass(frozen=True)
class RuleResult:
    rule_id: str
    status: RuleStatus
    reason_code: str
    citations: tuple[str, ...]
    details: dict[str, object]


DISPATCHER_RULES = "dispatcher_interview.txt"
EMAIL_SHAKTI = "emails/thread_01_shakti_sla.txt"
EMAIL_VERTEX = "emails/thread_09_vertex_gate.txt"
EMAIL_APEX = "emails/thread_13_apex_rotation.txt"
EMAIL_ORION = "emails/thread_17_orion_age.txt"


def _result(rule_id: str, status: RuleStatus, reason_code: str, citations: Iterable[str], **details: object) -> RuleResult:
    return RuleResult(rule_id, status, reason_code, tuple(sorted(set(citations))), details)


def delhi_ncr_rule(ticket_date: date, bs_stage: str | None, route_touches_delhi_ncr: bool | None, citation: str) -> RuleResult:
    if route_touches_delhi_ncr is None:
        return _result("DELHI_NCR_WINTER_BS6_V1", RuleStatus.INSUFFICIENT_DATA, "route_topology_unknown", [citation])
    if not route_touches_delhi_ncr or ticket_date.month not in {10, 11, 12, 1, 2}:
        return _result("DELHI_NCR_WINTER_BS6_V1", RuleStatus.PASS, "not_winter_delhi_ncr", [citation])
    if bs_stage is None:
        return _result("DELHI_NCR_WINTER_BS6_V1", RuleStatus.INSUFFICIENT_DATA, "missing_bs_stage", [citation])
    return _result("DELHI_NCR_WINTER_BS6_V1", RuleStatus.PASS if bs_stage.upper() == "BS6" else RuleStatus.FAIL,
                   "bs6_required" if bs_stage.upper() == "BS6" else "bs4_disallowed", [citation], bs_stage=bs_stage)


def hill_route_rule(
    ticket_date: date,
    is_hill_route: bool | None,
    engine_heater: str | None,
    brake_work_dates: Iterable[date],
    citation: str,
) -> RuleResult:
    if is_hill_route is None:
        return _result("HILL_ROUTE_WINTER_SAFETY_V1", RuleStatus.INSUFFICIENT_DATA, "hill_route_classification_unknown", [citation])
    if not is_hill_route or ticket_date.month not in {11, 12, 1, 2}:
        return _result("HILL_ROUTE_WINTER_SAFETY_V1", RuleStatus.PASS, "not_winter_hill_route", [citation])
    if engine_heater is None:
        return _result("HILL_ROUTE_WINTER_SAFETY_V1", RuleStatus.INSUFFICIENT_DATA, "missing_engine_heater", [citation])
    if engine_heater.upper() != "YES":
        return _result("HILL_ROUTE_WINTER_SAFETY_V1", RuleStatus.FAIL, "engine_heater_required", [citation])
    cutoff = ticket_date - timedelta(days=30)
    if any(cutoff <= work_date <= ticket_date for work_date in brake_work_dates):
        return _result("HILL_ROUTE_WINTER_SAFETY_V1", RuleStatus.FAIL, "brake_work_within_30_days", [citation])
    return _result("HILL_ROUTE_WINTER_SAFETY_V1", RuleStatus.PASS, "heater_and_brake_check_passed", [citation])


def shakti_sla_rule(client: str, citations: Iterable[str]) -> RuleResult:
    if client != "Shakti Cement":
        return _result("SHAKTI_SLA_36H_V1", RuleStatus.PASS, "not_shakti", citations)
    return _result("SHAKTI_SLA_36H_V1", RuleStatus.PASS, "operational_sla_36_hours", citations, sla_hours=36)


def vertex_cutoff_rule(client: str, destination: str, arrival_local_hour: int | None, citations: Iterable[str]) -> RuleResult:
    if client != "Vertex Retail" or destination != "Ludhiana":
        return _result("VERTEX_LUDHIANA_GATE_V1", RuleStatus.PASS, "not_vertex_ludhiana", citations)
    if arrival_local_hour is None:
        return _result("VERTEX_LUDHIANA_GATE_V1", RuleStatus.INSUFFICIENT_DATA, "arrival_eta_unknown", citations)
    if arrival_local_hour >= 18:
        return _result("VERTEX_LUDHIANA_GATE_V1", RuleStatus.PASS, "scheduled_next_morning_0800", citations,
                       delivery_status="SCHEDULED_MORNING", delivery_hour=8)
    return _result("VERTEX_LUDHIANA_GATE_V1", RuleStatus.PASS, "within_gate_hours", citations)


def apex_rotation_rule(client: str, candidate_is_previous_incident_vehicle: bool | None, citations: Iterable[str]) -> RuleResult:
    if client != "Apex Chemicals":
        return _result("APEX_ROTATION_V1", RuleStatus.PASS, "not_apex", citations)
    if candidate_is_previous_incident_vehicle is None:
        return _result("APEX_ROTATION_V1", RuleStatus.INSUFFICIENT_DATA, "next_dispatch_history_unknown", citations)
    return _result("APEX_ROTATION_V1", RuleStatus.FAIL if candidate_is_previous_incident_vehicle else RuleStatus.PASS,
                   "same_vehicle_next_dispatch_disallowed" if candidate_is_previous_incident_vehicle else "rotated_vehicle", citations)


def orion_age_rule(client: str, vehicle_year: int | None, citations: Iterable[str]) -> RuleResult:
    if client != "Orion Pharma":
        return _result("ORION_MODEL_YEAR_V1", RuleStatus.PASS, "not_orion", citations)
    if vehicle_year is None:
        return _result("ORION_MODEL_YEAR_V1", RuleStatus.INSUFFICIENT_DATA, "vehicle_year_unknown_or_conflicted", citations)
    return _result("ORION_MODEL_YEAR_V1", RuleStatus.PASS if vehicle_year >= 2020 else RuleStatus.FAIL,
                   "year_2020_or_later" if vehicle_year >= 2020 else "vehicle_too_old", citations, vehicle_year=vehicle_year)


def monsoon_eta_rule(ticket_date: date, east_of_lucknow: bool | None, citations: Iterable[str]) -> RuleResult:
    if ticket_date.month not in {7, 8, 9}:
        return _result("MONSOON_EAST_ETA_V1", RuleStatus.PASS, "not_monsoon", citations, eta_multiplier=1.0)
    if east_of_lucknow is None:
        return _result("MONSOON_EAST_ETA_V1", RuleStatus.INSUFFICIENT_DATA, "east_of_lucknow_classification_unknown", citations)
    return _result("MONSOON_EAST_ETA_V1", RuleStatus.PASS, "eta_padded_20_percent" if east_of_lucknow else "not_east_of_lucknow",
                   citations, eta_multiplier=1.2 if east_of_lucknow else 1.0)


def replacement_source_rule(km_from_origin: float, nearest_hub_distance_known: bool, citations: Iterable[str]) -> RuleResult:
    if km_from_origin <= 50:
        return _result("REPLACEMENT_SOURCE_V1", RuleStatus.PASS, "source_origin_hub", citations, source_strategy="ORIGIN_HUB")
    if not nearest_hub_distance_known:
        return _result("REPLACEMENT_SOURCE_V1", RuleStatus.INSUFFICIENT_DATA, "nearest_hub_distance_unknown", citations)
    return _result("REPLACEMENT_SOURCE_V1", RuleStatus.PASS, "source_nearest_eligible_hub", citations, source_strategy="NEAREST_HUB")


def maintenance_overdue_rule(days_past_due: int | None, citations: Iterable[str]) -> RuleResult:
    if days_past_due is None:
        return _result("MAINTENANCE_GROUNDING_V1", RuleStatus.INSUFFICIENT_DATA, "service_due_date_unknown", citations)
    return _result("MAINTENANCE_GROUNDING_V1", RuleStatus.FAIL if days_past_due > 30 else RuleStatus.PASS,
                   "more_than_30_days_overdue" if days_past_due > 30 else "within_service_grace", citations)


def jugaad_rule(
    ticket_date: date,
    temporary_fix_date: date | None,
    permanent_repair_confirmed: bool | None,
    within_home_region: bool | None,
    citations: Iterable[str],
) -> RuleResult:
    if temporary_fix_date is None:
        return _result("JUGAAD_RESTRICTION_V1", RuleStatus.PASS, "no_known_temporary_fix", citations)
    if permanent_repair_confirmed is None:
        return _result("JUGAAD_RESTRICTION_V1", RuleStatus.INSUFFICIENT_DATA, "permanent_repair_status_unknown", citations)
    if permanent_repair_confirmed:
        return _result("JUGAAD_RESTRICTION_V1", RuleStatus.PASS, "permanent_repair_confirmed", citations)
    if ticket_date > temporary_fix_date + timedelta(days=7):
        return _result("JUGAAD_RESTRICTION_V1", RuleStatus.FAIL, "permanent_repair_overdue", citations)
    if within_home_region is None:
        return _result("JUGAAD_RESTRICTION_V1", RuleStatus.INSUFFICIENT_DATA, "home_region_classification_unknown", citations)
    return _result("JUGAAD_RESTRICTION_V1", RuleStatus.PASS if within_home_region else RuleStatus.FAIL,
                   "within_home_region" if within_home_region else "cannot_leave_home_region", citations)


def driver_night_rule(ticket_date: date, is_night_run: bool | None, solo: bool | None, eligible_after: date | None, citations: Iterable[str]) -> RuleResult:
    if is_night_run is None or solo is None:
        return _result("NEW_DRIVER_NIGHT_V1", RuleStatus.INSUFFICIENT_DATA, "night_or_pairing_unknown", citations)
    if not is_night_run or not solo:
        return _result("NEW_DRIVER_NIGHT_V1", RuleStatus.PASS, "not_solo_night_run", citations)
    if eligible_after is None:
        return _result("NEW_DRIVER_NIGHT_V1", RuleStatus.INSUFFICIENT_DATA, "driver_tenure_unknown", citations)
    return _result("NEW_DRIVER_NIGHT_V1", RuleStatus.PASS if ticket_date >= eligible_after else RuleStatus.FAIL,
                   "driver_tenure_sufficient" if ticket_date >= eligible_after else "new_driver_cannot_drive_solo_at_night", citations)

