"""
Call Handler (Phase 29, REQ-78, D-5)

Click-to-call with a record. The requester's number is visible to every member (D-6); dialling it
through the portal needs `support.call.make`:

- `start_call` records the intent (who, which ticket, when), adds a staff-only timeline event and an
  audit row, and returns the number for the `tel:` link. A member has at most one open call: the same
  ticket returns the open one, another ticket is refused until its outcome is recorded.
- `finish_call` records outcome, duration and note; only the member who made the call can.

The number is never written to application logs.

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.support.application.event_bus import EventBus
from app.modules.support.application.events import TICKET_UPDATED, SupportEvent
from app.modules.support.application.guard import SupportGuard
from app.modules.support.application.validation import clean_text
from app.modules.support.domain.entities import AuditEntry, CallLog, Ticket, TicketEvent
from app.modules.support.domain.enums import AuditAction, CallOutcome, EventType
from app.modules.support.domain.exceptions import (
    CallAlreadyOpenException,
    CallNotFoundException,
    SupportValidationException,
    TicketNotFoundException,
)
from app.modules.support.domain.irepository import ISupportRepository, ITicketRepository
from app.modules.support.domain.permissions import SupportPermission
from app.modules.support.infrastructure.call_repository import CallRepository

MAX_DURATION_S = 6 * 3600


class CallHandler:

    __slots__ = ("_database", "_calls", "_tickets", "_support", "_guard", "_events")

    def __init__(
        self,
        *,
        database: DatabaseManager,
        calls: CallRepository,
        tickets: ITicketRepository,
        support: ISupportRepository,
        events: EventBus | None = None,
    ) -> None:
        self._database = database
        self._calls = calls
        self._tickets = tickets
        self._support = support
        self._guard = SupportGuard(support)
        self._events = events or EventBus()

    async def _visible_ticket(self, ctx, ticket_id: UUID) -> Ticket:
        from app.modules.support.application.ticket_handler import TicketHandler

        ticket = await self._tickets.get_ticket(ticket_id)
        if ticket is None or not TicketHandler._staff_can_see(ctx, ticket):
            raise TicketNotFoundException()
        return ticket

    def _emit(self, ticket: Ticket) -> None:
        self._events.after_commit(
            self._database.session,
            SupportEvent(
                type=TICKET_UPDATED, ticket_id=str(ticket.id), ticket_no=ticket.ticket_no,
                team_id=str(ticket.team_id) if ticket.team_id else None, requester_id=str(ticket.requester_user_id),
                assigned_to=str(ticket.assigned_to) if ticket.assigned_to else None, public=False,
                data={"change": "call"},
            ),
        )

    async def _record(self, ctx, ticket: Ticket, action: AuditAction, event: EventType, **meta) -> None:
        await self._tickets.add_event(
            TicketEvent(
                ticket_id=ticket.id, actor_user_id=ctx.user_id, event_type=event,
                to_value=meta.get("outcome"), meta=meta, is_public=False,
            )
        )
        await self._support.add_audit(
            AuditEntry(
                actor_id=ctx.user_id, action=str(action), entity="ticket", entity_id=str(ticket.id),
                team_id=ticket.team_id, meta={"ticket_no": ticket.ticket_no, **meta},
            )
        )
        self._emit(ticket)

    async def start_call(self, ticket_id: UUID, actor: CurrentUser | None) -> tuple[CallLog, str]:
        """(call, number to dial)."""
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.CALL_MAKE)
            ticket = await self._visible_ticket(ctx, ticket_id)
            if not ticket.requester_mobile:
                raise SupportValidationException("The requester has no phone number.")
            open_call = await self._calls.open_call(ctx.user_id)
            if open_call is not None:
                if open_call.ticket_id == ticket.id:
                    return open_call, ticket.requester_mobile
                raise CallAlreadyOpenException(
                    f"Record the outcome of your call on {open_call.ticket_no} first.",
                    details={"ticket_id": str(open_call.ticket_id), "call_id": str(open_call.id)},
                )
            call = CallLog(
                id=uuid4(), ticket_id=ticket.id, member_user_id=ctx.user_id,
                requester_user_id=ticket.requester_user_id, started_at=now_naive_ist(),
            )
            await self._calls.add(call)
            await self._record(ctx, ticket, AuditAction.CALL_STARTED, EventType.CALL_STARTED, call_id=str(call.id))
            created = await self._calls.get(call.id)
        return created or call, ticket.requester_mobile

    async def finish_call(
        self,
        call_id: UUID,
        *,
        outcome: str,
        duration_s: int | None,
        note: str | None,
        actor: CurrentUser | None,
    ) -> CallLog:
        try:
            result = CallOutcome(str(outcome or "").upper())
        except ValueError:
            raise SupportValidationException("Choose what happened on the call.") from None
        if duration_s is not None and not 0 <= int(duration_s) <= MAX_DURATION_S:
            raise SupportValidationException("Call length must be between 0 and 6 hours.")
        text = clean_text(note, label="Note", minimum=0, maximum=1000) or None

        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            call = await self._calls.get(call_id)
            # Only the member who called records the outcome; any other member is told it does not exist
            if call is None or call.member_user_id != ctx.user_id:
                raise CallNotFoundException()
            if not call.is_open:
                raise SupportValidationException("The outcome of this call is already recorded.")
            ticket = await self._tickets.get_ticket(call.ticket_id)
            if ticket is None:
                raise CallNotFoundException()
            await self._calls.finish(
                call.id, outcome=result.value, duration_s=duration_s, note=text, finished_at=now_naive_ist(),
            )
            await self._record(
                ctx, ticket, AuditAction.CALL_LOGGED, EventType.CALL_LOGGED,
                call_id=str(call.id), outcome=result.value, duration_s=duration_s,
            )
            finished = await self._calls.get(call.id)
        return finished or call

    async def open_call(self, actor: CurrentUser | None) -> CallLog | None:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            return await self._calls.open_call(ctx.user_id)

    async def calls_for_ticket(self, ticket_id: UUID, actor: CurrentUser | None) -> list[CallLog]:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ticket = await self._visible_ticket(ctx, ticket_id)
            return await self._calls.for_ticket(ticket.id)
