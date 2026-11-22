"""
Support activity screens (Plan 29.2, REQ-79, D-10)

/support/activity                      My Activity (a Manager / Super Admin picks a member with ?member=)
/support/activity/team                 team comparison table (Manager, report.view, or Super Admin with ?team=)

Python 3.13+
"""

from __future__ import annotations

from datetime import date
from typing import Any
from urllib.parse import urlencode
from uuid import UUID

from fastapi import Request

from app.modules.dependencies import GetHandler
from app.modules.support.application.activity_query import PERIODS, period
from app.modules.support.application.command import ListTeamsQuery
from app.modules.support.domain.entities import TicketEvent
from app.modules.support.domain.enums import CallOutcome, EventType, TicketStatus
from app.modules.support.domain.exceptions import (
    MemberNotFoundException,
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    SupportValidationException,
    TeamNotFoundException,
)
from app.modules.support.domain.permissions import SupportPermission as P
from app.web.framework.renderer import Renderer
from app.web.support.forms import optional_uuid
from app.web.support.portal import SupportPortal
from app.web.support.tickets_controller import _describe, _when

CHART_W, CHART_H, CHART_PAD = 640, 160, 24

SORTABLE = ("name", "assigned_to_me", "replies", "resolved", "closed", "notes", "assignments_made", "calls")


def _duration(seconds: float | None) -> str:
    if seconds is None:
        return "—"
    seconds = int(seconds)
    if seconds < 3600:
        return f"{max(1, seconds // 60)} min"
    if seconds < 86400:
        return f"{seconds // 3600} h {seconds % 3600 // 60} min"
    return f"{seconds // 86400} d {seconds % 86400 // 3600} h"


def _chart(points: list[tuple[date, int]]) -> dict[str, Any]:
    """Bars for the inline SVG: one series, baseline at the bottom, 2 px gaps, rounded data ends."""
    count = max(1, len(points))
    peak = max([value for _, value in points] + [1])
    inner_w, inner_h = CHART_W - CHART_PAD, CHART_H - CHART_PAD
    slot = inner_w / count
    width = max(2.0, slot - 2)
    every = max(1, count // 8)                                    # at most about eight day labels
    bars = []
    for index, (day, value) in enumerate(points):
        height = 0 if not value else max(3.0, inner_h * value / peak)
        bars.append({
            "x": round(CHART_PAD + index * slot + 1, 2), "y": round(inner_h - height, 2),
            "w": round(width, 2), "h": round(height, 2), "value": value,
            "label": f"{day:%d %b}", "show_label": index % every == 0 or index == count - 1,
            "cx": round(CHART_PAD + index * slot + slot / 2, 2),
        })
    return {"bars": bars, "peak": peak, "w": CHART_W, "h": CHART_H, "base": inner_h, "pad": CHART_PAD,
            "total": sum(value for _, value in points)}


def _sees_team(ctx) -> bool:
    return ctx.is_super_admin or ctx.has(P.REPORT_VIEW)


def _period(request: Request):
    params = request.query_params
    try:
        return period(params.get("period"), params.get("from"), params.get("to")), None
    except SupportValidationException as exc:
        return period("week"), exc.message


class SupportActivityController:

    @staticmethod
    async def member_page(request: Request):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        member_id = optional_uuid(request.query_params.get("member"))
        if ctx.is_super_admin and member_id is None:
            return Renderer.redirect("/support/activity/team")
        when, error = _period(request)
        try:
            view = await GetHandler.activity_query(request).member_activity(
                request.state.user, member_id=member_id, when=when,
            )
        except SupportPermissionDeniedException:
            return Renderer.redirect("/support/activity")
        except MemberNotFoundException:
            return Renderer.redirect("/support/activity/team" if _sees_team(ctx) else "/support/activity")

        numbers = view.numbers
        calls = numbers.get("calls_by_outcome", {})
        recent = []
        for item in view.recent:
            event = TicketEvent(
                ticket_id=item["ticket_id"], actor_user_id=None, event_type=EventType(item["event_type"]),
                from_value=item["from_value"], to_value=item["to_value"], meta=item["meta"] or {},
            )
            recent.append({"text": _describe(event), "ticket_no": item["ticket_no"], "ticket_id": item["ticket_id"],
                           "when": _when(item["created_at"])})
        own = view.member.user_id == ctx.user_id
        return await SupportPortal.page(
            request, template="support/pages/activity/member.html",
            title="My activity" if own else f"Activity of {view.member.name}",
            active="activity" if own else "team_activity", ctx=ctx,
            model={
                "view": view, "own": own, "error": error, "periods": PERIODS,
                "chart": _chart(view.trend),
                "first_reply": _duration(numbers.get("avg_first_reply_s")),
                "shows_first_reply": any(card["key"] == "replies" for card in view.cards),
                "calls": [(CallOutcome(key).label if key != "OPEN" else "No outcome yet", value) for key, value in calls.items()],
                "open_by_status": [(TicketStatus(key).label, value) for key, value in view.open_by_status.items()],
                "recent": recent,
                "member_options": [(str(m.id), m.name) for m in view.members],
                "query": {"from": request.query_params.get("from") or "", "to": request.query_params.get("to") or ""},
            },
        )

    @staticmethod
    async def team_page(request: Request):
        try:
            ctx = await SupportPortal.context(request)
        except SupportAccessDeniedException:
            return SupportPortal.denied()
        if not _sees_team(ctx):
            return SupportPortal.denied()
        user = request.state.user
        team_id = optional_uuid(request.query_params.get("team"))
        teams: list = []
        if ctx.is_super_admin:
            teams = (await GetHandler.support_team_handler(request).list_teams(ListTeamsQuery(limit=100), user))[0]
            if team_id is None and teams:
                team_id = teams[0].id
            if team_id is None:
                return await SupportPortal.page(
                    request, template="support/pages/activity/team.html", title="Team activity", active="team_activity",
                    ctx=ctx, model={"view": None, "teams": [], "periods": PERIODS, "error": None, "query": {}},
                )
        when, error = _period(request)
        try:
            view = await GetHandler.activity_query(request).team_activity(user, team_id=team_id, when=when)
        except (TeamNotFoundException, SupportPermissionDeniedException):
            return SupportPortal.denied()

        sort = request.query_params.get("sort") or "replies"
        sort = sort if sort in SORTABLE else "replies"
        if sort == "name":
            view.rows.sort(key=lambda row: row["member"].name.lower())
        else:
            view.rows.sort(key=lambda row: (-int(row.get(sort) or 0), row["member"].name.lower()))
        return await SupportPortal.page(
            request, template="support/pages/activity/team.html", title="Team activity", active="team_activity", ctx=ctx,
            model={
                "view": view, "teams": [(str(t.id), t.name) for t in teams], "team_id": str(view.team.id),
                "periods": PERIODS, "error": error, "sort": sort,
                "sort_urls": {
                    key: "/support/activity/team?" + urlencode({
                        name: value for name, value in {
                            "team": str(view.team.id) if ctx.is_super_admin else None, "period": when.key,
                            "from": request.query_params.get("from"), "to": request.query_params.get("to"), "sort": key,
                        }.items() if value
                    })
                    for key in SORTABLE
                },
                "first_reply": {str(row["member"].user_id): _duration(row.get("avg_first_reply_s")) for row in view.rows},
                "query": {"from": request.query_params.get("from") or "", "to": request.query_params.get("to") or ""},
            },
        )
