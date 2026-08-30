from __future__ import annotations

import csv
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any


FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "ticket_id": ("ticket_id", "ticketId", "id", "case_id"),
    "created_at": ("created_at", "createdAt", "timestamp", "opened_at"),
    "vehicle": ("vehicle", "vehicle_reg", "vehicleReg", "registration_number"),
    "driver_id": ("driver_id", "driverId", "driver"),
    "origin_hub": ("origin_hub", "originHub", "origin"),
    "km_from_origin_hub": ("km_from_origin_hub", "kmFromOrigin", "distance_from_origin_km"),
    "destination": ("destination", "destinationHub", "dest"),
    "issue": ("issue", "problem", "breakdown_issue"),
    "severity": ("severity", "priority"),
    "client": ("client", "customer"),
    "status": ("status", "state"),
    "resolution_note": ("resolution_note", "resolution", "note"),
}
REQUIRED = tuple(key for key in FIELD_ALIASES if key != "resolution_note")


@dataclass(frozen=True)
class AdaptedInput:
    safe: bool
    records: tuple[dict[str, Any], ...]
    reasons: tuple[str, ...]
    mapping: dict[str, str]


def _load_rows(path: Path) -> list[dict[str, Any]]:
    suffix = path.suffix.lower()
    if suffix == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, dict):
            value = value.get("tickets") or value.get("records")
        if not isinstance(value, list) or not all(isinstance(row, dict) for row in value):
            raise ValueError("json_must_be_an_array_of_objects")
        return value
    if suffix == ".csv":
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle))
    raise ValueError("unsupported_ticket_file_extension")


def adapt_ticket_file(path: Path) -> AdaptedInput:
    try:
        rows = _load_rows(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        return AdaptedInput(False, (), (str(exc),), {})
    if not rows:
        return AdaptedInput(False, (), ("empty_ticket_file",), {})
    keys = {key for row in rows for key in row}
    mapping: dict[str, str] = {}
    for canonical, aliases in FIELD_ALIASES.items():
        matches = [alias for alias in aliases if alias in keys]
        if len(matches) > 1:
            return AdaptedInput(False, (), (f"ambiguous_alias_{canonical}",), {})
        if matches:
            mapping[canonical] = matches[0]
    missing = sorted(set(REQUIRED) - set(mapping))
    if missing:
        return AdaptedInput(False, (), tuple(f"missing_required_mapping_{field}" for field in missing), mapping)
    records = tuple({canonical: row.get(source) for canonical, source in mapping.items()} for row in rows)
    return AdaptedInput(True, records, (), mapping)

