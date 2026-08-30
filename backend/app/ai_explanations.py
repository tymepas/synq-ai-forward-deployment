from __future__ import annotations

import json
import os
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from dotenv import load_dotenv
from openai import OpenAI

from .config import Settings
from .db import ContextStore
from .query_service import query_ticket, query_vehicle
from .redaction import PIIRedactor, contains_raw_pii


DEFAULT_MODEL = "gpt-5"
MAX_OUTPUT_TOKENS = 350


class ExplanationUnavailable(RuntimeError):
    """Raised when a grounded explanation cannot reach the model service."""


@dataclass(frozen=True)
class GroundedExplanation:
    status: str
    explanation: str | None
    citations: list[str]
    evidence: dict[str, Any]
    reason: str | None = None


def _load_api_key(settings: Settings) -> str | None:
    # The key stays on the backend. dotenv does not override deployment-provided values.
    load_dotenv(settings.root.parent / ".env", override=False)
    key = os.getenv("OPENAI_API_KEY", "").strip()
    return key or None


def _safe_question(question: str) -> str:
    # Questions are transient and never persisted. Scrub recognizable PII before model use.
    return PIIRedactor().redact_text(question.strip()) or "Explain the recorded operational evidence."


def _safe_evidence(result: dict[str, Any]) -> dict[str, Any]:
    evidence = PIIRedactor().redact_value(result)
    serialized = json.dumps(evidence, sort_keys=True)
    if contains_raw_pii(serialized):
        raise ExplanationUnavailable("safe evidence check failed")
    return evidence


def _instruction() -> str:
    return (
        "You are Meridian Freight's explanation assistant. You explain only the supplied structured evidence. "
        "You do not make, change, recommend, or approve dispatch decisions. "
        "Do not infer facts not present in the evidence. If the evidence does not answer the question, say "
        "INSUFFICIENT_DATA and identify the missing evidence. Keep the answer concise and operational. "
        "Do not repeat personal data, credentials, free text, or source documents. "
        "The application will attach the authoritative evidence citations; do not invent citations."
    )


def explain(
    settings: Settings,
    store: ContextStore,
    question: str,
    ticket_id: str | None = None,
    vehicle_reg: str | None = None,
    client_factory: Callable[..., Any] = OpenAI,
) -> GroundedExplanation:
    """Retrieve deterministic backend evidence first, then ask GPT to explain it."""
    result = query_ticket(store, ticket_id) if ticket_id else query_vehicle(store, vehicle_reg or "")
    if result.get("status") == "INSUFFICIENT_DATA":
        return GroundedExplanation(
            status="INSUFFICIENT_DATA", explanation=None, citations=list(result.get("citations", [])),
            evidence=_safe_evidence(result), reason=str(result.get("reason", "evidence_unavailable")),
        )

    evidence = _safe_evidence(result)
    api_key = _load_api_key(settings)
    if not api_key:
        raise ExplanationUnavailable("OpenAI API key is not configured")

    try:
        response = client_factory(api_key=api_key).responses.create(
            model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
            instructions=_instruction(),
            input=(
                f"Operator question: {_safe_question(question)}\n\n"
                f"Authoritative structured evidence (JSON):\n{json.dumps(evidence, sort_keys=True)}"
            ),
            max_output_tokens=MAX_OUTPUT_TOKENS,
            store=False,
        )
    except Exception as exc:  # The API exception is intentionally not exposed to the browser.
        raise ExplanationUnavailable("OpenAI explanation service is unavailable") from exc

    explanation = (getattr(response, "output_text", "") or "").strip()
    if not explanation:
        return GroundedExplanation(
            status="INSUFFICIENT_DATA", explanation=None, citations=list(evidence.get("citations", [])),
            evidence=evidence, reason="model_returned_no_explanation",
        )
    return GroundedExplanation(
        status="EXPLAINED", explanation=PIIRedactor().redact_text(explanation),
        citations=list(evidence.get("citations", [])), evidence=evidence,
    )
