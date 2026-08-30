from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any

from .normalization import normalize_ticket_id, normalize_vehicle_registration, normalized_text


REQUIRED_TICKET_FIELDS = (
    "ticket_id",
    "created_at",
    "vehicle",
    "driver_id",
    "origin_hub",
    "km_from_origin_hub",
    "destination",
    "issue",
    "severity",
    "client",
    "status",
)
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH"}
VALID_TICKET_STATUSES = {"OPEN", "CLOSED"}
KNOWN_ISSUES = {
    "fuel line leak", "suspension damage", "clutch slipping", "turbo failure", "radiator leak",
    "gearbox jam", "engine overheating", "brake failure warning", "tyre burst", "electrical failure",
}
KNOWN_CLIENTS = {"Shakti Cement", "Vertex Retail", "Apex Chemicals", "Orion Pharma", "Internal"}
KNOWN_HUBS = {"Ambala", "Chandigarh", "Delhi", "Gurgaon", "Jaipur", "Kanpur", "Lucknow", "Ludhiana", "Rudrapur"}


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    reasons: tuple[str, ...]
    ticket_id: str | None
    normalized_vehicle: str | None
    normalized: dict[str, Any]


def validate_ticket(record: dict[str, Any]) -> ValidationResult:
    normalized = {key: normalized_text(value) if isinstance(value, str) else value for key, value in record.items()}
    ticket_id = normalize_ticket_id(record.get("ticket_id"))
    normalized["ticket_id"] = ticket_id
    normalized_vehicle = normalize_vehicle_registration(record.get("vehicle"))
    normalized["vehicle_normalized"] = normalized_vehicle
    reasons: list[str] = []

    for field in REQUIRED_TICKET_FIELDS:
        if record.get(field) in (None, ""):
            reasons.append(f"missing_{field}")

    timestamp = record.get("created_at")
    if timestamp not in (None, ""):
        try:
            datetime.fromisoformat(str(timestamp).replace("Z", "+00:00"))
        except ValueError:
            reasons.append("invalid_created_at")

    severity = normalized_text(record.get("severity"))
    if severity and severity.upper() not in VALID_SEVERITIES:
        reasons.append("invalid_severity")
    normalized["severity"] = severity.upper() if severity else severity

    status = normalized_text(record.get("status"))
    if status and status.upper() not in VALID_TICKET_STATUSES:
        reasons.append("invalid_status")
    normalized["status"] = status.upper() if status else status

    km = record.get("km_from_origin_hub")
    if km not in (None, ""):
        try:
            normalized["km_from_origin_hub"] = float(km)
            if normalized["km_from_origin_hub"] < 0:
                reasons.append("negative_km_from_origin_hub")
        except (TypeError, ValueError):
            reasons.append("invalid_km_from_origin_hub")

    return ValidationResult(
        valid=not reasons,
        reasons=tuple(sorted(set(reasons))),
        ticket_id=ticket_id,
        normalized_vehicle=normalized_vehicle,
        normalized=normalized,
    )


def safe_ticket_context(normalized: dict[str, Any]) -> dict[str, Any]:
    """Persist only operationally necessary, non-free-text ticket context."""
    client = normalized_text(normalized.get("client"))
    origin = normalized_text(normalized.get("origin_hub"))
    destination = normalized_text(normalized.get("destination"))
    issue = normalized_text(normalized.get("issue"))
    driver_id = normalized_text(normalized.get("driver_id"))
    return {
        "ticket_id": normalized.get("ticket_id"),
        "created_at": normalized.get("created_at"),
        "vehicle_normalized": normalized.get("vehicle_normalized"),
        "driver_id": driver_id if driver_id and driver_id.startswith("DRV-") else "[UNRECOGNIZED_DRIVER]",
        "origin_hub": origin if origin in KNOWN_HUBS else "[UNRECOGNIZED_HUB]",
        "km_from_origin_hub": normalized.get("km_from_origin_hub"),
        "destination": destination if destination in KNOWN_HUBS else "[UNRECOGNIZED_HUB]",
        "issue": issue if issue in KNOWN_ISSUES else "[UNCLASSIFIED_ISSUE]",
        "severity": normalized.get("severity"),
        "client": client if client in KNOWN_CLIENTS else "[UNRECOGNIZED_CLIENT]",
        "status": normalized.get("status"),
    }
