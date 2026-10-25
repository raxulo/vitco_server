"""
Excel Job Handler

API-side use cases for import / export jobs. It only validates, stores the
file and queues a job row — the exchange worker process does the work
(DECISION-008). When the system is busy it answers at once with 429 / 409
and a Retry-After, never by slowing down (NFR-04).

Python 3.13+
"""

from __future__ import annotations

import asyncio
import os
from pathlib import Path
from uuid import uuid4

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.command import (
    CancelExcelJobCommand,
    GetExcelJobFileQuery,
    GetExcelJobQuery,
    ListExcelJobsQuery,
    SubmitExportCommand,
    SubmitImportCommand,
)
from app.modules.dataexchange.application.dto import ExcelJobDto, job_file_name
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus
from app.modules.dataexchange.domain.exceptions import (
    ExcelJobCapacityException,
    ExcelJobConflictException,
    ExcelJobFileNotReadyException,
    ExcelJobFinishedException,
    ExcelJobNotFoundException,
)
from app.modules.dataexchange.domain.irepository import IExcelJobRepository
from app.modules.dataexchange.infrastructure.file_guard import FileGuard
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage

_SOURCE_FILE = "source.xlsx"


class ExcelJobHandler:

    __slots__ = ("_database", "_repository", "_storage", "_guard", "_max_queued")

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: IExcelJobRepository,
        storage: ExchangeStorage,
        guard: FileGuard,
        max_queued: int,
    ) -> None:
        self._database = database
        self._repository = repository
        self._storage = storage
        self._guard = guard
        self._max_queued = max_queued

    # =========================================================
    # SUBMIT
    # =========================================================

    async def submit_export(self, command: SubmitExportCommand) -> ExcelJobDto:
        await self._ensure_capacity(command.owner, command.kind)
        await asyncio.to_thread(self._storage.ensure_free_space, 0)
        job = self._new_job(command.kind, command.owner, command.target_id)
        await self._insert(job)
        return ExcelJobDto.from_job(job)

    async def submit_import(self, command: SubmitImportCommand) -> ExcelJobDto:
        await self._ensure_capacity(command.owner, command.kind)
        size = command.source.stat().st_size
        await asyncio.to_thread(self._storage.ensure_free_space, size * 2)

        job = self._new_job(command.kind, command.owner, command.target_id)
        job.mode = command.mode
        job.dry_run = command.dry_run
        job.source_file = _SOURCE_FILE

        job_dir = self._storage.job_dir(job.id)
        try:
            source = self._storage.path(job_dir, _SOURCE_FILE)
            await asyncio.to_thread(os.replace, command.source, source)
            await asyncio.to_thread(self._guard.inspect, source)
            await self._insert(job)
        except BaseException:
            await asyncio.to_thread(self._storage.delete_dir, job_dir)
            raise
        return ExcelJobDto.from_job(job)

    # =========================================================
    # QUERY
    # =========================================================

    async def get(self, query: GetExcelJobQuery) -> ExcelJobDto:
        return ExcelJobDto.from_job(await self._owned(query.id, query.owner))

    async def list(self, query: ListExcelJobsQuery) -> list[ExcelJobDto]:
        async with self._database.transaction():
            jobs = await self._repository.list_for_user(
                query.owner.id, kind=query.kind, status=query.status, limit=query.limit, offset=query.offset,
            )
        return [ExcelJobDto.from_job(job) for job in jobs]

    async def count(self, query: ListExcelJobsQuery) -> int:
        async with self._database.transaction():
            return await self._repository.count_for_user(query.owner.id, kind=query.kind, status=query.status)

    async def file_path(self, query: GetExcelJobFileQuery) -> tuple[Path, ExcelJob]:
        job = await self._owned(query.id, query.owner)
        name = job_file_name(job)
        if name is None:
            raise ExcelJobFileNotReadyException()
        path = self._storage.path(self._storage.root / "jobs" / str(job.id), name)
        if not path.is_file():
            raise ExcelJobFileNotReadyException("The file for this job is no longer available.")
        return path, job

    # =========================================================
    # CANCEL
    # =========================================================

    async def cancel(self, command: CancelExcelJobCommand) -> ExcelJobDto:
        job = await self._owned(command.id, command.owner)
        if job.status.is_finished:
            raise ExcelJobFinishedException()
        async with self._database.transaction():
            await self._repository.request_cancel(job.id)
            if job.status is ExcelJobStatus.QUEUED:
                # Nobody is running it yet: finish it here so it never starts
                await self._repository.mark_finished(
                    job.id, status=ExcelJobStatus.CANCELLED, finished_at=now_naive_ist(),
                    error_message="Cancelled by the user",
                )
        return await self.get(GetExcelJobQuery(id=job.id, owner=command.owner))

    # =========================================================
    # HELPERS
    # =========================================================

    async def _ensure_capacity(self, owner: CurrentUser, kind: ExcelJobKind) -> None:
        async with self._database.transaction():
            active = await self._repository.find_active(owner.id, kind)
            if active is not None:
                # The app can resume polling the running job instead of starting a new one
                raise ExcelJobConflictException(details={"job_id": str(active.id)})
            if await self._repository.count_queued() >= self._max_queued:
                raise ExcelJobCapacityException()

    async def _owned(self, job_id, owner: CurrentUser) -> ExcelJob:
        async with self._database.transaction():
            job = await self._repository.get(job_id)
        # Another user's job is reported as missing (404, never 403) so ids cannot be probed
        if job is None or (job.created_by != owner.id and owner.role_type is not Role.SUPER_ADMIN):
            raise ExcelJobNotFoundException()
        return job

    async def _insert(self, job: ExcelJob) -> None:
        async with self._database.transaction():
            await self._repository.create(job)

    @staticmethod
    def _new_job(kind: ExcelJobKind, owner: CurrentUser, target_id) -> ExcelJob:
        now = now_naive_ist()
        return ExcelJob(
            id=uuid4(),
            kind=kind,
            status=ExcelJobStatus.QUEUED,
            created_by=owner.id,
            owner_role=int(owner.role_type),
            owner_own_id=owner.own_id,
            target_id=target_id,
            created_at=now,
            updated_at=now,
        )
