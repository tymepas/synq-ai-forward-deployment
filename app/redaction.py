from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any


PHONE_RE = re.compile(r"(?<!\d)(?:\+91[\s-]?)?[6-9]\d{9}(?!\d)")
AADHAAR_RE = re.compile(r"(?<!\d)\d{4}[\s-]\d{4}[\s-]\d{4}(?!\d)")
DL_RE = re.compile(r"(?<![A-Z0-9])[A-Z]{2}\d{2}[\s-]?\d{11}(?!\d)", re.IGNORECASE)
EMAIL_RE = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)


class PIIRedactor:
    """Conservative, deterministic PII scrubber for all persisted text."""

    def __init__(self, names: Sequence[str] = ()) -> None:
        clean_names = sorted(
            {name.strip() for name in names if name and name.strip()}, key=len, reverse=True
        )
        self._name_patterns = [
            re.compile(rf"(?<![A-Za-z]){re.escape(name)}(?![A-Za-z])", re.IGNORECASE)
            for name in clean_names
        ]

    def redact_text(self, value: str | None) -> str | None:
        if value is None:
            return None
        redacted = str(value)
        redacted = AADHAAR_RE.sub("[REDACTED_AADHAAR]", redacted)
        redacted = DL_RE.sub("[REDACTED_DL]", redacted)
        redacted = PHONE_RE.sub("[REDACTED_PHONE]", redacted)
        redacted = EMAIL_RE.sub("[REDACTED_EMAIL]", redacted)
        for pattern in self._name_patterns:
            redacted = pattern.sub("[REDACTED_NAME]", redacted)
        return redacted

    def redact_value(self, value: Any, field_name: str | None = None) -> Any:
        sensitive_field = (field_name or "").lower()
        if sensitive_field and any(token in sensitive_field for token in (
            "name", "phone", "aadhaar", "license", "dl_number", "email", "recipient", "mechanic"
        )):
            return f"[REDACTED_{field_name.upper()}]" if value not in (None, "") else value
        if isinstance(value, str):
            return self.redact_text(value)
        if isinstance(value, Mapping):
            return {str(k): self.redact_value(v, str(k)) for k, v in value.items()}
        if isinstance(value, list):
            return [self.redact_value(v) for v in value]
        return value


def contains_raw_pii(value: Any) -> bool:
    """Used by regression tests and export gates; false positives are safe."""
    if isinstance(value, Mapping):
        return any(contains_raw_pii(v) for v in value.values())
    if isinstance(value, list):
        return any(contains_raw_pii(v) for v in value)
    if not isinstance(value, str):
        return False
    return any(pattern.search(value) for pattern in (PHONE_RE, AADHAAR_RE, DL_RE, EMAIL_RE))
