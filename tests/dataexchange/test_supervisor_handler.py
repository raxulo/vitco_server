"""
WorkerSupervisor with a real worker process, and ExcelJobHandler (Plan 1.5, task 3).

The supervisor tests start `tests.dataexchange.worker_fixture` — the real worker
plus test processors — as a child process sharing the test database, then
kill it to prove crash isolation and recovery.
"""

from __future__ import annotations

import asyncio
import os
import signal
import subprocess
import sys
import time
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, select

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.dataexchange.application.command import (
    CancelExcelJobCommand,
    GetExcelJobFileQuery,
    GetExcelJobQuery,
    ListExcelJobsQuery,
    SubmitExportCommand,
    SubmitImportCommand,
)
from app.modules.dataexchange.application.handler import ExcelJobHandler
from app.modules.dataexchange.domain.columns import ColumnKind, ColumnSpec, Section, SheetSpec
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus
from app.modules.dataexchange.domain.exceptions import (
    ExcelJobCapacityException,
    ExcelJobConflictException,
    ExcelJobFileNotReadyException,
    ExcelJobFinishedException,
    ExcelJobNotFoundException,
    InvalidExcelFileException,
)
from app.modules.dataexchange.infrastructure.file_guard import FileGuard
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.worker.exchange import parent_alive
from app.worker.supervisor import WorkerSupervisor

MB = 1024 * 1024
FIXTURE_WORKER = (sys.executable, "-m", "tests.dataexchange.worker_fixture")


# =========================================================
# FIXTURES & HELPERS
# =========================================================

@pytest.fixture(autouse=True)
async def _empty_job_table(database: DatabaseManager):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


@pytest.fixture
def repository(database) -> ExcelJobRepository:
    return ExcelJobRepository(database)


@pytest.fixture
def storage(test_root: Path) -> ExchangeStorage:
    return ExchangeStorage(Path(os.environ["EXCHANGE_PATH"]), max_upload_bytes=10 * MB, min_free_bytes=0)


@pytest.fixture
def handler(database, repository, storage) -> ExcelJobHandler:
    return ExcelJobHandler(
        database=database, repository=repository, storage=storage,
        guard=FileGuard(max_uncompressed_bytes=100 * MB), max_queued=20,
    )


@pytest.fixture
async def supervisor(database, repository, storage, test_root):
    instance = WorkerSupervisor(
        database=database, repository=repository, storage=storage, enabled=True,
        log_dir=test_root / "logs", heartbeat_timeout_s=3, file_ttl_hours=24,
        watchdog_interval_s=0.5, command=FIXTURE_WORKER, cwd=Path.cwd(),
    )
    yield instance
    await instance.stop()


async def _owner(user_factory, role: Role = Role.VLCC) -> CurrentUser:
    return CurrentUser(id=await user_factory(role), role=role)


async def _queue(database, repository, user_id: UUID, kind: ExcelJobKind, **fields) -> ExcelJob:
    job = ExcelJob(
        id=uuid4(), kind=kind, status=fields.pop("status", ExcelJobStatus.QUEUED), created_by=user_id,
        owner_role=int(Role.VLCC), created_at=now_naive_ist(), **fields,
    )
    async with database.transaction():
        await repository.create(job)
    return job


async def _get(database, repository, job_id) -> ExcelJob:
    async with database.transaction():
        return await repository.get(job_id)


async def _wait(database, repository, job_id, predicate, timeout: float = 30.0) -> ExcelJob:
    deadline = time.monotonic() + timeout
    while True:
        job = await _get(database, repository, job_id)
        if predicate(job):
            return job
        if time.monotonic() > deadline:
            raise AssertionError(f"job {job_id}: condition not met after {timeout}s (status {job.status.name})")
        await asyncio.sleep(0.1)


async def _wait_for_pid(supervisor: WorkerSupervisor, not_pid: int | None = None, timeout: float = 30.0) -> int:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        pid = supervisor.worker_pid
        if pid is not None and pid != not_pid:
            return pid
        await asyncio.sleep(0.1)
    raise AssertionError("worker process did not (re)start")


def _hard_kill(pid: int) -> None:
    # Windows: TerminateProcess; POSIX: SIGKILL — no chance to clean up, like an OOM kill
    os.kill(pid, signal.SIGTERM if sys.platform == "win32" else signal.SIGKILL)


def _xlsx(path: Path) -> Path:
    sheet = SheetSpec(name="Farmers", key_column="code", columns=(
        ColumnSpec(key="code", header="Code", section=Section.ENTITY, kind=ColumnKind.CODE, required=True),
    ))
    writer = XlsxSheetWriter(path, sheet)
    writer.write_rows([["F1"]])
    writer.close()
    return path


# =========================================================
# SUPERVISOR + REAL WORKER PROCESS
# =========================================================

async def test_supervisor_runs_a_real_worker_that_completes_jobs(database, repository, user_factory, supervisor):
    await supervisor.start()
    pid = await _wait_for_pid(supervisor)
    user_id = await user_factory()

    job = await _queue(database, repository, user_id, ExcelJobKind.VLCC_EXPORT)
    done = await _wait(database, repository, job.id, lambda j: j.status.is_finished)

    assert done.status is ExcelJobStatus.COMPLETED
    # Ran in the child, not in this process. On Windows a venv python.exe is a launcher
    # that runs the real interpreter as its own child, so the two PIDs may differ.
    assert done.worker_pid not in (None, os.getpid())
    assert pid != os.getpid()

    await supervisor.stop()

    assert supervisor.worker_pid is None
    # The process that actually ran the job must be gone too (no orphan worker left behind)
    deadline = time.monotonic() + 10
    while parent_alive(done.worker_pid) and time.monotonic() < deadline:
        await asyncio.sleep(0.2)
    assert not parent_alive(done.worker_pid)


async def test_killed_worker_is_restarted_and_its_job_fails_cleanly(
    database, repository, handler, user_factory, supervisor,
):
    await supervisor.start()
    first_pid = await _wait_for_pid(supervisor)
    owner = await _owner(user_factory)
    job = await _queue(database, repository, owner.id, ExcelJobKind.FARMER_IMPORT)
    await _wait(database, repository, job.id, lambda j: j.processed_rows >= 20)

    _hard_kill(first_pid)

    # The API side keeps answering while the worker is dead
    started = time.monotonic()
    seen = await handler.get(GetExcelJobQuery(id=job.id, owner=owner))
    assert seen.status is ExcelJobStatus.RUNNING
    assert time.monotonic() - started < 1.0

    second_pid = await _wait_for_pid(supervisor, not_pid=first_pid)
    failed = await _wait(database, repository, job.id, lambda j: j.status.is_finished)

    assert second_pid != first_pid
    assert failed.status is ExcelJobStatus.FAILED
    assert failed.error_message == "Worker stopped responding"
    async with database.transaction() as session:
        committed = int(await session.scalar(
            select(func.count(UserModel.id)).where(UserModel.email.like(f"sv-{job.id.hex}-%"))
        ))
    assert committed >= 20
    assert committed % 5 == 0                                  # whole batches only, never half of one
    assert committed >= failed.processed_rows                  # progress never claims more than was saved


async def test_worker_exits_when_its_parent_process_is_gone(test_root):
    parent = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(1)"])
    worker = subprocess.Popen(
        [sys.executable, "-m", "app.worker.exchange", "--parent-pid", str(parent.pid)],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    parent.wait()
    try:
        code = await asyncio.to_thread(worker.wait, 15)
    finally:
        if worker.poll() is None:
            worker.kill()

    assert code == 0


async def test_recover_fails_running_jobs_of_dead_workers_only(database, repository, user_factory, supervisor):
    user_id = await user_factory()
    dead = subprocess.Popen([sys.executable, "-c", "pass"])
    dead.wait()
    orphan = await _queue(database, repository, user_id, ExcelJobKind.FARMER_IMPORT,
                          status=ExcelJobStatus.RUNNING, worker_pid=dead.pid)
    alive = await _queue(database, repository, user_id, ExcelJobKind.VLCC_IMPORT,
                         status=ExcelJobStatus.RUNNING, worker_pid=os.getpid())
    queued = await _queue(database, repository, user_id, ExcelJobKind.PRODATA_IMPORT)

    assert await supervisor.recover() == 1

    assert (await _get(database, repository, orphan.id)).status is ExcelJobStatus.FAILED
    assert (await _get(database, repository, alive.id)).status is ExcelJobStatus.RUNNING
    assert (await _get(database, repository, queued.id)).status is ExcelJobStatus.QUEUED


async def test_cleanup_removes_only_expired_jobs_and_their_files(database, repository, storage, user_factory, supervisor):
    user_id = await user_factory()
    now = now_naive_ist()
    old = await _queue(database, repository, user_id, ExcelJobKind.FARMER_EXPORT,
                       status=ExcelJobStatus.COMPLETED, finished_at=now - timedelta(hours=25))
    recent = await _queue(database, repository, user_id, ExcelJobKind.VLCC_EXPORT,
                          status=ExcelJobStatus.COMPLETED, finished_at=now - timedelta(hours=1))
    for job in (old, recent):
        (storage.job_dir(job.id) / "result.xlsx").write_bytes(b"x")

    assert await supervisor.cleanup_once() == 1

    assert await _get(database, repository, old.id) is None
    assert not (storage.root / "jobs" / str(old.id)).exists()
    assert await _get(database, repository, recent.id) is not None
    assert (storage.root / "jobs" / str(recent.id) / "result.xlsx").exists()


# =========================================================
# HANDLER
# =========================================================

async def test_submit_export_queues_a_job_and_never_runs_it(database, repository, handler, user_factory):
    owner = await _owner(user_factory)

    dto = await handler.submit_export(SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owner, target_id=uuid4()))
    stored = await _get(database, repository, dto.id)

    assert dto.status is ExcelJobStatus.QUEUED and dto.poll_after_ms == 1000
    assert stored.status is ExcelJobStatus.QUEUED and stored.worker_pid is None
    assert stored.owner_role == int(Role.VLCC)


async def test_same_user_and_kind_twice_is_409(handler, user_factory):
    owner = await _owner(user_factory)
    await handler.submit_export(SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owner))

    with pytest.raises(ExcelJobConflictException) as error:
        await handler.submit_export(SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owner))
    other_kind = await handler.submit_export(SubmitExportCommand(kind=ExcelJobKind.VLCC_EXPORT, owner=owner))

    assert error.value.status_code == 409 and error.value.retry_after == 30
    assert other_kind.status is ExcelJobStatus.QUEUED


async def test_full_queue_is_429_with_retry_after(database, repository, storage, user_factory):
    small = ExcelJobHandler(database=database, repository=repository, storage=storage,
                            guard=FileGuard(max_uncompressed_bytes=MB), max_queued=2)
    owners = [await _owner(user_factory) for _ in range(3)]
    for owner in owners[:2]:
        await small.submit_export(SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owner))

    with pytest.raises(ExcelJobCapacityException) as error:
        await small.submit_export(SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owners[2]))

    assert error.value.status_code == 429 and error.value.retry_after == 30


async def test_other_users_jobs_are_not_found(handler, user_factory):
    owner_a = await _owner(user_factory)
    owner_b = await _owner(user_factory)
    super_admin = await _owner(user_factory, Role.SUPER_ADMIN)
    dto = await handler.submit_export(SubmitExportCommand(kind=ExcelJobKind.VLCC_EXPORT, owner=owner_a))

    with pytest.raises(ExcelJobNotFoundException):
        await handler.get(GetExcelJobQuery(id=dto.id, owner=owner_b))
    with pytest.raises(ExcelJobNotFoundException):
        await handler.cancel(CancelExcelJobCommand(id=dto.id, owner=owner_b))
    assert (await handler.get(GetExcelJobQuery(id=dto.id, owner=super_admin))).id == dto.id
    assert [job.id for job in await handler.list(ListExcelJobsQuery(owner=owner_b))] == []


async def test_cancel_queued_job_finishes_it_and_cancel_again_is_409(handler, user_factory):
    owner = await _owner(user_factory)
    dto = await handler.submit_export(SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owner))

    cancelled = await handler.cancel(CancelExcelJobCommand(id=dto.id, owner=owner))
    with pytest.raises(ExcelJobFinishedException):
        await handler.cancel(CancelExcelJobCommand(id=dto.id, owner=owner))

    assert cancelled.status is ExcelJobStatus.CANCELLED
    assert cancelled.poll_after_ms is None


async def test_file_path_requires_a_finished_job_with_a_file(database, repository, storage, handler, user_factory):
    owner = await _owner(user_factory)
    queued = await handler.submit_export(SubmitExportCommand(kind=ExcelJobKind.FARMER_EXPORT, owner=owner))
    done = await _queue(database, repository, owner.id, ExcelJobKind.VLCC_EXPORT,
                        status=ExcelJobStatus.COMPLETED, result_file="result.xlsx", finished_at=now_naive_ist())
    (storage.job_dir(done.id) / "result.xlsx").write_bytes(b"PK\x03\x04data")

    with pytest.raises(ExcelJobFileNotReadyException):
        await handler.file_path(GetExcelJobFileQuery(id=queued.id, owner=owner))
    path, job = await handler.file_path(GetExcelJobFileQuery(id=done.id, owner=owner))

    assert path.read_bytes() == b"PK\x03\x04data" and job.id == done.id


async def test_submit_import_moves_a_valid_file_into_the_job_folder(storage, handler, user_factory, tmp_path):
    owner = await _owner(user_factory)
    upload = _xlsx(tmp_path / "upload.xlsx")

    dto = await handler.submit_import(SubmitImportCommand(kind=ExcelJobKind.FARMER_IMPORT, owner=owner, source=upload))

    assert not upload.exists()
    assert (storage.root / "jobs" / str(dto.id) / "source.xlsx").is_file()
    assert dto.status is ExcelJobStatus.QUEUED


async def test_submit_import_rejects_a_hostile_file_and_leaves_nothing(database, repository, storage, handler, user_factory, tmp_path):
    owner = await _owner(user_factory)
    fake = tmp_path / "fake.xlsx"
    fake.write_text("not a workbook")
    jobs_root = storage.root / "jobs"
    before = set(jobs_root.iterdir()) if jobs_root.exists() else set()

    with pytest.raises(InvalidExcelFileException):
        await handler.submit_import(SubmitImportCommand(kind=ExcelJobKind.FARMER_IMPORT, owner=owner, source=fake))

    async with database.transaction():
        assert await repository.count_for_user(owner.id) == 0
    after = set(jobs_root.iterdir()) if jobs_root.exists() else set()
    assert after == before                                   # no job folder left behind
