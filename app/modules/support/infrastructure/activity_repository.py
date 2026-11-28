"""
Activity and Audit Repository (Phase 29, REQ-79, REQ-80, D-10)

Every number is an aggregate query over what already exists: ticket events, messages, call logs and
tickets. Nothing is counted in Python and no counter table is kept. Each metric is one grouped query
for any number of members, so the team comparison costs the same as one member's page.

Python 3.13+
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import Date, and_, cast, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.models import UserModel
from app.modules.support.domain.enums import EventType, TicketStatus
from app.modules.support.domain.ticket_rules import OPEN_STATES
from app.modules.support.infrastructure.models import (
    SupportAuditLogModel,
    SupportCallLogModel,
    SupportMemberModel,
    SupportTicketEventModel,
    SupportTicketMessageModel,
    SupportTicketModel,
)

E = SupportTicketEventModel
M = SupportTicketMessageModel
C = SupportCallLogModel


class ActivityRepository:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    @property
    def _sqlite(self) -> bool:
        return self._database.engine.dialect.name == "sqlite"

    def _day(self, column):
        return func.date(column) if self._sqlite else cast(column, Date)

    def _seconds_between(self, later, earlier):
        if self._sqlite:
            return (func.julianday(later) - func.julianday(earlier)) * 86400.0
        return func.extract("epoch", later - earlier)

    async def _grouped(self, key, stmt) -> dict[str, int]:
        rows = (await self._session.execute(stmt.group_by(key))).all()
        return {str(row[0]): int(row[1] or 0) for row in rows}

    # ------------------------------------------------------------ member numbers

    async def counts(self, user_ids: list[UUID], start: datetime, end: datetime) -> dict[str, dict[str, Any]]:
        """{user id: {metric: value}} for every member, one grouped query per metric."""
        if not user_ids:
            return {}
        ids = list(user_ids)
        texts = [str(user_id) for user_id in ids]
        in_range = lambda column: and_(column >= start, column < end)  # noqa: E731

        def events(*where):
            return select(E.actor_user_id, func.count(E.id)).where(E.actor_user_id.in_(ids), in_range(E.created_at), *where)

        metrics: dict[str, dict[str, int]] = {
            "replies": await self._grouped(
                M.sender_user_id,
                select(M.sender_user_id, func.count(M.id)).where(
                    M.sender_user_id.in_(ids), M.sender_is_staff.is_(True), M.is_internal.is_(False), in_range(M.created_at),
                ),
            ),
            "notes": await self._grouped(
                M.sender_user_id,
                select(M.sender_user_id, func.count(M.id)).where(
                    M.sender_user_id.in_(ids), M.is_internal.is_(True), in_range(M.created_at),
                ),
            ),
            "assigned_to_me": await self._grouped(
                E.to_value,
                select(E.to_value, func.count(E.id)).where(
                    E.event_type == EventType.ASSIGNED, E.to_value.in_(texts), in_range(E.created_at),
                ),
            ),
            "assignments_made": await self._grouped(E.actor_user_id, events(E.event_type == EventType.ASSIGNED)),
            "reassigned": await self._grouped(
                E.actor_user_id, events(E.event_type == EventType.ASSIGNED, E.from_value.is_not(None)),
            ),
            "resolved": await self._grouped(
                E.actor_user_id, events(E.event_type == EventType.STATUS_CHANGED, E.to_value == TicketStatus.RESOLVED.value),
            ),
            "closed": await self._grouped(
                E.actor_user_id, events(E.event_type == EventType.STATUS_CHANGED, E.to_value == TicketStatus.CLOSED.value),
            ),
        }

        # Calls by outcome (an open call has no outcome yet)
        calls: dict[str, dict[str, int]] = defaultdict(dict)
        rows = (
            await self._session.execute(
                select(C.member_user_id, C.outcome, func.count(C.id))
                .where(C.member_user_id.in_(ids), in_range(C.started_at))
                .group_by(C.member_user_id, C.outcome)
            )
        ).all()
        for member, outcome, count in rows:
            calls[str(member)][outcome or "OPEN"] = int(count)

        # Average time to the first staff reply, for tickets whose first reply this member wrote in the range
        first = (
            select(E.ticket_id, func.min(E.id).label("first_id"))
            .where(E.event_type == EventType.REPLIED)
            .group_by(E.ticket_id)
            .subquery()
        )
        rows = (
            await self._session.execute(
                select(E.actor_user_id, func.avg(self._seconds_between(E.created_at, SupportTicketModel.created_at)))
                .join(first, first.c.first_id == E.id)
                .join(SupportTicketModel, SupportTicketModel.id == E.ticket_id)
                .where(E.actor_user_id.in_(ids), in_range(E.created_at))
                .group_by(E.actor_user_id)
            )
        ).all()
        first_reply = {str(member): float(value) for member, value in rows if value is not None}

        result: dict[str, dict[str, Any]] = {}
        for user_id in texts:
            row: dict[str, Any] = {name: values.get(user_id, 0) for name, values in metrics.items()}
            row["calls_by_outcome"] = dict(calls.get(user_id, {}))
            row["calls"] = sum(row["calls_by_outcome"].values())
            row["avg_first_reply_s"] = first_reply.get(user_id)
            result[user_id] = row
        return result

    async def trend(self, user_id: UUID, start: datetime, end: datetime) -> dict[str, int]:
        """{yyyy-mm-dd: actions} - replies, notes, status moves, assignments and calls per day."""
        totals: dict[str, int] = defaultdict(int)
        day_m, day_e, day_c = self._day(M.created_at), self._day(E.created_at), self._day(C.started_at)
        queries = (
            select(day_m, func.count(M.id)).where(
                M.sender_user_id == user_id, M.sender_is_staff.is_(True), M.created_at >= start, M.created_at < end,
            ).group_by(day_m),
            select(day_e, func.count(E.id)).where(
                E.actor_user_id == user_id,
                E.event_type.in_([EventType.STATUS_CHANGED, EventType.ASSIGNED]),
                E.created_at >= start, E.created_at < end,
            ).group_by(day_e),
            select(day_c, func.count(C.id)).where(
                C.member_user_id == user_id, C.started_at >= start, C.started_at < end,
            ).group_by(day_c),
        )
        for stmt in queries:
            for day, count in (await self._session.execute(stmt)).all():
                totals[str(day)[:10]] += int(count)
        return dict(totals)

    async def open_by_status(self, user_id: UUID) -> dict[str, int]:
        rows = (
            await self._session.execute(
                select(SupportTicketModel.status, func.count(SupportTicketModel.id))
                .where(SupportTicketModel.assigned_to == user_id, SupportTicketModel.status.in_(OPEN_STATES))
                .group_by(SupportTicketModel.status)
            )
        ).all()
        return {str(getattr(status, "value", status)): int(count) for status, count in rows}

    async def recent(self, user_id: UUID, *, limit: int = 15) -> list[dict[str, Any]]:
        rows = (
            await self._session.execute(
                select(E.event_type, E.from_value, E.to_value, E.meta, E.created_at, E.ticket_id, SupportTicketModel.ticket_no)
                .join(SupportTicketModel, SupportTicketModel.id == E.ticket_id)
                .where(E.actor_user_id == user_id)
                .order_by(E.id.desc())
                .limit(limit)
            )
        ).all()
        return [dict(row._mapping) for row in rows]

    # ------------------------------------------------------------ audit log

    async def audit_page(
        self,
        *,
        team_id: UUID | None,
        actor_id: UUID | None,
        action: str | None,
        entity_id: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[dict[str, Any]], int]:
        """Newest first. `team_id` None = every team (Super Admin)."""
        A = SupportAuditLogModel
        conditions = []
        if team_id is not None:
            conditions.append(A.team_id == team_id)
        if actor_id is not None:
            conditions.append(A.actor_id == actor_id)
        if action:
            conditions.append(A.action == action)
        if entity_id:
            conditions.append(A.entity_id == entity_id)
        if date_from is not None:
            conditions.append(A.created_at >= date_from)
        if date_to is not None:
            conditions.append(A.created_at <= date_to)
        total = int(await self._session.scalar(select(func.count(A.id)).where(*conditions)) or 0)
        rows = (
            await self._session.execute(
                select(A, UserModel.name.label("actor_name"))
                .outerjoin(UserModel, UserModel.id == A.actor_id)
                .where(*conditions)
                .order_by(A.created_at.desc(), A.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        items = [
            {
                "id": row[0].id, "actor_id": row[0].actor_id, "actor_name": row.actor_name, "action": row[0].action,
                "entity": row[0].entity, "entity_id": row[0].entity_id, "meta": row[0].meta or {},
                "team_id": row[0].team_id, "created_at": row[0].created_at,
            }
            for row in rows
        ]
        await self._name_entities(items)
        return items, total

    async def _name_entities(self, items: list[dict[str, Any]]) -> None:
        """Ticket numbers and member names for the page, two queries whatever the page size."""
        ticket_ids, member_ids, user_ids = set(), set(), set()
        for item in items:
            try:
                user_ids.add(UUID(str(item["meta"].get("assignee"))))
            except (TypeError, ValueError):
                pass
            try:
                key = UUID(str(item["entity_id"]))
            except (TypeError, ValueError):
                continue
            if item["entity"] == "ticket":
                ticket_ids.add(key)
            elif item["entity"] == "member":
                member_ids.add(key)
        tickets = dict(
            (await self._session.execute(
                select(SupportTicketModel.id, SupportTicketModel.ticket_no).where(SupportTicketModel.id.in_(ticket_ids))
            )).all()
        ) if ticket_ids else {}
        members = dict(
            (await self._session.execute(
                select(SupportMemberModel.id, UserModel.name)
                .join(UserModel, UserModel.id == SupportMemberModel.user_id)
                .where(SupportMemberModel.id.in_(member_ids))
            )).all()
        ) if member_ids else {}
        users = dict(
            (await self._session.execute(select(UserModel.id, UserModel.name).where(UserModel.id.in_(user_ids)))).all()
        ) if user_ids else {}
        for item in items:
            try:
                item["assignee_name"] = users.get(UUID(str(item["meta"].get("assignee"))))
            except (TypeError, ValueError):
                item["assignee_name"] = None
            try:
                key = UUID(str(item["entity_id"]))
            except (TypeError, ValueError):
                key = None
            item["ticket_no"] = tickets.get(key) or item["meta"].get("ticket_no")
            item["member_name"] = members.get(key)

    async def audit_actions(self, team_id: UUID | None) -> list[str]:
        stmt = select(SupportAuditLogModel.action).distinct()
        if team_id is not None:
            stmt = stmt.where(SupportAuditLogModel.team_id == team_id)
        return sorted(str(value) for value in (await self._session.scalars(stmt)).all())
