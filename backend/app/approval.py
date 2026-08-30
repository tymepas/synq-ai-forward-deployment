from __future__ import annotations

import re
import json
from datetime import datetime

from .db import ContextStore


APPROVER_HANDLE_RE = re.compile(r"^(?:role|operator)-[a-z0-9_-]{2,32}$")


def approve_message(store: ContextStore, ticket_id: str, approved_by: str, approved_at: str) -> dict[str, object]:
    """Record a human-approved outbox send exactly once; never perform network delivery."""
    ticket_id = ticket_id.strip().upper()
    approved_by = approved_by.strip()
    if not APPROVER_HANDLE_RE.fullmatch(approved_by):
        raise ValueError("approved_by must be an opaque role- or operator- handle")
    try:
        datetime.fromisoformat(approved_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise ValueError("approved_at must be an ISO-8601 timestamp") from exc
    message_id, created = store.create_sent_message(ticket_id, approved_by, approved_at)
    if created:
        pending = store.read_rows("SELECT citations_json FROM pending_messages WHERE ticket_id=?", (ticket_id,))
        citations = [] if not pending else json.loads(pending[0]["citations_json"])
        store.audit(ticket_id, "approval", "SENT", approved_at, citations,
                    {"message_id": message_id, "approved_by": approved_by}, actor="human_approval")
    return {"ticket_id": ticket_id, "message_id": message_id, "created": created}
