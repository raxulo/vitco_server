from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus
from app.modules.dataexchange.domain.irepository import IExcelJobRepository
from app.modules.dataexchange.infrastructure.mapper import ExcelJobMapper
from app.modules.dataexchange.infrastructure.models import ExcelJobModel

_ACTIVE = (ExcelJobStatus.QUEUED, ExcelJobStatus.RUNNING)


class ExcelJobRepository(IExcelJobRepository):
    """
    Persistence for Excel jobs. Every write is a single statement; the caller
    owns the transaction (`async with database.transaction()`).
    """

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # CREATE / READ
    # =========================================================

    async def create(self, job: ExcelJob) -> None:
        self._session.add(ExcelJobMapper.to_model(job))
        await self._session.flush()

    async def get(self, job_id: UUID) -> ExcelJob | None:
        model = await self._session.get(ExcelJobModel, job_id, populate_existing=True)
        return ExcelJobMapper.to_entity(model) if model else None

    async def list_for_user(
        self,
        user_id: UUID,
        *,
        kind: ExcelJobKind | None = None,
        status: ExcelJobStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ExcelJob]:
        stmt = (
            self._filtered(select(ExcelJobModel), user_id, kind, status)
            .order_by(ExcelJobModel.created_at.desc(), ExcelJobModel.id.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [ExcelJobMapper.to_entity(model) for model in result]

    async def count_for_user(
        self,
        user_id: UUID,
        *,
        kind: ExcelJobKind | None = None,
        status: ExcelJobStatus | None = None,
    ) -> int:
        stmt = self._filtered(select(func.count(ExcelJobModel.id)), user_id, kind, status)
        return int(await self._session.scalar(stmt) or 0)

    async def find_active(self, user_id: UUID, kind: ExcelJobKind) -> ExcelJob | None:
        stmt = (
            select(ExcelJobModel)
            .where(
                ExcelJobModel.created_by == user_id,
                ExcelJobModel.kind == kind,
                ExcelJobModel.status.in_(_ACTIVE),
            )
            .order_by(ExcelJobModel.created_at)
            .limit(1)
        )
        model = await self._session.scalar(stmt)
        return ExcelJobMapper.to_entity(model) if model else None

    async def count_running(self) -> int:
        return await self._count_status(ExcelJobStatus.RUNNING)

    async def list_running(self) -> list[ExcelJob]:
        stmt = select(ExcelJobModel).where(ExcelJobModel.status == ExcelJobStatus.RUNNING)
        result = await self._session.scalars(stmt)
        return [ExcelJobMapper.to_entity(model) for model in result]

    async def count_queued(self) -> int:
        return await self._count_status(ExcelJobStatus.QUEUED)

    # =========================================================
    # WORKER LIFECYCLE
    # =========================================================

    async def claim_next(self, worker_pid: int, now: datetime) -> ExcelJob | None:
        # One atomic statement: the second `status == QUEUED` guard makes a
        # caller that lost the race update nothing, so a job never runs twice.
        oldest_queued = (
            select(ExcelJobModel.id)
            .where(ExcelJobModel.status == ExcelJobStatus.QUEUED)
            .order_by(ExcelJobModel.created_at, ExcelJobModel.id)
            .limit(1)
            .scalar_subquery()
        )
        stmt = (
            update(ExcelJobModel)
            .where(
                ExcelJobModel.id == oldest_queued,
                ExcelJobModel.status == ExcelJobStatus.QUEUED,
            )
            .values(
                status=ExcelJobStatus.RUNNING,
                worker_pid=worker_pid,
                started_at=now,
                heartbeat_at=now,
                updated_at=now,
            )
            .returning(ExcelJobModel)
            .execution_options(synchronize_session=False)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return ExcelJobMapper.to_entity(model) if model else None

    async def heartbeat(self, job_id: UUID, now: datetime) -> None:
        await self._update(job_id, heartbeat_at=now)

    async def save_progress(
        self,
        job_id: UUID,
        *,
        processed_rows: int,
        total_rows: int,
        inserted: int,
        updated: int,
        discarded: int,
        now: datetime,
    ) -> None:
        await self._update(
            job_id,
            processed_rows=processed_rows,
            total_rows=total_rows,
            inserted=inserted,
            updated=updated,
            discarded=discarded,
            heartbeat_at=now,
            updated_at=now,
        )

    async def mark_finished(
        self,
        job_id: UUID,
        *,
        status: ExcelJobStatus,
        finished_at: datetime,
        error_message: str | None = None,
        result_file: str | None = None,
        report_file: str | None = None,
    ) -> None:
        await self._update(
            job_id,
            status=status,
            finished_at=finished_at,
            updated_at=finished_at,
            error_message=error_message[:500] if error_message else None,
            result_file=result_file,
            report_file=report_file,
        )

    async def request_cancel(self, job_id: UUID) -> None:
        await self._session.execute(
            update(ExcelJobModel)
            .where(ExcelJobModel.id == job_id, ExcelJobModel.status.in_(_ACTIVE))
            .values(cancel_requested=True)
            .execution_options(synchronize_session=False)
        )

    async def is_cancel_requested(self, job_id: UUID) -> bool:
        stmt = select(ExcelJobModel.cancel_requested).where(ExcelJobModel.id == job_id)
        return bool(await self._session.scalar(stmt))

    # =========================================================
    # RECOVERY / CLEANUP
    # =========================================================

    async def fail_stale(self, before: datetime, now: datetime) -> int:
        result = await self._session.execute(
            update(ExcelJobModel)
            .where(
                ExcelJobModel.status == ExcelJobStatus.RUNNING,
                ExcelJobModel.heartbeat_at < before,
            )
            .values(
                status=ExcelJobStatus.FAILED,
                error_message="Worker stopped responding",
                finished_at=now,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0

    async def fail_interrupted(self, now: datetime) -> int:
        result = await self._session.execute(
            update(ExcelJobModel)
            .where(ExcelJobModel.status.in_(_ACTIVE))
            .values(
                status=ExcelJobStatus.FAILED,
                error_message="Interrupted by server restart",
                finished_at=now,
                updated_at=now,
            )
            .execution_options(synchronize_session=False)
        )
        return result.rowcount or 0

    async def list_expired(self, before: datetime) -> list[ExcelJob]:
        stmt = (
            select(ExcelJobModel)
            .where(
                ExcelJobModel.status.not_in(_ACTIVE),
                ExcelJobModel.finished_at < before,
            )
            .order_by(ExcelJobModel.finished_at)
        )
        result = await self._session.scalars(stmt)
        return [ExcelJobMapper.to_entity(model) for model in result]

    async def delete(self, job_id: UUID) -> None:
        await self._session.execute(
            delete(ExcelJobModel)
            .where(ExcelJobModel.id == job_id)
            .execution_options(synchronize_session=False)
        )

    # =========================================================
    # HELPERS
    # =========================================================

    async def _update(self, job_id: UUID, **values) -> None:
        await self._session.execute(
            update(ExcelJobModel)
            .where(ExcelJobModel.id == job_id)
            .values(**values)
            .execution_options(synchronize_session=False)
        )

    async def _count_status(self, status: ExcelJobStatus) -> int:
        stmt = select(func.count(ExcelJobModel.id)).where(ExcelJobModel.status == status)
        return int(await self._session.scalar(stmt) or 0)

    @staticmethod
    def _filtered(stmt, user_id: UUID, kind: ExcelJobKind | None, status: ExcelJobStatus | None):
        stmt = stmt.where(ExcelJobModel.created_by == user_id)
        if kind is not None:
            stmt = stmt.where(ExcelJobModel.kind == kind)
        if status is not None:
            stmt = stmt.where(ExcelJobModel.status == status)
        return stmt
