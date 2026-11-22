"""
My Activity, team activity and the audit log (Phase 29, REQ-79, REQ-80, D-10)

Who may see what:
- every member sees their own activity; asking for someone else is refused (403);
- a Manager (or a member with `support.report.view`) sees every member of their team and the team table;
  a member of another team looks like one that does not exist (404);
- Super Admin sees any member and any team;
- the audit log is for the Manager (their team) and Super Admin (all teams) only.

The cards follow the member's role: a Ticket Assigner is counted on assignments, Technical Support on
replies and resolutions, a Caller on calls; a Viewer has nothing to count and gets an honest empty state.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any
from uuid import UUID

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.support.application.guard import SupportContext, SupportGuard
from app.modules.support.domain.entities import SupportMember, SupportTeam
from app.modules.support.domain.exceptions import (
    MemberNotFoundException,
    SupportPermissionDeniedException,
    SupportValidationException,
    TeamNotFoundException,
)
from app.modules.support.domain.irepository import ISupportRepository
from app.modules.support.domain.permissions import ALL_PERMISSIONS, SUPER_ADMIN_ONLY, SupportPermission as P
from app.modules.support.infrastructure.activity_repository import ActivityRepository

PERIODS = {"today": "Today", "week": "Last 7 days", "month": "Last 30 days", "custom": "Custom"}
MAX_DAYS = 366

# (metric, label, note, permissions any of which makes the card relevant)
CARDS: tuple[tuple[str, str, str, tuple[P, ...]], ...] = (
    ("assigned_to_me", "Assigned to me", "Tickets given to you", (P.TICKET_VIEW_ASSIGNED,)),
    ("replies", "Replies sent", "Messages to requesters", (P.TICKET_REPLY,)),
    ("resolved", "Resolved", "Tickets you marked resolved", (P.TICKET_RESOLVE,)),
    ("closed", "Closed", "Tickets you closed", (P.TICKET_CLOSE,)),
    ("notes", "Internal notes", "Notes for the team", (P.TICKET_INTERNAL_NOTE,)),
    ("assignments_made", "Assignments made", "Tickets you handed out", (P.TICKET_ASSIGN,)),
    ("reassigned", "Reassigned", "Tickets moved to someone else", (P.TICKET_ASSIGN,)),
    ("calls", "Calls", "Calls to requesters", (P.CALL_MAKE,)),
)


@dataclass(slots=True, frozen=True)
class Period:
    key: str
    label: str
    start: datetime
    end: datetime          # exclusive

    @property
    def days(self) -> list[date]:
        first = self.start.date()
        return [first + timedelta(days=i) for i in range((self.end.date() - first).days)]


def period(key: str | None, date_from: str | None = None, date_to: str | None = None) -> Period:
    today = now_naive_ist().replace(hour=0, minute=0, second=0, microsecond=0)
    tomorrow = today + timedelta(days=1)
    key = key if key in PERIODS else "week"
    if key == "today":
        return Period(key, PERIODS[key], today, tomorrow)
    if key == "month":
        return Period(key, PERIODS[key], today - timedelta(days=29), tomorrow)
    if key == "custom":
        try:
            start = datetime.strptime((date_from or "").strip(), "%Y-%m-%d")
            end = datetime.strptime((date_to or "").strip(), "%Y-%m-%d") + timedelta(days=1)
        except ValueError:
            raise SupportValidationException("Choose a start and an end date.") from None
        if end <= start:
            raise SupportValidationException("The end date must be on or after the start date.")
        if (end - start).days > MAX_DAYS:
            raise SupportValidationException("Choose at most one year.")
        label = f"{start:%d %b %Y} – {(end - timedelta(days=1)):%d %b %Y}"
        return Period(key, label, start, end)
    return Period("week", PERIODS["week"], today - timedelta(days=6), tomorrow)


def member_permissions(member: SupportMember) -> frozenset[P]:
    return (ALL_PERMISSIONS - SUPER_ADMIN_ONLY) if member.is_manager else member.permissions


def cards_for(member: SupportMember, numbers: dict[str, Any]) -> list[dict[str, Any]]:
    permissions = member_permissions(member)
    return [
        {"key": key, "label": label, "note": note, "value": numbers.get(key, 0)}
        for key, label, note, needs in CARDS
        if any(permission in permissions for permission in needs)
    ]


@dataclass(slots=True, kw_only=True)
class ActivityView:
    member: SupportMember
    period: Period
    numbers: dict[str, Any]
    cards: list[dict[str, Any]]
    trend: list[tuple[date, int]]
    open_by_status: dict[str, int]
    recent: list[dict[str, Any]]
    can_switch: bool = False                     # Manager / Super Admin: a member picker is shown
    members: list[SupportMember] = field(default_factory=list)


@dataclass(slots=True, kw_only=True)
class TeamActivityView:
    team: SupportTeam
    period: Period
    rows: list[dict[str, Any]]
    totals: dict[str, int]


class ActivityQuery:

    __slots__ = ("_database", "_activity", "_support", "_guard")

    def __init__(self, *, database: DatabaseManager, activity: ActivityRepository, support: ISupportRepository) -> None:
        self._database = database
        self._activity = activity
        self._support = support
        self._guard = SupportGuard(support)

    @staticmethod
    def _sees_team(ctx: SupportContext) -> bool:
        return ctx.is_super_admin or ctx.has(P.REPORT_VIEW)

    async def _team_members(self, team_id: UUID) -> list[SupportMember]:
        members, _total = await self._support.list_members(team_id, search=None, limit=500, offset=0)
        return members

    async def member_activity(
        self, actor: CurrentUser | None, *, member_id: UUID | None, when: Period,
    ) -> ActivityView:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if member_id is None:
                if ctx.member is None:
                    raise MemberNotFoundException("Choose a member.")
                member = ctx.member
            else:
                member = await self._support.get_member(member_id)
                if member is None:
                    raise MemberNotFoundException()
                if member.user_id != ctx.user_id:
                    if not self._sees_team(ctx):
                        raise SupportPermissionDeniedException("You can only see your own activity.")
                    if not ctx.can_access_team(member.team_id):
                        raise MemberNotFoundException()
            numbers = (await self._activity.counts([member.user_id], when.start, when.end)).get(str(member.user_id), {})
            per_day = await self._activity.trend(member.user_id, when.start, when.end)
            view = ActivityView(
                member=member,
                period=when,
                numbers=numbers,
                cards=cards_for(member, numbers),
                trend=[(day, per_day.get(day.isoformat(), 0)) for day in when.days],
                open_by_status=await self._activity.open_by_status(member.user_id),
                recent=await self._activity.recent(member.user_id),
                can_switch=self._sees_team(ctx),
            )
            if view.can_switch:
                view.members = await self._team_members(member.team_id)
        return view

    async def team_activity(self, actor: CurrentUser | None, *, team_id: UUID | None, when: Period) -> TeamActivityView:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not self._sees_team(ctx):
                raise SupportPermissionDeniedException()
            scope = ctx.team_scope(team_id)
            team = await self._support.get_team(scope)
            if team is None:
                raise TeamNotFoundException()
            members = await self._team_members(scope)
            numbers = await self._activity.counts([m.user_id for m in members], when.start, when.end)
        rows = []
        for member in members:
            row = numbers.get(str(member.user_id), {})
            rows.append({"member": member, **row})
        keys = ("assigned_to_me", "replies", "resolved", "closed", "notes", "assignments_made", "calls")
        totals = {key: sum(int(row.get(key) or 0) for row in rows) for key in keys}
        return TeamActivityView(team=team, period=when, rows=rows, totals=totals)

    async def today_cards(self, ctx: SupportContext) -> list[dict[str, Any]]:
        """The member's own numbers for today, for the support home page."""
        if ctx.member is None:
            return []
        today = period("today")
        async with self._database.transaction():
            numbers = (await self._activity.counts([ctx.user_id], today.start, today.end)).get(str(ctx.user_id), {})
        return cards_for(ctx.member, numbers)

    # ------------------------------------------------------------ audit

    async def audit(
        self,
        actor: CurrentUser | None,
        *,
        team_id: UUID | None,
        actor_id: UUID | None,
        action: str | None,
        ticket_id: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int, list[str], SupportContext]:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not (ctx.is_super_admin or ctx.is_manager):
                raise SupportPermissionDeniedException()
            scope = team_id if ctx.is_super_admin else ctx.team_id
            items, total = await self._activity.audit_page(
                team_id=scope, actor_id=actor_id, action=action or None, entity_id=ticket_id or None,
                date_from=date_from, date_to=date_to, limit=limit, offset=offset,
            )
            actions = await self._activity.audit_actions(scope)
        return items, total, actions, ctx
