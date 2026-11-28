"""
Support audit screen (Plan 29.2, REQ-80, REQ-64)

/support/audit   who did what and when: Manager (their team) and Super Admin (every team), read-only.
There is no screen or API that edits or deletes audit rows.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime, time
from typing import Any

from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.support.application.command import ListMembersQuery, ListTeamsQuery
from app.modules.support.domain.enums import CallOutcome, TicketStatus
from app.modules.support.domain.exceptions import SupportAccessDeniedException, SupportPermissionDeniedException
from app.web.support.forms import PAGE_SIZE, build_page, optional_uuid, page_number
from app.web.support.portal import SupportPortal

LABELS = {
    "team.created": "Team created", "team.updated": "Team edited", "team.activated": "Team enabled",
    "team.deactivated": "Team disabled", "member.created": "Member added", "member.updated": "Member edited",
    "member.activated": "Member enabled", "member.deactivated": "Member disabled",
    "member.role_changed": "Role changed", "role.created": "Role created", "role.updated": "Role edited",
    "category.created": "Category created", "category.updated": "Category edited",
    "ticket.created": "Ticket raised", "ticket.routed": "Ticket sent to team", "ticket.assigned": "Ticket assigned",
    "ticket.status_changed": "Status changed", "ticket.priority_changed": "Priority changed",
    "ticket.category_changed": "Category changed", "ticket.note_added": "Internal note",
    "ticket.phone_viewed": "Phone number seen", "call.started": "Call started", "call.logged": "Call outcome",
}


def _status(value: Any) -> str:
    try:
        return TicketStatus(str(value)).label
    except ValueError:
        return str(value or "")


def sentence(item: dict[str, Any]) -> str:
    """'Asha assigned TS-2026-000123 to Ravi' — the row as a person would say it."""
    who = item.get("actor_name") or "Someone"
    meta = item.get("meta") or {}
    ticket = item.get("ticket_no") or "a ticket"
    member = item.get("member_name") or meta.get("name") or "a member"
    action = item.get("action")
    texts = {
        "team.created": f"{who} created the team {meta.get('name', '')}".strip(),
        "team.updated": f"{who} edited the team",
        "team.activated": f"{who} enabled the team",
        "team.deactivated": f"{who} disabled the team",
        "member.created": f"{who} added {member}" + (f" as {meta['role']}" if meta.get("role") else ""),
        "member.updated": f"{who} edited {member}",
        "member.activated": f"{who} enabled {member}",
        "member.deactivated": f"{who} disabled {member}",
        "member.role_changed": f"{who} changed the role of {member} to {meta.get('role', '')}".strip(),
        "role.created": f"{who} created a role",
        "role.updated": f"{who} edited a role",
        "category.created": f"{who} created the category {meta.get('name', '')}".strip(),
        "category.updated": f"{who} edited a category",
        "ticket.created": f"{who} raised {ticket}",
        "ticket.routed": f"{who} sent {ticket} to {meta.get('team', 'a team')}",
        "ticket.assigned": f"{who} assigned {ticket}" + (f" to {item['assignee_name']}" if item.get("assignee_name") else ""),
        "ticket.status_changed": f"{who} moved {ticket} from {_status(meta.get('previous'))} to {_status(meta.get('status'))}",
        "ticket.priority_changed": f"{who} changed the priority of {ticket} to {str(meta.get('priority', '')).title()}",
        "ticket.category_changed": f"{who} moved {ticket} to the category {meta.get('category', '')}".strip(),
        "ticket.note_added": f"{who} wrote an internal note on {ticket}",
        "ticket.phone_viewed": f"{who} saw the requester's phone number on {ticket}",
        "call.started": f"{who} called the requester of {ticket}",
        "call.logged": f"{who} recorded a call on {ticket}: " + (
            CallOutcome(meta["outcome"]).label if meta.get("outcome") in CallOutcome.__members__ else "outcome saved"
        ),
    }
    return texts.get(action, f"{who}: {LABELS.get(action, action)}")


def _day(value: str | None, *, end: bool) -> datetime | None:
    try:
        day = datetime.strptime((value or "").strip(), "%Y-%m-%d")
    except ValueError:
        return None
    return datetime.combine(day.date(), time.max if end else time.min)


class SupportAuditController:

    @staticmethod
    async def list_page(request: Request):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        if not (ctx.is_super_admin or ctx.is_manager):
            return SupportPortal.denied()
        params = request.query_params
        number = page_number(params.get("page"))
        team_id = optional_uuid(params.get("team")) if ctx.is_super_admin else ctx.team_id
        user = request.state.user
        try:
            items, total, actions, ctx = await GetHandler.activity_query(request).audit(
                user,
                team_id=team_id,
                actor_id=optional_uuid(params.get("member")),
                action=params.get("action") if params.get("action") in LABELS else None,
                ticket_id=str(optional_uuid(params.get("ticket")) or "") or None,
                date_from=_day(params.get("from"), end=False),
                date_to=_day(params.get("to"), end=True),
                limit=PAGE_SIZE,
                offset=(number - 1) * PAGE_SIZE,
            )
        except SupportPermissionDeniedException:
            return SupportPortal.denied()

        rows = [
            {
                "when": item["created_at"].strftime("%d %b %Y, %H:%M"),
                "text": sentence(item),
                "label": LABELS.get(item["action"], item["action"]),
                "actor": item.get("actor_name") or "—",
                "ticket_id": item["entity_id"] if item["entity"] == "ticket" else None,
                "ticket_no": item.get("ticket_no") if item["entity"] == "ticket" else None,
            }
            for item in items
        ]
        members: list = []
        if team_id is not None:
            members = (await GetHandler.support_member_handler(request).list_members(
                ListMembersQuery(team_id=team_id, limit=100), user,
            ))[0]
        teams = []
        if ctx.is_super_admin:
            teams = [(str(t.id), t.name) for t in (await GetHandler.support_team_handler(request).list_teams(
                ListTeamsQuery(limit=100), user))[0]]
        keep = {key: params.get(key) for key in ("team", "member", "action", "ticket", "from", "to")}
        return await SupportPortal.page(
            request, template="support/pages/audit/list.html", title="Audit log", active="audit", ctx=ctx,
            model={
                "rows": rows, "total": total, "page": build_page("/support/audit", keep, number, total),
                "values": {key: value or "" for key, value in keep.items()},
                "actions": [(action, LABELS.get(action, action)) for action in actions],
                "members": [(str(m.user_id), m.name) for m in members],
                "teams": teams,
                "filtered": any(keep.values()),
            },
        )
