"""
Exchange Processor Protocol & Job Context

Every entity adapter (farmers, VLCCs, prodata rows) implements
`ExchangeProcessor`. It does its work through `JobContext`:

- `run_batch(fn)`  — one short top-level transaction, timed for the adaptive batcher;
- `checkpoint()`   — between batches: progress + heartbeat, cancel / memory / disk
                     checks, then a short pause that lets API writers take the lock.

CPU-heavy steps (xlsx parsing / writing, password hashing) belong in
`asyncio.to_thread` so heartbeats keep flowing.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, TypeVar
from uuid import UUID

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.batching import AdaptiveBatcher, MemoryGuard
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.modules.dataexchange.domain.irepository import IExcelJobRepository

T = TypeVar("T")

_REPORT_EVERY_S = 1.0
_DISK_CHECK_EVERY_ROWS = 10_000


class JobCancelled(Exception):
    """The user cancelled the job."""


class JobInterrupted(Exception):
    """The worker is stopping (server shutdown / restart)."""


class DiskGuard(Protocol):

    def ensure_free_space(self, expected_bytes: int) -> None: ...


@dataclass(slots=True, kw_only=True)
class ProcessorResult:

    result_file: str | None = None
    report_file: str | None = None


class JobContext:

    __slots__ = (
        "job",
        "owner",
        "job_dir",
        "batcher",
        "processed",
        "total",
        "inserted",
        "updated",
        "discarded",
        "_database",
        "_repository",
        "_disk",
        "_memory",
        "_pause_s",
        "_last_report",
        "_last_disk_check",
        "_interrupt_reason",
    )

    def __init__(
        self,
        *,
        job: ExcelJob,
        job_dir: Path,
        database: DatabaseManager,
        repository: IExcelJobRepository,
        disk: DiskGuard,
        batcher: AdaptiveBatcher,
        memory: MemoryGuard,
        pause_ms: int,
    ) -> None:
        self.job = job
        # Plain uuid.UUID ids: on PostgreSQL the job row hands back asyncpg's own UUID class,
        # which SQLAlchemy cannot type when it is used as a bare query parameter
        self.owner = CurrentUser(
            id=UUID(str(job.created_by)),
            role=Role(job.owner_role),
            own_id=UUID(str(job.owner_own_id)) if job.owner_own_id else None,
        )
        self.job_dir = job_dir
        self.batcher = batcher
        self.processed = 0
        self.total = job.total_rows
        self.inserted = 0
        self.updated = 0
        self.discarded = 0
        self._database = database
        self._repository = repository
        self._disk = disk
        self._memory = memory
        self._pause_s = pause_ms / 1000
        self._last_report = 0.0
        self._last_disk_check = 0
        self._interrupt_reason: str | None = None

    # ---------------------------------------------------------

    async def run_batch(self, fn: Callable[[], Awaitable[T]]) -> T:
        """Run `fn` in one top-level transaction; nested `transaction()` calls inside it are savepoints."""
        started = time.perf_counter()
        async with self._database.transaction():
            result = await fn()
        self.batcher.record((time.perf_counter() - started) * 1000)
        return result

    async def checkpoint(self) -> None:
        """Call between batches."""
        if self._interrupt_reason:
            raise JobInterrupted(self._interrupt_reason)

        now = time.monotonic()
        if now - self._last_report >= _REPORT_EVERY_S:
            self._last_report = now
            await self.report()
            async with self._database.transaction():
                cancelled = await self._repository.is_cancel_requested(self.job.id)
            if cancelled:
                raise JobCancelled()

        self._memory.check(self.batcher)

        if self.processed - self._last_disk_check >= _DISK_CHECK_EVERY_ROWS:
            self._last_disk_check = self.processed
            await asyncio.to_thread(self._disk.ensure_free_space, 0)

        await asyncio.sleep(self._pause_s)

    async def report(self) -> None:
        """Persist the counters (also refreshes the heartbeat)."""
        async with self._database.transaction():
            await self._repository.save_progress(
                self.job.id,
                processed_rows=self.processed,
                total_rows=max(self.total, self.processed),
                inserted=self.inserted,
                updated=self.updated,
                discarded=self.discarded,
                now=now_naive_ist(),
            )

    def interrupt(self, reason: str) -> None:
        """Ask the job to stop at its next checkpoint (worker shutdown)."""
        self._interrupt_reason = reason


class ExchangeProcessor(Protocol):

    kind: ExcelJobKind

    async def run(self, ctx: JobContext) -> ProcessorResult: ...
