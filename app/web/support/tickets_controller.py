"""
Support ticket screens (Plan 26.3, REQ-62, REQ-65, REQ-72)

/support/tickets?scope=unassigned|all|mine   one list, three queues, with filters
/support/tickets/{id}                        conversation, requester card, meta and timeline
/support/tickets/{id}/messages               reply or internal note (HTMX, no page reload)
/support/tickets/{id}/assign|status|priority|category|route   one action each, then back to the ticket
/support/attachments/{id}                    a file of a ticket the member may see

Every screen asks the handler, which checks permission and team scope on the server; the template
only hides controls the member cannot use.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, time
from urllib.parse import urlencode
from uuid import UUID

from fastapi import Request
from fastapi.responses import FileResponse, JSONResponse, Response

from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.dependencies import GetHandler
from app.modules.support.application.command import ListTeamsQuery
from app.modules.support.application.ticket_command import (
    AddAttachmentCommand,
    AssignTicketCommand,
    ChangeCategoryCommand,
    ChangePriorityCommand,
    ChangeStatusCommand,
    ListStaffTicketsQuery,
    PostMessageCommand,
    RouteTicketCommand,
)
from app.modules.support.domain import ticket_rules
from app.modules.support.domain.entities import Ticket, TicketEvent, TicketMessage
from app.modules.support.domain.enums import CallOutcome, EventType, Scope, TicketPriority, TicketStatus
from app.modules.support.domain.exceptions import (
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    TicketNotFoundException,
)
from app.modules.support.domain.permissions import SupportPermission as P
from app.web.framework.renderer import Renderer
from app.web.support.forms import FORM_ERRORS, PAGE_SIZE, build_page, error_message, optional_uuid, page_number
from app.web.support.navigation import default_scope
from app.web.support.portal import SupportPortal

STATUS_TONES = {
    TicketStatus.NEW: "info",
    TicketStatus.ASSIGNED: "info",
    TicketStatus.IN_PROGRESS: "accent",
    TicketStatus.WAITING_ON_USER: "warning",
    TicketStatus.ESCALATED: "danger",
    TicketStatus.RESOLVED: "success",
    TicketStatus.CLOSED: "",
    TicketStatus.REOPENED: "warning",
}

SCOPE_TITLES = {
    Scope.UNASSIGNED: "Unassigned queue",
    Scope.ALL: "All tickets",
    Scope.MINE: "My tickets",
}

SCOPE_EMPTY = {
    Scope.UNASSIGNED: ("The queue is clear", "New tickets waiting for someone to pick them up appear here."),
    Scope.ALL: ("No tickets yet", "Tickets raised from the app for your team appear here."),
    Scope.MINE: ("Nothing assigned to you", "Tickets assigned to you appear here."),
}

# What the page says after an action (the URL carries a short code, never free text)
NOTICES = {
    "assigned": ("Ticket assigned.", "success"),
    "status": ("Status updated.", "success"),
    "priority": ("Priority updated.", "success"),
    "category": ("Category updated.", "success"),
    "routed": ("Ticket sent to the team.", "success"),
    "refused": ("That change is not allowed for this ticket right now.", "warning"),
    "denied": ("You do not have permission to do that.", "danger"),
    "invalid": ("Please check your choice and try again.", "danger"),
    "call_logged": ("Call outcome saved.", "success"),
}

NEEDS_ATTENTION = (TicketStatus.NEW, TicketStatus.REOPENED)

_THREAD_EVENTS = (EventType.ASSIGNED, EventType.STATUS_CHANGED, EventType.ROUTED)


ROLE_LABELS = {
    Role.MCC: "MCC",
    Role.VLCC: "VLCC",
    Role.FARMER: "Farmer",
    Role.VLCC_FARMER: "VLCC farmer",
}


def _role(value: int | None) -> str:
    """The requester's role as the app names it."""
    try:
        return ROLE_LABELS.get(Role(value), Role(value).name.replace("_", " ").title()) if value else ""
    except ValueError:
        return ""


def _when(value: datetime | None) -> str:
    return value.strftime("%d %b, %H:%M") if value else ""


def _age(value: datetime | None, now: datetime) -> str:
    if value is None:
        return ""
    seconds = max(0, int((now - value).total_seconds()))
    if seconds < 3600:
        return f"{max(1, seconds // 60)}m"
    if seconds < 86400:
        return f"{seconds // 3600}h"
    return f"{seconds // 86400}d"


def _status_label(value: str | None) -> str:
    try:
        return TicketStatus(value).label if value else ""
    except ValueError:
        return value or ""


def _describe(event: TicketEvent) -> str:
    kind = event.event_type
    meta = event.meta or {}
    if kind is EventType.CREATED:
        return "Ticket created"
    if kind is EventType.ROUTED:
        return f"Sent to {meta['team']}" if meta.get("team") else "Routed to the team"
    if kind is EventType.ASSIGNED:
        return f"Assigned to {meta['assignee']}" if meta.get("assignee") else "Assigned"
    if kind is EventType.STATUS_CHANGED:
        return f"Status: {_status_label(event.from_value)} → {_status_label(event.to_value)}"
    if kind is EventType.PRIORITY_CHANGED:
        return f"Priority: {(event.from_value or '').title()} → {(event.to_value or '').title()}"
    if kind is EventType.CATEGORY_CHANGED:
        return f"Category: {event.from_value or '—'} → {event.to_value or '—'}"
    if kind is EventType.NOTE_ADDED:
        return "Internal note added"
    if kind is EventType.REPLIED:
        return "Replied to the requester"
    if kind is EventType.REQUESTER_REPLIED:
        return "Requester replied"
    if kind is EventType.ATTACHMENT_ADDED:
        return "File attached"
    if kind is EventType.CALL_STARTED:
        return "Called the requester"
    if kind is EventType.CALL_LOGGED:
        try:
            return f"Call outcome: {CallOutcome(event.to_value).label}"
        except ValueError:
            return "Call outcome recorded"
    return kind.value.replace("_", " ").title()


@dataclass(slots=True, kw_only=True)
class ThreadItem:
    """One row of the conversation: a message, or a short system line for assignments and status moves."""

    kind: str                 # requester | staff | note | system
    when: str
    sender: str = ""
    body: str = ""
    attachments: list = None  # type: ignore[assignment]
    at: datetime | None = None


def _thread(messages: list[TicketMessage], events: list[TicketEvent]) -> list[ThreadItem]:
    items: list[ThreadItem] = []
    for message in messages:
        if message.is_internal:
            kind = "note"
        elif message.sender_is_staff:
            kind = "staff"
        else:
            kind = "requester"
        items.append(
            ThreadItem(
                kind=kind, when=_when(message.created_at), sender=message.sender_name or "",
                body=message.body, attachments=message.attachments, at=message.created_at,
            )
        )
    for event in events:
        if event.event_type in _THREAD_EVENTS:
            items.append(
                ThreadItem(kind="system", when=_when(event.created_at), body=_describe(event), at=event.created_at)
            )
    # Messages were added first, so a message and an event with the same second keep that order
    items.sort(key=lambda item: item.at or datetime.min)
    return items


class MissingChoice(Exception):
    """A form value the member did not choose; shown as a generic 'check your choice' notice."""

    status_code = 422


_ACTION_ERRORS = (*FORM_ERRORS, MissingChoice)


def _query_url(path: str, **params: str | None) -> str:
    query = {key: value for key, value in params.items() if value}
    return f"{path}?{urlencode(query)}" if query else path


def _day(value: str | None, *, end: bool) -> datetime | None:
    try:
        day = datetime.strptime((value or "").strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return datetime.combine(day.date(), time.max if end else time.min)


def _error_code(exc: Exception) -> str:
    if isinstance(exc, SupportPermissionDeniedException):
        return "denied"
    code = getattr(exc, "status_code", 0)
    return "refused" if code == 409 else "invalid"


class SupportTicketsController:

    # ------------------------------------------------------------ list

    @staticmethod
    async def list_page(
        request: Request,
        scope: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        category: str | None = None,
        assignee: str | None = None,
        q: str | None = None,
        date_from: str | None = None,
        date_to: str | None = None,
        page: str | None = None,
    ):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()

        try:
            chosen = Scope(scope) if scope else Scope(default_scope(ctx) or "")
        except ValueError:
            return Renderer.redirect("/support")

        # "All tickets" is the whole team's queue; a member who only sees assigned tickets uses "My tickets"
        if chosen is Scope.ALL and not (ctx.is_super_admin or ctx.has(P.TICKET_VIEW_ALL)):
            return Renderer.redirect("/support")

        user = request.state.user
        handler = GetHandler.ticket_handler(request)
        number = page_number(page)
        try:
            status_value = TicketStatus(status) if status else None
            priority_value = TicketPriority(priority) if priority else None
        except ValueError:
            status_value = priority_value = None

        query = ListStaffTicketsQuery(
            scope=chosen,
            status=[status_value] if status_value else None,
            priority=priority_value,
            category_id=optional_uuid(category),
            assignee_id=optional_uuid(assignee),
            search=q,
            date_from=_day(date_from, end=False),
            date_to=_day(date_to, end=True),
            limit=PAGE_SIZE,
            offset=(number - 1) * PAGE_SIZE,
        )
        try:
            tickets, total = await handler.list_for_staff(query, user)
        except SupportPermissionDeniedException:
            return Renderer.redirect("/support")

        now = now_naive_ist()
        rows = [
            {
                "ticket": ticket,
                "age": _age(ticket.last_message_at or ticket.created_at, now),
                "tone": STATUS_TONES[ticket.status],
                "role": _role(ticket.requester_role),
            }
            for ticket in tickets
        ]
        params = {
            "scope": chosen.value, "status": status_value.value if status_value else None,
            "priority": priority_value.value if priority_value else None, "category": category,
            "assignee": assignee, "q": q, "date_from": date_from, "date_to": date_to,
        }
        empty_title, empty_text = SCOPE_EMPTY[chosen]
        return await SupportPortal.page(
            request, template="support/pages/tickets/list.html", title=SCOPE_TITLES[chosen], active=chosen.value,
            ctx=ctx,
            model={
                "scope": chosen.value,
                "scope_title": SCOPE_TITLES[chosen],
                "rows": rows,
                "total": total,
                "page": build_page("/support/tickets", params, number, total),
                "values": {
                    "q": q or "", "status": status_value.value if status_value else "",
                    "priority": priority_value.value if priority_value else "", "category": category or "",
                    "assignee": assignee or "", "date_from": date_from or "", "date_to": date_to or "",
                },
                "filtered": any(params[key] for key in params if key != "scope"),
                "statuses": [(item.value, item.label) for item in TicketStatus],
                "priorities": [(item.value, item.label) for item in TicketPriority],
                "categories": [
                    (str(item.id), item.name) for item in await handler.list_categories(user, active_only=False)
                ],
                "assignees": [(str(item.user_id), item.name) for item in await handler.team_members(ctx)],
                "empty_title": empty_title,
                "empty_text": empty_text,
                "is_super_admin": ctx.is_super_admin,
            },
        )

    # ------------------------------------------------------------ live helpers

    @staticmethod
    async def live_counts(request: Request):
        """Badge counts and the latest event id; the live client also polls this when its socket is down."""
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return JSONResponse(status_code=403, content={"status": False})
        counts = await GetHandler.ticket_handler(request).queue_counts(ctx)
        bus = GetHandler.event_bus(request)
        return JSONResponse(
            content={"counts": counts, "latest_id": bus.latest_id, "redis": bus.redis_active},
            headers={"Cache-Control": "no-store"},
        )

    # ------------------------------------------------------------ detail

    @staticmethod
    def _allowed_statuses(ctx, ticket: Ticket) -> list[tuple[str, str]]:
        """Statuses this member may move the ticket to now (assignment has its own control)."""
        targets = []
        for target in ticket_rules.STAFF_TRANSITIONS.get(ticket.status, frozenset()):
            if target is TicketStatus.ASSIGNED:
                continue
            if any(ctx.has(permission) for permission in ticket_rules.permissions_for(target)):
                targets.append((target.value, target.label))
        order = [item.value for item in TicketStatus]
        return sorted(targets, key=lambda pair: order.index(pair[0]))

    @classmethod
    async def _detail_model(cls, request: Request, ctx, view, *, error: str | None = None, mode: str = "reply") -> dict:
        ticket = view.ticket
        closed = ticket.status is TicketStatus.CLOSED
        handler = GetHandler.ticket_handler(request)
        user = request.state.user
        can_assign = ctx.has(P.TICKET_ASSIGN) and ticket.team_id is not None and not closed
        can_priority = ctx.has(P.TICKET_CHANGE_PRIORITY)
        can_reply = ctx.has(P.TICKET_REPLY) and not closed
        can_note = ctx.has(P.TICKET_INTERNAL_NOTE)
        can_route = ctx.is_super_admin and ticket.assigned_to is None and not closed

        assignees = await handler.list_assignees(ticket.id, user) if can_assign else []
        calls_handler = GetHandler.call_handler(request)
        calls = await calls_handler.calls_for_ticket(ticket.id, user)
        open_call = await calls_handler.open_call(user)
        categories = await handler.list_categories(user, active_only=True) if can_priority else []
        teams: list = []
        if can_route:
            teams = [team for team in (await GetHandler.support_team_handler(request).list_teams(
                ListTeamsQuery(limit=100), user))[0] if team.is_active]

        now = now_naive_ist()
        timeline = [
            {"text": _describe(event), "actor": event.actor_name or "System", "when": _when(event.created_at)}
            for event in reversed(view.events)
        ]
        return {
            "ticket": ticket,
            "tone": STATUS_TONES[ticket.status],
            "role": _role(ticket.requester_role),
            "age": _age(ticket.created_at, now),
            "created": _when(ticket.created_at),
            "thread": _thread(view.messages, view.events),
            "timeline": timeline,
            "last_message_id": view.messages[-1].id if view.messages else 0,
            "can_reply": can_reply,
            "can_note": can_note,
            "can_compose": can_reply or can_note,
            "default_mode": mode if (mode == "note" and can_note) or not can_reply else "reply",
            "can_assign": can_assign,
            "can_priority": can_priority,
            "can_route": can_route,
            "assignees": [(str(item.user_id), item.name) for item in assignees],
            "categories": [(str(item.id), item.name) for item in categories],
            "teams": [(str(team.id), team.name) for team in teams],
            "priorities": [(item.value, item.label) for item in TicketPriority],
            "status_actions": cls._allowed_statuses(ctx, ticket),
            # Calls (Plan 29.1): the number is shown to everyone, dialling needs the permission
            "can_call": ctx.has(P.CALL_MAKE) and bool(ticket.requester_mobile),
            "calls": calls,
            "call_here": open_call if open_call and open_call.ticket_id == ticket.id else None,
            "call_elsewhere": open_call if open_call and open_call.ticket_id != ticket.id else None,
            "call_outcomes": [(item.value, item.label) for item in CallOutcome],
            "outcome_labels": {item.value: item.label for item in CallOutcome},
            "needs_assignment": ticket.status in NEEDS_ATTENTION and ticket.assigned_to is None,
            "closed": closed,
            "error": error,
            "notices": NOTICES,
            "notice": request.query_params.get("notice"),
        }

    @classmethod
    async def detail_page(cls, request: Request, ticket_id: UUID):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        try:
            view = await GetHandler.ticket_handler(request).get_for_staff(ticket_id, request.state.user)
        except TicketNotFoundException:
            return Renderer.redirect("/support/tickets")
        model = await cls._detail_model(request, ctx, view)
        scope = request.query_params.get("scope") or ""
        model["back_url"] = _query_url("/support/tickets", scope=scope if scope in {s.value for s in Scope} else None)
        return await SupportPortal.page(
            request, template="support/pages/tickets/detail.html", title=view.ticket.ticket_no,
            active=scope if scope in {s.value for s in Scope} else (default_scope(ctx) or ""), ctx=ctx, model=model,
        )

    # ------------------------------------------------------------ conversation

    @classmethod
    async def post_message(cls, request: Request, ticket_id: UUID):
        """Reply or internal note, with an optional file. HTMX swaps the conversation; without it we redirect."""
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        handler = GetHandler.ticket_handler(request)
        user = request.state.user
        form = await request.form()
        mode = "note" if str(form.get("mode")) == "note" else "reply"
        body = str(form.get("body") or "").strip()
        upload = form.get("file")
        has_file = bool(upload) and getattr(upload, "filename", "")

        error = None
        try:
            if body:
                await handler.post_staff_message(
                    PostMessageCommand(ticket_id=ticket_id, body=body, internal=mode == "note"), user,
                )
            if has_file:
                await handler.attach_for_staff(
                    AddAttachmentCommand(
                        ticket_id=ticket_id, file_name=upload.filename, content_type=upload.content_type or "",
                        data=await upload.read(), internal=mode == "note",
                    ),
                    user,
                )
            if not body and not has_file:
                error = "Write a message or choose a file."
        except TicketNotFoundException:
            return Renderer.redirect("/support/tickets")
        except FORM_ERRORS as exc:
            error = error_message(exc)

        if request.headers.get("HX-Request") != "true":
            return Renderer.redirect(f"/support/tickets/{ticket_id}")
        try:
            view = await handler.get_for_staff(ticket_id, user)
        except TicketNotFoundException:
            return Renderer.redirect("/support/tickets")
        model = await cls._detail_model(request, ctx, view, error=error, mode=mode)
        return Renderer.page(request=request, template="support/partials/ticket_thread.html", model=model)

    # ------------------------------------------------------------ actions

    @staticmethod
    async def _act(request: Request, ticket_id: UUID, notice: str, call):
        """Run one action; every outcome goes back to the ticket with a short notice code."""
        try:
            await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        form = await request.form()
        try:
            await call(GetHandler.ticket_handler(request), form, request.state.user)
        except TicketNotFoundException:
            return Renderer.redirect("/support/tickets")
        except _ACTION_ERRORS as exc:
            return Renderer.redirect(f"/support/tickets/{ticket_id}?notice={_error_code(exc)}")
        return Renderer.redirect(f"/support/tickets/{ticket_id}?notice={notice}")

    @classmethod
    async def assign(cls, request: Request, ticket_id: UUID):
        async def call(handler, form, user):
            assignee = optional_uuid(str(form.get("assignee") or ""))
            if assignee is None:
                raise MissingChoice("Choose a member.")
            await handler.assign(AssignTicketCommand(ticket_id=ticket_id, assignee_user_id=assignee), user)
        return await cls._act(request, ticket_id, "assigned", call)

    @classmethod
    async def set_status(cls, request: Request, ticket_id: UUID):
        async def call(handler, form, user):
            try:
                status = TicketStatus(str(form.get("status")))
            except ValueError:
                raise MissingChoice("Choose a status.") from None
            await handler.change_status(ChangeStatusCommand(ticket_id=ticket_id, status=status), user)
        return await cls._act(request, ticket_id, "status", call)

    @classmethod
    async def set_priority(cls, request: Request, ticket_id: UUID):
        async def call(handler, form, user):
            try:
                priority = TicketPriority(str(form.get("priority")))
            except ValueError:
                raise MissingChoice("Choose a priority.") from None
            await handler.change_priority(ChangePriorityCommand(ticket_id=ticket_id, priority=priority), user)
        return await cls._act(request, ticket_id, "priority", call)

    @classmethod
    async def set_category(cls, request: Request, ticket_id: UUID):
        async def call(handler, form, user):
            category = optional_uuid(str(form.get("category") or ""))
            if category is None:
                raise MissingChoice("Choose a category.")
            await handler.change_category(ChangeCategoryCommand(ticket_id=ticket_id, category_id=category), user)
        return await cls._act(request, ticket_id, "category", call)

    @classmethod
    async def route(cls, request: Request, ticket_id: UUID):
        async def call(handler, form, user):
            team = optional_uuid(str(form.get("team") or ""))
            if team is None:
                raise MissingChoice("Choose a team.")
            await handler.route_to_team(RouteTicketCommand(ticket_id=ticket_id, team_id=team), user)
        return await cls._act(request, ticket_id, "routed", call)

    # ------------------------------------------------------------ files

    @staticmethod
    async def attachment(request: Request, attachment_id: UUID):
        """A ticket file, shown inline for images; never cached and never guessed by the browser."""
        try:
            await SupportPortal.context(request)
            attachment, path = await GetHandler.ticket_handler(request).open_attachment(
                attachment_id, request.state.user,
            )
        except (SupportAccessDeniedException, TicketNotFoundException):
            return Response(status_code=404)
        if not path.is_file():
            return Response(status_code=404)
        return FileResponse(
            path,
            media_type=attachment.mime_type,
            filename=attachment.file_name,
            content_disposition_type="inline",
            headers={"Cache-Control": "private, no-store", "X-Content-Type-Options": "nosniff"},
        )

