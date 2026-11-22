"""
Technical Support pushes (Phase 28, REQ-77)

What support tells a requester's phone, through the shared `NotificationService` (source "support").
Called by the ticket handlers inside the ticket change's transaction:

- staff reply              → "Reply on TS-…", the message cut to 100 characters (a file: a fixed line);
- a status move by staff   → "TS-…: In review / In progress / Waiting for your reply";
- resolved                 → "TS-… is resolved".

Never for internal notes, and never for the requester's own reply, close or reopen. Replies are skipped
while the requester has the support chat open (they see it live).

Python 3.13+
"""

from __future__ import annotations

from app.modules.notification.application.service import NotificationService, cut
from app.modules.support.domain import ticket_rules
from app.modules.support.domain.entities import Ticket
from app.modules.support.domain.enums import TicketStatus

SOURCE = "support"
REPLY = "TICKET_REPLY"
STATUS = "TICKET_STATUS"
RESOLVED = "TICKET_RESOLVED"
BODY_LIMIT = 100


class SupportPush:

    __slots__ = ("_notifications",)

    def __init__(self, notifications: NotificationService) -> None:
        self._notifications = notifications

    async def _send(self, ticket: Ticket, kind: str, title: str, body: str, *, skip_if_online: bool) -> None:
        await self._notifications.notify(
            user_id=ticket.requester_user_id,
            source=SOURCE,
            type=kind,
            title=title,
            body=cut(body, BODY_LIMIT),
            reference_id=str(ticket.id),
            data={"ticket_no": ticket.ticket_no},
            skip_if_online=skip_if_online,
        )

    async def staff_replied(self, ticket: Ticket, text: str, *, is_file: bool = False) -> None:
        await self._send(
            ticket, REPLY, f"Reply on {ticket.ticket_no}",
            "The support team sent you a file." if is_file else text, skip_if_online=True,
        )

    async def status_changed(self, ticket: Ticket, status: TicketStatus) -> None:
        if status is TicketStatus.RESOLVED:
            await self._send(
                ticket, RESOLVED, f"{ticket.ticket_no} is resolved",
                "Your problem is marked as solved. Reopen the ticket if it is not.", skip_if_online=False,
            )
            return
        label = ticket_rules.REQUESTER_LABELS.get(status, status.label)
        await self._send(ticket, STATUS, f"{ticket.ticket_no}: {label}", ticket.subject, skip_if_online=True)
