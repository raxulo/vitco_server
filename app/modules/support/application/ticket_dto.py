"""
Ticket Application DTOs (Phase 26)

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.modules.support.domain.entities import Ticket, TicketEvent, TicketMessage


@dataclass(slots=True, kw_only=True)
class TicketView:
    """A ticket with its thread and timeline, already filtered for the reader (REQ-71)."""

    ticket: Ticket
    messages: list[TicketMessage] = field(default_factory=list)
    events: list[TicketEvent] = field(default_factory=list)
