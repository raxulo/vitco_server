"""
ExchangeWorker against the real test database (Plan 1.4, task 3).

Processors here are small test classes that write real `users` rows through
`JobContext.run_batch`, so batch atomicity, concurrency, cancel, heartbeat
and memory handling are observed in the database, not in mocks.
"""

from __future__ import annotations

import asyncio
import contextvars
from collections.abc import Callable
from datetime import timedelta
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.dataexchange.application.processor import JobContext, ProcessorResult
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.worker.exchange import ExchangeWorker, parent_alive

MB = 1024 * 1024


# =========================================================
# FIXTURES & HELPERS
# =========================================================

@pytest.fixture(autouse=True)
async def _empty_job_table(database: DatabaseManager):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


@pytest.fixture
def repository(database: DatabaseManager) -> ExcelJobRepository:
    return ExcelJobRepository(database)


@pytest.fixture
async def start_worker(database, repository, tmp_path):
    workers: list[tuple[ExchangeWorker, asyncio.Task]] = []

    def start(*processors, max_concurrent: int = 2, rss_reader: Callable[[], int] = lambda: 50 * MB) -> ExchangeWorker:
        worker = ExchangeWorker(
            database=database,
            repository=repository,
            storage=ExchangeStorage(tmp_path / "exchange", max_upload_bytes=10 * MB, min_free_bytes=0),
            max_concurrent=max_concurrent,
            poll_interval_ms=20,
            tx_budget_ms=250,
            max_batch_size=500,
            batch_pause_ms=0,
            max_memory_mb=1000,
            heartbeat_interval_s=0.2,
            rss_reader=rss_reader,
        )
        for processor in processors:
            worker.register(processor)
        task = asyncio.create_task(worker.run(), context=contextvars.Context())
        workers.append((worker, task))
        return worker

    yield start

    for worker, _ in workers:
        worker.stop()
    for _, task in workers:
        await asyncio.wait_for(task, timeout=10)


async def _queue(database, repository, user_id: UUID, kind: ExcelJobKind, total: int = 0) -> ExcelJob:
    job = ExcelJob(
        id=uuid4(), kind=kind, status=ExcelJobStatus.QUEUED, created_by=user_id,
        owner_role=int(Role.VLCC), total_rows=total, created_at=now_naive_ist(),
    )
    async with database.transaction():
        await repository.create(job)
    return job


async def _get(database, repository, job_id: UUID) -> ExcelJob:
    async with database.transaction():
        return await repository.get(job_id)


async def _wait_finished(database, repository, job_id: UUID, timeout: float = 15.0) -> ExcelJob:
    deadline = asyncio.get_running_loop().time() + timeout
    while True:
        job = await _get(database, repository, job_id)
        if job.status.is_finished:
            return job
        if asyncio.get_running_loop().time() > deadline:
            raise AssertionError(f"job {job_id} still {job.status.name} after {timeout}s")
        await asyncio.sleep(0.05)


async def _count_users(database, tag: str) -> int:
    async with database.transaction() as session:
        return int(await session.scalar(select(func.count(UserModel.id)).where(UserModel.email.like(f"{tag}-%"))))


class InsertUsers:
    """Inserts `batches` x `per_batch` real users, one batch per transaction."""

    def __init__(self, database, kind, *, batches=3, per_batch=10, fail_in_batch=None, delay=0.0, on_batch=None):
        self.database = database
        self.kind = kind
        self.batches = batches
        self.per_batch = per_batch
        self.fail_in_batch = fail_in_batch
        self.delay = delay
        self.on_batch = on_batch
        self.tag = f"w{uuid4().hex[:8]}"

    async def run(self, ctx: JobContext) -> ProcessorResult:
        ctx.total = self.batches * self.per_batch
        for number in range(1, self.batches + 1):
            async def write(number=number):
                session = self.database.session
                for i in range(self.per_batch):
                    uid = uuid4()
                    session.add(UserModel(
                        id=uid, name="Worker Test", email=f"{self.tag}-{number}-{i}-{ctx.job.id.hex[:8]}@w.test",
                        mobile=f"7{str(uid.int)[-9:]}", password_hash="x", role=Role.FARMER,
                    ))
                await session.flush()
                if number == self.fail_in_batch:
                    raise ValueError(f"boom in batch {number}")

            await ctx.run_batch(write)
            ctx.processed += self.per_batch
            ctx.inserted += self.per_batch
            if self.on_batch:
                await self.on_batch(number)
            if self.delay:
                await asyncio.sleep(self.delay)
            await ctx.checkpoint()
        return ProcessorResult(result_file="result.xlsx")


# =========================================================
# TESTS
# =========================================================

async def test_happy_path_completes_and_saves_counters(database, repository, user_factory, start_worker):
    processor = InsertUsers(database, ExcelJobKind.FARMER_IMPORT, batches=3, per_batch=10)
    start_worker(processor)
    user_id = await user_factory()

    job = await _queue(database, repository, user_id, ExcelJobKind.FARMER_IMPORT)
    done = await _wait_finished(database, repository, job.id)

    assert done.status is ExcelJobStatus.COMPLETED
    assert (done.processed_rows, done.inserted, done.total_rows) == (30, 30, 30)
    assert done.result_file == "result.xlsx"
    assert done.worker_pid is not None and done.finished_at is not None
    assert await _count_users(database, processor.tag) == 30


async def test_never_more_than_max_concurrent_jobs(database, repository, user_factory, start_worker):
    state = {"now": 0, "max": 0}

    class Slow:
        kind = ExcelJobKind.VLCC_EXPORT

        async def run(self, ctx: JobContext) -> ProcessorResult:
            state["now"] += 1
            state["max"] = max(state["max"], state["now"])
            await asyncio.sleep(0.4)
            state["now"] -= 1
            return ProcessorResult()

    start_worker(Slow(), max_concurrent=2)
    users = [await user_factory() for _ in range(3)]
    jobs = [await _queue(database, repository, user, ExcelJobKind.VLCC_EXPORT) for user in users]

    await asyncio.sleep(0.2)
    async with database.transaction():
        running_mid_way = await repository.count_running()
    results = [await _wait_finished(database, repository, job.id) for job in jobs]

    assert running_mid_way == 2
    assert state["max"] == 2
    assert all(result.status is ExcelJobStatus.COMPLETED for result in results)


async def test_failure_rolls_back_only_the_failing_batch(database, repository, user_factory, start_worker):
    processor = InsertUsers(database, ExcelJobKind.FARMER_IMPORT, batches=5, per_batch=10, fail_in_batch=3)
    start_worker(processor)
    user_id = await user_factory()

    job = await _queue(database, repository, user_id, ExcelJobKind.FARMER_IMPORT)
    done = await _wait_finished(database, repository, job.id)

    assert done.status is ExcelJobStatus.FAILED
    assert done.error_message == "boom in batch 3"
    assert done.processed_rows == 20                       # batches 1-2 were counted
    assert await _count_users(database, processor.tag) == 20
    async with database.transaction() as session:
        batch_three = await session.scalar(
            select(func.count(UserModel.id)).where(UserModel.email.like(f"{processor.tag}-3-%"))
        )
    assert batch_three == 0


async def test_cancel_stops_at_next_checkpoint(database, repository, user_factory, start_worker):
    first_batch = asyncio.Event()

    async def on_batch(number):
        if number == 1:
            first_batch.set()

    processor = InsertUsers(database, ExcelJobKind.FARMER_IMPORT, batches=200, per_batch=5, delay=0.02, on_batch=on_batch)
    start_worker(processor)
    user_id = await user_factory()
    job = await _queue(database, repository, user_id, ExcelJobKind.FARMER_IMPORT)

    await asyncio.wait_for(first_batch.wait(), timeout=10)
    async with database.transaction():
        await repository.request_cancel(job.id)
    done = await _wait_finished(database, repository, job.id)

    assert done.status is ExcelJobStatus.CANCELLED
    assert done.error_message == "Cancelled by the user"
    assert 0 < done.processed_rows < 1000
    assert await _count_users(database, processor.tag) == done.processed_rows


async def test_heartbeat_advances_while_a_job_runs(database, repository, user_factory, start_worker):
    release = asyncio.Event()

    class Quiet:
        kind = ExcelJobKind.PRODATA_EXPORT

        async def run(self, ctx: JobContext) -> ProcessorResult:
            await release.wait()                            # long step without checkpoints
            return ProcessorResult()

    start_worker(Quiet())
    user_id = await user_factory()
    job = await _queue(database, repository, user_id, ExcelJobKind.PRODATA_EXPORT)

    await asyncio.sleep(0.15)
    first = (await _get(database, repository, job.id)).heartbeat_at
    await asyncio.sleep(0.6)
    later = (await _get(database, repository, job.id)).heartbeat_at
    release.set()
    await _wait_finished(database, repository, job.id)

    assert first is not None and later is not None
    assert later - first >= timedelta(milliseconds=200)


async def test_unknown_kind_fails_with_clear_message(database, repository, user_factory, start_worker):
    start_worker()                                          # no processors registered
    user_id = await user_factory()

    job = await _queue(database, repository, user_id, ExcelJobKind.VLCC_IMPORT)
    done = await _wait_finished(database, repository, job.id)

    assert done.status is ExcelJobStatus.FAILED
    assert done.error_message == "No processor for VLCC_IMPORT"


async def test_memory_limit_fails_the_job_and_worker_keeps_running(database, repository, user_factory, start_worker):
    memory = {"rss": 5000 * MB}                             # above the 1000 MB hard limit
    processor = InsertUsers(database, ExcelJobKind.FARMER_IMPORT, batches=3, per_batch=5)
    start_worker(processor, rss_reader=lambda: memory["rss"])
    user_id = await user_factory()

    first = await _queue(database, repository, user_id, ExcelJobKind.FARMER_IMPORT)
    failed = await _wait_finished(database, repository, first.id)
    memory["rss"] = 100 * MB
    second = await _queue(database, repository, user_id, ExcelJobKind.FARMER_IMPORT)
    completed = await _wait_finished(database, repository, second.id)

    assert failed.status is ExcelJobStatus.FAILED
    assert failed.error_message == "Worker memory limit reached"
    assert failed.processed_rows == 5                       # stopped at the first checkpoint
    assert completed.status is ExcelJobStatus.COMPLETED


async def test_stop_interrupts_running_jobs_cleanly(database, repository, user_factory, start_worker):
    processor = InsertUsers(database, ExcelJobKind.FARMER_IMPORT, batches=500, per_batch=2, delay=0.01)
    worker = start_worker(processor)
    user_id = await user_factory()
    job = await _queue(database, repository, user_id, ExcelJobKind.FARMER_IMPORT)

    await asyncio.sleep(0.5)
    worker.stop()
    done = await _wait_finished(database, repository, job.id)

    assert done.status is ExcelJobStatus.FAILED
    assert done.error_message == "Interrupted by server restart"
    assert await _count_users(database, processor.tag) == done.processed_rows


def test_parent_alive_for_this_process_and_not_for_a_dead_pid():
    import os
    import subprocess
    import sys

    assert parent_alive(os.getppid()) is True
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()

    assert parent_alive(child.pid) is False
