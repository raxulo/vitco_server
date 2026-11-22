"""
Call Log Repository (Phase 29, REQ-78)

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.models import UserModel
from app.modules.support.domain.entities import CallLog
from app.modules.support.infrastructure.models import SupportCallLogModel, SupportTicketModel


class CallRepository:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    def _query(self):
        return (
            select(SupportCallLogModel, UserModel.name.label("member_name"), SupportTicketModel.ticket_no)
            .join(UserModel, UserModel.id == SupportCallLogModel.member_user_id)
            .join(SupportTicketModel, SupportTicketModel.id == SupportCallLogModel.ticket_id)
        )

    @staticmethod
    def _to_call(row) -> CallLog:
        model: SupportCallLogModel = row[0]
        return CallLog(
            id=model.id, ticket_id=model.ticket_id, member_user_id=model.member_user_id,
            requester_user_id=model.requester_user_id, started_at=model.started_at, finished_at=model.finished_at,
            outcome=model.outcome, duration_s=model.duration_s, note=model.note,
            member_name=row.member_name, ticket_no=row.ticket_no,
        )

    async def add(self, call: CallLog) -> None:
        self._session.add(
            SupportCallLogModel(
                id=call.id, ticket_id=call.ticket_id, member_user_id=call.member_user_id,
                requester_user_id=call.requester_user_id, started_at=call.started_at or now_naive_ist(),
            )
        )
        await self._session.flush()

    async def get(self, call_id: UUID) -> CallLog | None:
        row = (await self._session.execute(self._query().where(SupportCallLogModel.id == call_id))).first()
        return self._to_call(row) if row else None

    async def open_call(self, member_user_id: UUID) -> CallLog | None:
        row = (
            await self._session.execute(
                self._query()
                .where(SupportCallLogModel.member_user_id == member_user_id, SupportCallLogModel.finished_at.is_(None))
                .order_by(SupportCallLogModel.started_at.desc())
                .limit(1)
            )
        ).first()
        return self._to_call(row) if row else None

    async def finish(
        self, call_id: UUID, *, outcome: str, duration_s: int | None, note: str | None, finished_at: datetime,
    ) -> None:
        await self._session.execute(
            update(SupportCallLogModel)
            .where(SupportCallLogModel.id == call_id)
            .values(outcome=outcome, duration_s=duration_s, note=note, finished_at=finished_at)
            .execution_options(synchronize_session=False)
        )

    async def for_ticket(self, ticket_id: UUID, *, limit: int = 50) -> list[CallLog]:
        rows = (
            await self._session.execute(
                self._query()
                .where(SupportCallLogModel.ticket_id == ticket_id)
                .order_by(SupportCallLogModel.started_at.desc())
                .limit(limit)
            )
        ).all()
        return [self._to_call(row) for row in rows]
