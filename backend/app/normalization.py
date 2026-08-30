from __future__ import annotations

import re


def normalize_vehicle_registration(value: object) -> str | None:
    if value is None:
        return None
    normalized = re.sub(r"[^A-Z0-9]", "", str(value).upper())
    return normalized or None


def normalize_ticket_id(value: object) -> str | None:
    if value is None:
        return None
    normalized = str(value).strip().upper()
    return normalized or None


def normalized_text(value: object) -> str | None:
    if value is None:
        return None
    result = " ".join(str(value).strip().split())
    return result or None

