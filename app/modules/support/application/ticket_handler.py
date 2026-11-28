"""
Ticket Handlers (Phase 26)

Use cases for REQ-66 to REQ-71. Every use case opens one transaction, works out who is
acting, checks permission and team scope on the server, writes, and records a timeline
event (and, for staff actions, an audit row) in the same transaction.

Two kinds of callers:
- requesters (MCC, VLCC, Farmer, VLCC_FARMER) through the mobile API: only their own
  tickets, never internal notes or internal events;
- staff (Super Admin or an active support member): scoped to their team and permissions.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.support.application.attachment_service import AttachmentService, is_audio
from app.modules.support.application.event_bus import EventBus
from app.modules.support.application.push_messages import SupportPush
from app.modules.support.application import events as ev
from app.modules.support.application.guard import SupportContext, SupportGuard
from app.modules.support.application.routing import route_team
from app.modules.support.application.ticket_command import (
    AddAttachmentCommand,
    AssignTicketCommand,
    ChangeCategoryCommand,
    ChangePriorityCommand,
    ChangeStatusCommand,
    CreateCategoryCommand,
    CreateTicketCommand,
    ListMessagesQuery,
    ListRequesterTicketsQuery,
    ListStaffTicketsQuery,
    PostMessageCommand,
    RouteTicketCommand,
    UpdateCategoryCommand,
)
from app.modules.support.application.ticket_dto import TicketView
from app.modules.support.application.validation import clean_name, clean_text, clip
from app.modules.support.domain import ticket_rules
from app.modules.support.domain.entities import (
    AuditEntry,
    Category,
    SupportMember,
    Ticket,
    TicketAttachment,
    TicketEvent,
    TicketMessage,
)
from app.modules.support.domain.enums import (
    AuditAction,
    EventType,
    MessageKind,
    Scope,
    TicketStatus,
)
from app.modules.support.domain.exceptions import (
    CategoryNameAlreadyExistsException,
    CategoryNotFoundException,
    DuplicateClientRequestException,
    InvalidAssigneeException,
    InvalidTicketTransitionException,
    MessageNotDeletableException,
    MessageNotFoundException,
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    SupportValidationException,
    TeamNotFoundException,
    TicketClosedException,
    TicketNotFoundException,
    TicketNotRoutedException,
)
from app.modules.support.domain.irepository import ISupportRepository, ITicketRepository
from app.modules.support.domain.permissions import SupportPermission

REQUESTER_ROLES = frozenset({Role.MCC, Role.VLCC, Role.FARMER, Role.VLCC_FARMER})
MAX_PAGE = 100
MAX_MESSAGES = 200


_SAME = object()


def _page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))


def _request_id(value: str | None) -> str | None:
    text = (value or "").strip()
    if not text:
        return None
    if len(text) > 64:
        raise SupportValidationException("Request id must be at most 64 characters.")
    return text


def _file_kind(stored: TicketAttachment) -> MessageKind:
    """An audio file is a voice message; anything else a plain attachment."""
    return MessageKind.AUDIO if is_audio(stored.mime_type) else MessageKind.ATTACHMENT


def _event(
    ticket_id: UUID,
    actor_id: UUID | None,
    event_type: EventType,
    *,
    from_value: str | None = None,
    to_value: str | None = None,
    is_public: bool = True,
    **meta: Any,
) -> TicketEvent:
    return TicketEvent(
        ticket_id=ticket_id,
        actor_user_id=actor_id,
        event_type=event_type,
        from_value=from_value,
        to_value=to_value,
        meta=meta,
        is_public=is_public,
    )


class TicketHandler:

    __slots__ = ("_database", "_repository", "_support", "_guard", "_attachments", "_events", "_outbox")

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: ITicketRepository,
        support: ISupportRepository,
        attachments: AttachmentService,
        events: EventBus | None = None,
        outbox: SupportPush | None = None,
    ) -> None:
        self._database = database
        self._repository = repository
        self._support = support
        self._guard = SupportGuard(support)
        self._attachments = attachments
        self._events = events or EventBus()
        self._outbox = outbox

    # =========================================================
    # SHARED HELPERS
    # =========================================================

    async def context(self, actor: CurrentUser | None) -> SupportContext:
        """The staff context of the acting user; callers run it outside any other transaction."""
        async with self._database.transaction():
            return await self._guard.resolve(actor)

    @staticmethod
    def _require_requester(actor: CurrentUser | None) -> UUID:
        """Only MCC, VLCC, Farmer and VLCC_FARMER logins may use the requester side (D-9)."""
        if actor is None or actor.role_type not in REQUESTER_ROLES:
            raise SupportAccessDeniedException()
        return actor.id

    async def _audit(
        self,
        ctx: SupportContext,
        action: AuditAction,
        entity: str,
        entity_id: UUID | str | None,
        team_id: UUID | None,
        **meta: Any,
    ) -> None:
        await self._support.add_audit(
            AuditEntry(
                actor_id=ctx.user_id,
                action=str(action),
                entity=entity,
                entity_id=str(entity_id) if entity_id else None,
                team_id=team_id,
                meta=meta,
            )
        )

    @staticmethod
    def _staff_can_see(ctx: SupportContext, ticket: Ticket) -> bool:
        """Super Admin sees all (including the unassigned pool); staff see their team's tickets.

        Same rule as `audience.can_receive` and the queue counts: whoever may assign works the
        team's unassigned queue, so may open those tickets too.
        """
        if ctx.is_super_admin:
            return True
        if ticket.team_id is None or ticket.team_id != ctx.team_id:
            return False
        if ctx.has(SupportPermission.TICKET_VIEW_ALL):
            return True
        if ctx.has(SupportPermission.TICKET_VIEW_ASSIGNED) and ticket.assigned_to == ctx.user_id:
            return True
        return ctx.has(SupportPermission.TICKET_ASSIGN) and ticket.assigned_to is None

    def _emit(
        self,
        kind: str,
        ticket: Ticket,
        *,
        public: bool = True,
        team_id: Any = _SAME,
        assigned_to: Any = _SAME,
        previous_assignee: UUID | None = None,
        **data: Any,
    ) -> None:
        """Queue a realtime event; it is published only if the transaction commits."""
        team = ticket.team_id if team_id is _SAME else team_id
        assignee = ticket.assigned_to if assigned_to is _SAME else assigned_to
        self._events.after_commit(
            self._database.session,
            ev.SupportEvent(
                type=kind,
                ticket_id=str(ticket.id),
                ticket_no=ticket.ticket_no,
                team_id=str(team) if team else None,
                requester_id=str(ticket.requester_user_id),
                assigned_to=str(assignee) if assignee else None,
                previous_assignee=str(previous_assignee) if previous_assignee else None,
                public=public,
                data=data,
            ),
        )

    async def _staff_ticket(self, ctx: SupportContext, ticket_id: UUID) -> Ticket:
        ticket = await self._repository.get_ticket(ticket_id)
        # A ticket the member may not see looks like one that does not exist
        if ticket is None or not self._staff_can_see(ctx, ticket):
            raise TicketNotFoundException()
        return ticket

    async def _requester_ticket(self, requester_id: UUID, ticket_id: UUID) -> Ticket:
        ticket = await self._repository.get_ticket(ticket_id)
        if ticket is None or ticket.requester_user_id != requester_id:
            raise TicketNotFoundException()
        return ticket

    @staticmethod
    def _require_any(ctx: SupportContext, permissions: tuple[SupportPermission, ...]) -> None:
        if not any(ctx.has(permission) for permission in permissions):
            raise SupportPermissionDeniedException()

    async def _apply_status(
        self,
        ticket: Ticket,
        target: TicketStatus,
        actor_id: UUID,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        """Write a status change and its timeline event. The move itself was checked by the caller."""
        now = now_naive_ist()
        values: dict[str, Any] = {"status": target, "updated_by": actor_id, **(extra or {})}
        if target is TicketStatus.RESOLVED:
            values["resolved_at"] = now
        elif target is TicketStatus.CLOSED:
            values["closed_at"] = now
        elif target is TicketStatus.REOPENED:
            values["resolved_at"] = None
            values["closed_at"] = None
        await self._repository.update_ticket(ticket.id, values)
        await self._repository.add_event(
            _event(
                ticket.id, actor_id, EventType.STATUS_CHANGED,
                from_value=ticket.status.value, to_value=target.value,
            )
        )
        self._emit(ev.TICKET_UPDATED, ticket, change="status", status=target.value)
        # The requester gets a push when staff moved the ticket, not for their own close / reopen / reply
        if self._outbox is not None and actor_id != ticket.requester_user_id:
            await self._outbox.status_changed(ticket, target)

    # =========================================================
    # CATEGORIES
    # =========================================================

    async def list_categories(
        self, actor: CurrentUser | None, *, active_only: bool = True, requester_only: bool = False,
    ) -> list[Category]:
        """Requesters and Super Admin see categories; other staff see them for filters too.

        The mobile API passes `requester_only` so only app users reach it.
        """
        async with self._database.transaction():
            if requester_only:
                self._require_requester(actor)
            elif actor is not None and actor.role_type == Role.SUPPORT:
                await self._guard.resolve(actor)
            elif actor is None or (actor.role_type not in REQUESTER_ROLES and actor.role_type != Role.SUPER_ADMIN):
                raise SupportAccessDeniedException()
            return await self._repository.list_categories(active_only=active_only)

    async def get_category(self, category_id: UUID, actor: CurrentUser | None) -> Category:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not ctx.is_super_admin:
                raise SupportPermissionDeniedException()
            category = await self._repository.get_category(category_id)
        if category is None:
            raise CategoryNotFoundException()
        return category

    async def create_category(self, command: CreateCategoryCommand, actor: CurrentUser | None) -> Category:
        name = clean_name(command.name, label="Category name", minimum=2, maximum=80)
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not ctx.is_super_admin:
                raise SupportPermissionDeniedException()
            if await self._repository.category_name_exists(name):
                raise CategoryNameAlreadyExistsException()
            if command.default_team_id is not None and await self._support.get_team(command.default_team_id) is None:
                raise TeamNotFoundException()
            category = Category(
                id=uuid4(), name=name,
                default_team_id=command.default_team_id,
                default_priority=command.default_priority,
            )
            await self._repository.add_category(category, ctx.user_id)
            await self._audit(
                ctx, AuditAction.CATEGORY_CREATED, "category", category.id, command.default_team_id, name=name,
            )
            created = await self._repository.get_category(category.id)
        return created or category

    async def update_category(self, command: UpdateCategoryCommand, actor: CurrentUser | None) -> Category:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not ctx.is_super_admin:
                raise SupportPermissionDeniedException()
            category = await self._repository.get_category(command.category_id)
            if category is None:
                raise CategoryNotFoundException()
            name = None
            if command.name is not None:
                name = clean_name(command.name, label="Category name", minimum=2, maximum=80)
                if await self._repository.category_name_exists(name, exclude_category_id=category.id):
                    raise CategoryNameAlreadyExistsException()
            if command.set_team and command.default_team_id is not None:
                if await self._support.get_team(command.default_team_id) is None:
                    raise TeamNotFoundException()
            await self._repository.update_category(
                category.id,
                name=name,
                default_team_id=command.default_team_id,
                set_team=command.set_team,
                default_priority=command.default_priority,
                is_active=command.is_active,
                actor_id=ctx.user_id,
            )
            await self._audit(
                ctx, AuditAction.CATEGORY_UPDATED, "category", category.id, command.default_team_id,
                name=name, is_active=command.is_active,
            )
            updated = await self._repository.get_category(category.id)
        return updated or category

    # =========================================================
    # REQUESTER SIDE (mobile API)
    # =========================================================

    async def create(self, command: CreateTicketCommand, actor: CurrentUser | None) -> tuple[Ticket, bool]:
        """Raise a ticket. Returns (ticket, created); a repeated `client_request_id` returns the first one."""
        subject = clean_text(command.subject, label="Subject", minimum=3, maximum=200)
        description = clean_text(command.description, label="Description", minimum=5, maximum=4000)
        request_id = _request_id(command.client_request_id)
        requester_id = self._require_requester(actor)
        try:
            return await self._create(command, requester_id, subject, description, request_id)
        except DuplicateClientRequestException:
            # A retry raced the original and lost: answer with the ticket the original saved
            async with self._database.transaction():
                existing = await self._repository.find_by_client_request(requester_id, request_id or "")
            if existing is None:
                raise
            return existing, False

    async def _create(
        self, command: CreateTicketCommand, requester_id: UUID, subject: str, description: str, request_id: str | None,
    ) -> tuple[Ticket, bool]:
        async with self._database.transaction():
            if request_id:
                existing = await self._repository.find_by_client_request(requester_id, request_id)
                if existing is not None:
                    return existing, False

            category = await self._repository.get_category(command.category_id)
            if category is None or not category.is_active:
                raise CategoryNotFoundException()
            team = await self._support.get_team(category.default_team_id) if category.default_team_id else None
            team_id = route_team(category, team)

            now = now_naive_ist()
            ticket = Ticket(
                id=uuid4(),
                ticket_no=await self._repository.next_ticket_number(now.year),
                requester_user_id=requester_id,
                category_id=category.id,
                subject=subject,
                description=description,
                priority=category.default_priority,
                team_id=team_id,
                device_model=clip(command.device_model, 100),
                os_version=clip(command.os_version, 50),
                app_version=clip(command.app_version, 30),
                client_request_id=request_id,
                last_message_at=now,
                staff_unread=1,
            )
            await self._repository.add_ticket(ticket)
            await self._repository.add_message(
                TicketMessage(
                    ticket_id=ticket.id, sender_user_id=requester_id, sender_is_staff=False, body=description,
                )
            )
            await self._repository.add_event(
                _event(ticket.id, requester_id, EventType.CREATED, to_value=TicketStatus.NEW.value)
            )
            if team_id is not None:
                await self._repository.add_event(
                    _event(
                        ticket.id, None, EventType.ROUTED, to_value=str(team_id), is_public=False, team=team.name,
                    )
                )
            await self._support.add_audit(
                AuditEntry(
                    actor_id=requester_id, action=str(AuditAction.TICKET_CREATED), entity="ticket",
                    entity_id=str(ticket.id), team_id=team_id, meta={"ticket_no": ticket.ticket_no},
                )
            )
            self._emit(ev.TICKET_CREATED, ticket)
            created = await self._repository.get_ticket(ticket.id)
        return created or ticket, True

    async def list_for_requester(
        self, query: ListRequesterTicketsQuery, actor: CurrentUser | None,
    ) -> tuple[list[Ticket], int]:
        limit, offset = _page(query.limit, query.offset)
        async with self._database.transaction():
            requester_id = self._require_requester(actor)
            return await self._repository.list_for_requester(
                requester_id, status=query.status, limit=limit, offset=offset,
            )

    async def get_for_requester(self, ticket_id: UUID, actor: CurrentUser | None) -> TicketView:
        """The requester's own ticket with public messages and public timeline only."""
        async with self._database.transaction():
            requester_id = self._require_requester(actor)
            ticket = await self._requester_ticket(requester_id, ticket_id)
            messages = await self._repository.list_messages(
                ticket.id, include_internal=False, after_id=None, limit=MAX_MESSAGES,
            )
            events = await self._repository.list_events(ticket.id, public_only=True)
        return TicketView(ticket=ticket, messages=messages, events=events)

    async def list_messages_for_requester(
        self, query: ListMessagesQuery, actor: CurrentUser | None,
    ) -> list[TicketMessage]:
        limit = max(1, min(int(query.limit), MAX_MESSAGES))
        async with self._database.transaction():
            requester_id = self._require_requester(actor)
            ticket = await self._requester_ticket(requester_id, query.ticket_id)
            return await self._repository.list_messages(
                ticket.id, include_internal=False, after_id=query.after_id, limit=limit,
            )

    async def post_requester_message(self, command: PostMessageCommand, actor: CurrentUser | None) -> TicketMessage:
        body = clean_text(command.body, label="Message", maximum=4000)
        request_id = _request_id(command.client_request_id)
        requester_id = self._require_requester(actor)
        try:
            async with self._database.transaction():
                ticket = await self._requester_ticket(requester_id, command.ticket_id)
                if request_id:
                    existing = await self._repository.find_message_by_client_request(ticket.id, requester_id, request_id)
                    if existing is not None:
                        return existing
                return await self._write_requester_message(ticket, requester_id, body, request_id=request_id)
        except DuplicateClientRequestException:
            # A retry raced the original and lost: answer with the message the original saved
            async with self._database.transaction():
                existing = await self._repository.find_message_by_client_request(
                    command.ticket_id, requester_id, request_id or "",
                )
            if existing is None:
                raise
            return existing

    async def _write_requester_message(
        self,
        ticket: Ticket,
        requester_id: UUID,
        body: str,
        *,
        request_id: str | None = None,
        kind: MessageKind = MessageKind.TEXT,
        event_type: EventType = EventType.REQUESTER_REPLIED,
    ) -> TicketMessage:
        """Store a requester message and its side effects (timeline, unread mark, status resume)."""
        if ticket.status is TicketStatus.CLOSED:
            raise TicketClosedException()
        message = await self._repository.add_message(
            TicketMessage(
                ticket_id=ticket.id, sender_user_id=requester_id, sender_is_staff=False,
                body=body, kind=kind, client_request_id=request_id,
            )
        )
        await self._repository.add_event(_event(ticket.id, requester_id, event_type))
        await self._repository.update_ticket(
            ticket.id, {"last_message_at": message.created_at, "updated_by": requester_id},
        )
        await self._repository.bump_unread(ticket.id, for_staff=True)
        self._emit(ev.MESSAGE_CREATED, ticket, message_id=message.id)
        target = ticket_rules.requester_reply_target(ticket.status)
        if target is not None:
            await self._apply_status(ticket, target, requester_id)
        return message

    async def requester_close(self, ticket_id: UUID, actor: CurrentUser | None) -> Ticket:
        return await self._requester_move(ticket_id, TicketStatus.CLOSED, actor)

    async def requester_reopen(self, ticket_id: UUID, actor: CurrentUser | None) -> Ticket:
        return await self._requester_move(ticket_id, TicketStatus.REOPENED, actor)

    async def _requester_move(self, ticket_id: UUID, target: TicketStatus, actor: CurrentUser | None) -> Ticket:
        async with self._database.transaction():
            requester_id = self._require_requester(actor)
            ticket = await self._requester_ticket(requester_id, ticket_id)
            ticket_rules.ensure_requester_transition(ticket.status, target)
            await self._apply_status(ticket, target, requester_id)
            if target is TicketStatus.REOPENED:
                await self._repository.bump_unread(ticket.id, for_staff=True)
            updated = await self._repository.get_ticket(ticket.id)
        return updated or ticket

    async def mark_read_for_requester(self, ticket_id: UUID, actor: CurrentUser | None) -> None:
        async with self._database.transaction():
            requester_id = self._require_requester(actor)
            ticket = await self._requester_ticket(requester_id, ticket_id)
            await self._repository.clear_unread(ticket.id, for_staff=False)

    # =========================================================
    # STAFF SIDE
    # =========================================================

    async def list_for_staff(
        self, query: ListStaffTicketsQuery, actor: CurrentUser | None,
    ) -> tuple[list[Ticket], int]:
        limit, offset = _page(query.limit, query.offset)
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            limit_to_assigned = False
            if not ctx.is_super_admin:
                view_all = ctx.has(SupportPermission.TICKET_VIEW_ALL)
                view_assigned = ctx.has(SupportPermission.TICKET_VIEW_ASSIGNED)
                if query.scope is Scope.UNASSIGNED:
                    if not (view_all or ctx.has(SupportPermission.TICKET_ASSIGN)):
                        raise SupportPermissionDeniedException()
                elif not (view_all or view_assigned):
                    raise SupportPermissionDeniedException()
                limit_to_assigned = query.scope is Scope.ALL and not view_all
            return await self._repository.list_for_staff(
                scope=query.scope,
                team_id=None if ctx.is_super_admin else ctx.team_id,
                user_id=ctx.user_id,
                limit_to_assigned=limit_to_assigned,
                status=query.status,
                priority=query.priority,
                category_id=query.category_id,
                assignee_id=query.assignee_id,
                search=query.search,
                date_from=query.date_from,
                date_to=query.date_to,
                limit=limit,
                offset=offset,
            )

    async def get_for_staff(self, ticket_id: UUID, actor: CurrentUser | None) -> TicketView:
        """Opening a ticket shows everything, internal notes included, and clears its unread mark."""
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ticket = await self._staff_ticket(ctx, ticket_id)
            messages = await self._repository.list_messages(
                ticket.id, include_internal=True, after_id=None, limit=MAX_MESSAGES,
            )
            events = await self._repository.list_events(ticket.id, public_only=False)
            if ticket.staff_unread:
                await self._repository.clear_unread(ticket.id, for_staff=True)
            if ticket.requester_mobile:
                await self._audit_phone_view(ctx, ticket)
        return TicketView(ticket=ticket, messages=messages, events=events)

    async def _audit_phone_view(self, ctx: SupportContext, ticket: Ticket) -> None:
        """The detail page shows the number to every member (D-6); who saw it is kept, once a day per ticket."""
        today = now_naive_ist().replace(hour=0, minute=0, second=0, microsecond=0)
        action = str(AuditAction.PHONE_VIEWED)
        if not await self._support.audit_exists_since(
            actor_id=ctx.user_id, action=action, entity_id=str(ticket.id), since=today,
        ):
            await self._audit(ctx, AuditAction.PHONE_VIEWED, "ticket", ticket.id, ticket.team_id, ticket_no=ticket.ticket_no)

    async def list_messages_for_staff(
        self, query: ListMessagesQuery, actor: CurrentUser | None,
    ) -> list[TicketMessage]:
        limit = max(1, min(int(query.limit), MAX_MESSAGES))
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ticket = await self._staff_ticket(ctx, query.ticket_id)
            return await self._repository.list_messages(
                ticket.id, include_internal=True, after_id=query.after_id, limit=limit,
            )

    async def post_staff_message(self, command: PostMessageCommand, actor: CurrentUser | None) -> TicketMessage:
        """A reply to the requester, or an internal note that the requester never sees."""
        body = clean_text(command.body, label="Message", maximum=4000)
        request_id = _request_id(command.client_request_id)
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(
                SupportPermission.TICKET_INTERNAL_NOTE if command.internal else SupportPermission.TICKET_REPLY
            )
            ticket = await self._staff_ticket(ctx, command.ticket_id)
            if request_id:
                existing = await self._repository.find_message_by_client_request(ticket.id, ctx.user_id, request_id)
                if existing is not None:
                    return existing
            return await self._write_staff_message(
                ctx, ticket, body, internal=command.internal, request_id=request_id,
            )

    async def _write_staff_message(
        self,
        ctx: SupportContext,
        ticket: Ticket,
        body: str,
        *,
        internal: bool,
        request_id: str | None = None,
        kind: MessageKind = MessageKind.TEXT,
    ) -> TicketMessage:
        """Store a staff message and its side effects (timeline, audit, requester unread mark)."""
        if ticket.status is TicketStatus.CLOSED and not internal:
            raise TicketClosedException()
        message = await self._repository.add_message(
            TicketMessage(
                ticket_id=ticket.id, sender_user_id=ctx.user_id, sender_is_staff=True,
                body=body, kind=kind, is_internal=internal, client_request_id=request_id,
            )
        )
        if internal:
            await self._repository.add_event(_event(ticket.id, ctx.user_id, EventType.NOTE_ADDED, is_public=False))
            await self._audit(ctx, AuditAction.TICKET_NOTE_ADDED, "ticket", ticket.id, ticket.team_id)
            self._emit(ev.NOTE_CREATED, ticket, public=False, message_id=message.id)
        else:
            await self._repository.add_event(_event(ticket.id, ctx.user_id, EventType.REPLIED))
            values: dict[str, Any] = {"last_message_at": message.created_at, "updated_by": ctx.user_id}
            if ticket.first_response_at is None:
                values["first_response_at"] = message.created_at
            await self._repository.update_ticket(ticket.id, values)
            await self._repository.bump_unread(ticket.id, for_staff=False)
            self._emit(ev.MESSAGE_CREATED, ticket, message_id=message.id)
            if self._outbox is not None:
                await self._outbox.staff_replied(
                    ticket, body, is_file=kind is MessageKind.ATTACHMENT, is_audio=kind is MessageKind.AUDIO,
                )
        return message

    # =========================================================
    # ATTACHMENTS (REQ-70)
    # =========================================================

    async def attach_for_requester(
        self, command: AddAttachmentCommand, actor: CurrentUser | None,
    ) -> tuple[TicketMessage, TicketAttachment]:
        async with self._database.transaction() as session:
            requester_id = self._require_requester(actor)
            ticket = await self._requester_ticket(requester_id, command.ticket_id)
            if ticket.status is TicketStatus.CLOSED:
                raise TicketClosedException()
            stored = await self._attachments.store(session, ticket.id, command)
            message = await self._write_requester_message(
                ticket, requester_id, stored.file_name,
                kind=_file_kind(stored), event_type=EventType.ATTACHMENT_ADDED,
            )
            return message, await self._save_attachment(stored, message, requester_id)

    async def attach_for_staff(
        self, command: AddAttachmentCommand, actor: CurrentUser | None,
    ) -> tuple[TicketMessage, TicketAttachment]:
        async with self._database.transaction() as session:
            ctx = await self._guard.resolve(actor)
            ctx.require(
                SupportPermission.TICKET_INTERNAL_NOTE if command.internal else SupportPermission.TICKET_REPLY
            )
            ticket = await self._staff_ticket(ctx, command.ticket_id)
            if ticket.status is TicketStatus.CLOSED and not command.internal:
                raise TicketClosedException()
            stored = await self._attachments.store(session, ticket.id, command)
            message = await self._write_staff_message(
                ctx, ticket, stored.file_name, internal=command.internal, kind=_file_kind(stored),
            )
            return message, await self._save_attachment(stored, message, ctx.user_id)

    # =========================================================
    # DELETING A MESSAGE
    # =========================================================
    #
    # Only the sender deletes, and only what they could still send: the requester while the ticket is
    # open, staff a reply while it is open (with the reply permission) or a note at any time (with the
    # note permission). The ticket's first message is its description and stays. The row remains as a
    # "deleted" placeholder; its text is blanked and its files are removed once the deletion commits.
    # Deleting a message that is already deleted changes nothing and answers with it.

    async def delete_requester_message(
        self, ticket_id: UUID, message_id: int, actor: CurrentUser | None,
    ) -> TicketMessage:
        async with self._database.transaction() as session:
            requester_id = self._require_requester(actor)
            ticket = await self._requester_ticket(requester_id, ticket_id)
            message = await self._ticket_message(ticket, message_id, include_internal=False)
            if message.is_deleted:
                return message
            if message.sender_user_id != requester_id or message.sender_is_staff:
                raise MessageNotDeletableException("You can only delete your own messages.")
            if ticket.status is TicketStatus.CLOSED:
                raise TicketClosedException()
            return await self._delete_message(session, ticket, message, requester_id)

    async def delete_staff_message(
        self, ticket_id: UUID, message_id: int, actor: CurrentUser | None,
    ) -> TicketMessage:
        async with self._database.transaction() as session:
            ctx = await self._guard.resolve(actor)
            ticket = await self._staff_ticket(ctx, ticket_id)
            message = await self._ticket_message(ticket, message_id, include_internal=True)
            if message.is_deleted:
                return message
            if message.sender_user_id != ctx.user_id or not message.sender_is_staff:
                raise MessageNotDeletableException("You can only delete your own messages.")
            ctx.require(
                SupportPermission.TICKET_INTERNAL_NOTE if message.is_internal else SupportPermission.TICKET_REPLY
            )
            if ticket.status is TicketStatus.CLOSED and not message.is_internal:
                raise TicketClosedException()
            deleted = await self._delete_message(session, ticket, message, ctx.user_id)
            await self._audit(
                ctx, AuditAction.MESSAGE_DELETED, "ticket", ticket.id, ticket.team_id,
                ticket_no=ticket.ticket_no, message_id=message.id, internal=message.is_internal,
            )
            return deleted

    async def _ticket_message(self, ticket: Ticket, message_id: int, *, include_internal: bool) -> TicketMessage:
        message = await self._repository.get_message(message_id)
        # Another ticket's message, or a note asked for by the requester, looks like one that does not exist
        if message is None or message.ticket_id != ticket.id or (message.is_internal and not include_internal):
            raise MessageNotFoundException()
        return message

    async def _ensure_not_first(self, ticket: Ticket, message: TicketMessage) -> None:
        first = await self._repository.list_messages(ticket.id, include_internal=True, after_id=None, limit=1)
        if first and first[0].id == message.id:
            raise MessageNotDeletableException("The first message is the ticket's description and cannot be deleted.")

    async def _delete_message(self, session, ticket: Ticket, message: TicketMessage, actor_id: UUID) -> TicketMessage:
        await self._ensure_not_first(ticket, message)
        keys = await self._repository.delete_message(message.id, deleted_by=actor_id, deleted_at=now_naive_ist())
        self._attachments.remove_after_commit(session, keys)
        await self._repository.add_event(
            _event(
                ticket.id, actor_id, EventType.MESSAGE_DELETED, is_public=not message.is_internal,
                message_id=message.id,
            )
        )
        self._emit(ev.MESSAGE_DELETED, ticket, public=not message.is_internal, message_id=message.id)
        return await self._repository.get_message(message.id) or message

    async def _save_attachment(
        self, stored: TicketAttachment, message: TicketMessage, uploaded_by: UUID,
    ) -> TicketAttachment:
        stored.message_id = message.id
        stored.uploaded_by = uploaded_by
        await self._repository.add_attachment(stored)
        message.attachments.append(stored)
        return stored

    async def open_attachment(self, attachment_id: UUID, actor: CurrentUser | None) -> tuple[TicketAttachment, Path]:
        """The stored file for the ticket's requester or the staff who may see the ticket (REQ-71)."""
        async with self._database.transaction():
            attachment = await self._repository.get_attachment(attachment_id)
            if attachment is None:
                raise TicketNotFoundException()
            if actor is not None and actor.role_type in REQUESTER_ROLES:
                await self._requester_ticket(actor.id, attachment.ticket_id)
                message = await self._repository.get_message(attachment.message_id) if attachment.message_id else None
                if message is not None and message.is_internal:
                    raise TicketNotFoundException()
            else:
                ctx = await self._guard.resolve(actor)
                await self._staff_ticket(ctx, attachment.ticket_id)
        return attachment, self._attachments.path_of(attachment)

    async def socket_ticket(self, actor: CurrentUser | None, ticket_id: UUID) -> Ticket | None:
        """The ticket if this user may follow it on a socket (own ticket, or one their team scope allows)."""
        async with self._database.transaction():
            ticket = await self._repository.get_ticket(ticket_id)
            if ticket is None:
                return None
            if actor is not None and actor.role_type in REQUESTER_ROLES:
                return ticket if ticket.requester_user_id == actor.id else None
            try:
                ctx = await self._guard.resolve(actor)
            except SupportAccessDeniedException:
                return None
            return ticket if self._staff_can_see(ctx, ticket) else None

    async def mark_read_for_staff(self, ticket_id: UUID, actor: CurrentUser | None) -> None:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ticket = await self._staff_ticket(ctx, ticket_id)
            if ticket.staff_unread:
                await self._repository.clear_unread(ticket.id, for_staff=True)

    async def queue_counts(self, ctx: SupportContext) -> dict[str, int]:
        """Open-ticket badges for the sidebar, zero for the queues the member may not use."""
        view_all = ctx.has(SupportPermission.TICKET_VIEW_ALL)
        async with self._database.transaction():
            counts = await self._repository.queue_counts(
                team_id=None if ctx.is_super_admin else ctx.team_id, user_id=ctx.user_id,
            )
        allowed = {
            "all": view_all,
            "unassigned": view_all or ctx.has(SupportPermission.TICKET_ASSIGN),
            "mine": view_all or ctx.has(SupportPermission.TICKET_VIEW_ASSIGNED),
        }
        return {name: (value if allowed[name] else 0) for name, value in counts.items()}

    async def team_members(self, ctx: SupportContext) -> list[SupportMember]:
        """Active members of the member's own team, for the assignee filter (view_all or assign only)."""
        if ctx.is_super_admin or ctx.team_id is None:
            return []
        if not (ctx.has(SupportPermission.TICKET_VIEW_ALL) or ctx.has(SupportPermission.TICKET_ASSIGN)):
            return []
        async with self._database.transaction():
            members, _total = await self._support.list_members(ctx.team_id, search=None, limit=200, offset=0)
        return [member for member in members if member.is_active]

    async def list_assignees(self, ticket_id: UUID, actor: CurrentUser | None) -> list[SupportMember]:
        """Active members of the ticket's team the member may hand it to."""
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.TICKET_ASSIGN)
            ticket = await self._staff_ticket(ctx, ticket_id)
            if ticket.team_id is None:
                return []
            members, _total = await self._support.list_members(ticket.team_id, search=None, limit=200, offset=0)
        return [member for member in members if member.is_active]

    async def assign(self, command: AssignTicketCommand, actor: CurrentUser | None) -> Ticket:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.TICKET_ASSIGN)
            ticket = await self._staff_ticket(ctx, command.ticket_id)
            if ticket.team_id is None:
                raise TicketNotRoutedException()
            if ticket.status is TicketStatus.CLOSED:
                raise TicketClosedException()
            if not await self._repository.member_is_assignable(command.assignee_user_id, ticket.team_id):
                raise InvalidAssigneeException()
            assignee = await self._support.get_member_by_user(command.assignee_user_id)

            await self._repository.update_ticket(
                ticket.id, {"assigned_to": command.assignee_user_id, "updated_by": ctx.user_id},
            )
            await self._repository.add_event(
                _event(
                    ticket.id, ctx.user_id, EventType.ASSIGNED, is_public=False,
                    from_value=str(ticket.assigned_to) if ticket.assigned_to else None,
                    to_value=str(command.assignee_user_id),
                    assignee=assignee.name if assignee else None,
                )
            )
            self._emit(
                ev.TICKET_UPDATED, ticket, public=False, change="assigned",
                assigned_to=command.assignee_user_id, previous_assignee=ticket.assigned_to,
            )
            if ticket.status in (TicketStatus.NEW, TicketStatus.REOPENED):
                # The status event must name the new assignee, or that member's screen never hears it
                await self._apply_status(
                    replace(ticket, assigned_to=command.assignee_user_id), TicketStatus.ASSIGNED, ctx.user_id,
                )
            await self._audit(
                ctx, AuditAction.TICKET_ASSIGNED, "ticket", ticket.id, ticket.team_id,
                assignee=str(command.assignee_user_id),
            )
            updated = await self._repository.get_ticket(ticket.id)
        return updated or ticket

    async def route_to_team(self, command: RouteTicketCommand, actor: CurrentUser | None) -> Ticket:
        """Super Admin sends a ticket nobody is working on to a team (REQ-68)."""
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not ctx.is_super_admin:
                raise SupportPermissionDeniedException()
            ticket = await self._staff_ticket(ctx, command.ticket_id)
            team = await self._support.get_team(command.team_id)
            if team is None or not team.is_active:
                raise TeamNotFoundException()
            if ticket.assigned_to is not None:
                raise SupportValidationException("Only a ticket nobody is working on can be sent to another team.")
            if ticket.status is TicketStatus.CLOSED:
                raise TicketClosedException()

            await self._repository.update_ticket(ticket.id, {"team_id": team.id, "updated_by": ctx.user_id})
            await self._repository.add_event(
                _event(
                    ticket.id, ctx.user_id, EventType.ROUTED, is_public=False,
                    from_value=str(ticket.team_id) if ticket.team_id else None,
                    to_value=str(team.id), team=team.name,
                )
            )
            await self._audit(ctx, AuditAction.TICKET_ROUTED, "ticket", ticket.id, team.id, team=team.name)
            self._emit(ev.TICKET_UPDATED, ticket, public=False, change="routed", team_id=team.id)
            updated = await self._repository.get_ticket(ticket.id)
        return updated or ticket

    async def change_status(self, command: ChangeStatusCommand, actor: CurrentUser | None) -> Ticket:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ticket = await self._staff_ticket(ctx, command.ticket_id)
            target = command.status
            ticket_rules.ensure_staff_transition(ticket.status, target)
            self._require_any(ctx, ticket_rules.permissions_for(target))
            if target is TicketStatus.ASSIGNED and ticket.assigned_to is None:
                raise InvalidTicketTransitionException("Assign the ticket to a member first.")
            if ticket.status is TicketStatus.NEW and target is TicketStatus.ASSIGNED:
                raise InvalidTicketTransitionException("Use Assign to give the ticket to a member.")

            await self._apply_status(ticket, target, ctx.user_id)
            await self._audit(
                ctx, AuditAction.TICKET_STATUS_CHANGED, "ticket", ticket.id, ticket.team_id,
                previous=ticket.status.value, status=target.value,
            )
            updated = await self._repository.get_ticket(ticket.id)
        return updated or ticket

    async def change_priority(self, command: ChangePriorityCommand, actor: CurrentUser | None) -> Ticket:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.TICKET_CHANGE_PRIORITY)
            ticket = await self._staff_ticket(ctx, command.ticket_id)
            if command.priority is not ticket.priority:
                await self._repository.update_ticket(
                    ticket.id, {"priority": command.priority, "updated_by": ctx.user_id},
                )
                await self._repository.add_event(
                    _event(
                        ticket.id, ctx.user_id, EventType.PRIORITY_CHANGED, is_public=False,
                        from_value=ticket.priority.value, to_value=command.priority.value,
                    )
                )
                await self._audit(
                    ctx, AuditAction.TICKET_PRIORITY_CHANGED, "ticket", ticket.id, ticket.team_id,
                    previous=ticket.priority.value, priority=command.priority.value,
                )
                self._emit(ev.TICKET_UPDATED, ticket, public=False, change="priority")
            updated = await self._repository.get_ticket(ticket.id)
        return updated or ticket

    async def change_category(self, command: ChangeCategoryCommand, actor: CurrentUser | None) -> Ticket:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.TICKET_CHANGE_PRIORITY)
            ticket = await self._staff_ticket(ctx, command.ticket_id)
            category = await self._repository.get_category(command.category_id)
            if category is None or not category.is_active:
                raise CategoryNotFoundException()
            if category.id != ticket.category_id:
                await self._repository.update_ticket(
                    ticket.id, {"category_id": category.id, "updated_by": ctx.user_id},
                )
                await self._repository.add_event(
                    _event(
                        ticket.id, ctx.user_id, EventType.CATEGORY_CHANGED, is_public=False,
                        from_value=ticket.category_name, to_value=category.name,
                    )
                )
                await self._audit(
                    ctx, AuditAction.TICKET_CATEGORY_CHANGED, "ticket", ticket.id, ticket.team_id,
                    category=category.name,
                )
                self._emit(ev.TICKET_UPDATED, ticket, public=False, change="category")
            updated = await self._repository.get_ticket(ticket.id)
        return updated or ticket
