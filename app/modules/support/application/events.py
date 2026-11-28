"""
Support realtime events (Phase 27, REQ-73)

One compact event per change a person on an open screen may care about. The event carries only
ids and small facts; screens fetch the rendered fragment themselves, so no text of a message
travels through the bus.

Python 3.13+
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.modules.support.domain.enums import TicketStatus
from app.modules.support.domain.ticket_rules import REQUESTER_LABELS

TICKET_CREATED = "ticket.created"
TICKET_UPDATED = "ticket.updated"        # data.change: assigned | status | priority | category | routed
MESSAGE_CREATED = "message.created"
MESSAGE_DELETED = "message.deleted"      # public unless the message was an internal note
NOTE_CREATED = "note.created"            # internal, staff only
TYPING = "typing"                        # ephemeral: never stored or replayed


@dataclass(slots=True, kw_only=True)
class SupportEvent:
    """`public` False means staff only (internal notes, assignments, priority changes)."""

    type: str
    ticket_id: str
    ticket_no: str = ""
    team_id: str | None = None
    requester_id: str = ""
    assigned_to: str | None = None
    previous_assignee: str | None = None
    public: bool = True
    data: dict[str, Any] = field(default_factory=dict)
    id: int = 0

    @property
    def ephemeral(self) -> bool:
        return self.type == TYPING

    def to_json(self) -> str:
        return json.dumps(asdict(self), separators=(",", ":"))

    @classmethod
    def from_json(cls, text: str) -> "SupportEvent":
        return cls(**json.loads(text))

    def for_staff(self) -> dict[str, Any]:
        return {
            "id": self.id, "type": self.type, "ticket_id": self.ticket_id, "ticket_no": self.ticket_no,
            "team_id": self.team_id, "assigned_to": self.assigned_to,
            "previous_assignee": self.previous_assignee, "data": self.data,
        }

    def for_requester(self) -> dict[str, Any]:
        """What the app sees: no team, no assignee, no staff detail; a status comes with the app's label."""
        data = {key: value for key, value in self.data.items() if key in {"change", "status", "message_id", "typing"}}
        if "status" in data:
            data["status_label"] = _requester_label(data["status"])
        return {"id": self.id, "type": self.type, "ticket_id": self.ticket_id, "ticket_no": self.ticket_no, "data": data}


def _requester_label(status: Any) -> str:
    try:
        return REQUESTER_LABELS[TicketStatus(status)]
    except (ValueError, KeyError):
        return str(status)
