"""
ExcelJobRepository against a real SQLite database (Plan 1.1).
"""

from __future__ import annotations

import asyncio
import contextvars
from datetime import timedelta
from uuid import UUID, uuid4

import pytest

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus, ImportMode
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository


@pytest.fixture(scope="module")
def repository(database: DatabaseManager) -> ExcelJobRepository:
    return ExcelJobRepository(database)


@pytest.fixture(autouse=True)
async def _empty_job_table(database: DatabaseManager):
    """Each test starts with no jobs, so claim / count assertions are exact."""
    from sqlalchemy import delete

    from app.modules.dataexchange.infrastructure.models import ExcelJobModel

    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


async def _add_job(
    database: DatabaseManager,
    repository: ExcelJobRepository,
    user_id: UUID,
    *,
    kind: ExcelJobKind = ExcelJobKind.FARMER_IMPORT,
    status: ExcelJobStatus = ExcelJobStatus.QUEUED,
    age_minutes: int = 0,
    **fields,
) -> ExcelJob:
    created = now_naive_ist() - timedelta(minutes=age_minutes)
    job = ExcelJob(
        id=uuid4(),
        kind=kind,
        status=status,
        created_by=user_id,
        owner_role=int(Role.VLCC),
        created_at=created,
        updated_at=created,
        **fields,
    )
    async with database.transaction():
        await repository.create(job)
    return job


async def _in_new_transaction(database: DatabaseManager, fn):
    async with database.transaction():
        return await fn()


# =========================================================
# CREATE / READ
# =========================================================

async def test_create_and_get_round_trip_keeps_every_field(database, repository, user_factory):
    user_id = await user_factory()
    target = uuid4()
    own = uuid4()
    job = await _add_job(
        database, repository, user_id,
        kind=ExcelJobKind.VLCC_IMPORT,
        mode=ImportMode.CREATE_ONLY,
        dry_run=True,
        target_id=target,
        owner_own_id=own,
        source_file="source.xlsx",
        total_rows=1200,
    )

    loaded = await _in_new_transaction(database, lambda: repository.get(job.id))

    assert loaded is not None
    assert loaded.kind is ExcelJobKind.VLCC_IMPORT
    assert loaded.status is ExcelJobStatus.QUEUED
    assert loaded.mode is ImportMode.CREATE_ONLY
    assert loaded.dry_run is True
    assert loaded.created_by == user_id
    assert loaded.owner_role == int(Role.VLCC)
    assert loaded.owner_own_id == own
    assert loaded.target_id == target
    assert loaded.source_file == "source.xlsx"
    assert loaded.total_rows == 1200
    assert loaded.processed_rows == 0
    assert loaded.cancel_requested is False
    assert loaded.worker_pid is None


async def test_get_unknown_job_returns_none(database, repository):
    assert await _in_new_transaction(database, lambda: repository.get(uuid4())) is None


async def test_save_progress_updates_counters(database, repository, user_factory):
    user_id = await user_factory()
    job = await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING)
    now = now_naive_ist()

    await _in_new_transaction(database, lambda: repository.save_progress(
        job.id, processed_rows=500, total_rows=2000, inserted=300, updated=180, discarded=20, now=now,
    ))
    loaded = await _in_new_transaction(database, lambda: repository.get(job.id))

    assert (loaded.processed_rows, loaded.total_rows) == (500, 2000)
    assert (loaded.inserted, loaded.updated, loaded.discarded) == (300, 180, 20)
    assert loaded.heartbeat_at == now


async def test_mark_finished_sets_status_files_and_truncates_error(database, repository, user_factory):
    user_id = await user_factory()
    job = await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING)
    now = now_naive_ist()

    await _in_new_transaction(database, lambda: repository.mark_finished(
        job.id, status=ExcelJobStatus.FAILED, finished_at=now,
        error_message="x" * 900, report_file="discarded.xlsx",
    ))
    loaded = await _in_new_transaction(database, lambda: repository.get(job.id))

    assert loaded.status is ExcelJobStatus.FAILED
    assert loaded.finished_at == now
    assert loaded.report_file == "discarded.xlsx"
    assert len(loaded.error_message) == 500


async def test_find_active_matches_user_and_kind_only(database, repository, user_factory):
    user_a = await user_factory()
    user_b = await user_factory()
    queued = await _add_job(database, repository, user_a, kind=ExcelJobKind.FARMER_IMPORT)
    await _add_job(database, repository, user_a, kind=ExcelJobKind.FARMER_EXPORT, status=ExcelJobStatus.COMPLETED)

    found = await _in_new_transaction(database, lambda: repository.find_active(user_a, ExcelJobKind.FARMER_IMPORT))
    other_kind = await _in_new_transaction(database, lambda: repository.find_active(user_a, ExcelJobKind.FARMER_EXPORT))
    other_user = await _in_new_transaction(database, lambda: repository.find_active(user_b, ExcelJobKind.FARMER_IMPORT))

    assert found is not None and found.id == queued.id
    assert other_kind is None          # the only export is COMPLETED, not active
    assert other_user is None


async def test_list_and_count_never_return_other_users_jobs(database, repository, user_factory):
    user_a = await user_factory()
    user_b = await user_factory()
    a_jobs = [await _add_job(database, repository, user_a, age_minutes=age) for age in (3, 2, 1)]
    await _add_job(database, repository, user_b)

    page = await _in_new_transaction(database, lambda: repository.list_for_user(user_a, limit=2, offset=0))
    total = await _in_new_transaction(database, lambda: repository.count_for_user(user_a))
    b_total = await _in_new_transaction(database, lambda: repository.count_for_user(user_b))

    assert [job.id for job in page] == [a_jobs[2].id, a_jobs[1].id]     # newest first
    assert all(job.created_by == user_a for job in page)
    assert total == 3
    assert b_total == 1


async def test_count_running_and_queued(database, repository, user_factory):
    user_id = await user_factory()
    await _add_job(database, repository, user_id, status=ExcelJobStatus.QUEUED)
    await _add_job(database, repository, user_id, status=ExcelJobStatus.QUEUED)
    await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING)
    await _add_job(database, repository, user_id, status=ExcelJobStatus.COMPLETED)

    assert await _in_new_transaction(database, repository.count_queued) == 2
    assert await _in_new_transaction(database, repository.count_running) == 1
    running = await _in_new_transaction(database, repository.list_running)
    assert [job.status for job in running] == [ExcelJobStatus.RUNNING]


# =========================================================
# WORKER LIFECYCLE
# =========================================================

async def test_claim_next_takes_the_oldest_queued_job(database, repository, user_factory):
    user_id = await user_factory()
    older = await _add_job(database, repository, user_id, age_minutes=10)
    await _add_job(database, repository, user_id, age_minutes=1)
    now = now_naive_ist()

    claimed = await _in_new_transaction(database, lambda: repository.claim_next(4242, now))

    assert claimed is not None and claimed.id == older.id
    assert claimed.status is ExcelJobStatus.RUNNING
    assert claimed.worker_pid == 4242
    assert claimed.started_at == now and claimed.heartbeat_at == now


async def test_claim_next_without_queued_job_returns_none(database, repository, user_factory):
    user_id = await user_factory()
    await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING)

    assert await _in_new_transaction(database, lambda: repository.claim_next(1, now_naive_ist())) is None


async def test_claim_next_race_gives_the_job_to_exactly_one_caller(database, repository, user_factory):
    user_id = await user_factory()
    job = await _add_job(database, repository, user_id)

    async def claim(pid: int):
        return await _in_new_transaction(database, lambda: repository.claim_next(pid, now_naive_ist()))

    # Separate empty contexts -> separate sessions, like two worker loops
    results = await asyncio.gather(
        asyncio.create_task(claim(1), context=contextvars.Context()),
        asyncio.create_task(claim(2), context=contextvars.Context()),
    )

    winners = [result for result in results if result is not None]
    assert len(winners) == 1
    assert winners[0].id == job.id
    loaded = await _in_new_transaction(database, lambda: repository.get(job.id))
    assert loaded.worker_pid == winners[0].worker_pid


async def test_request_cancel_sets_flag_only_for_active_jobs(database, repository, user_factory):
    user_id = await user_factory()
    running = await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING)
    finished = await _add_job(database, repository, user_id, status=ExcelJobStatus.COMPLETED)

    await _in_new_transaction(database, lambda: repository.request_cancel(running.id))
    await _in_new_transaction(database, lambda: repository.request_cancel(finished.id))

    assert await _in_new_transaction(database, lambda: repository.is_cancel_requested(running.id)) is True
    assert await _in_new_transaction(database, lambda: repository.is_cancel_requested(finished.id)) is False


# =========================================================
# RECOVERY / CLEANUP
# =========================================================

async def test_fail_stale_fails_only_jobs_with_old_heartbeat(database, repository, user_factory):
    user_id = await user_factory()
    now = now_naive_ist()
    stale = await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING,
                           heartbeat_at=now - timedelta(minutes=5))
    fresh = await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING,
                           heartbeat_at=now - timedelta(seconds=10))

    count = await _in_new_transaction(database, lambda: repository.fail_stale(now - timedelta(minutes=2), now))
    stale_loaded = await _in_new_transaction(database, lambda: repository.get(stale.id))
    fresh_loaded = await _in_new_transaction(database, lambda: repository.get(fresh.id))

    assert count == 1
    assert stale_loaded.status is ExcelJobStatus.FAILED
    assert stale_loaded.error_message == "Worker stopped responding"
    assert fresh_loaded.status is ExcelJobStatus.RUNNING


async def test_fail_interrupted_fails_active_jobs_and_keeps_progress(database, repository, user_factory):
    user_id = await user_factory()
    queued = await _add_job(database, repository, user_id, status=ExcelJobStatus.QUEUED)
    running = await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING, processed_rows=700)
    done = await _add_job(database, repository, user_id, status=ExcelJobStatus.COMPLETED)

    count = await _in_new_transaction(database, lambda: repository.fail_interrupted(now_naive_ist()))
    loaded = {
        job.id: await _in_new_transaction(database, lambda job=job: repository.get(job.id))
        for job in (queued, running, done)
    }

    assert count == 2
    assert loaded[queued.id].status is ExcelJobStatus.FAILED
    assert loaded[running.id].status is ExcelJobStatus.FAILED
    assert loaded[running.id].processed_rows == 700
    assert loaded[running.id].error_message == "Interrupted by server restart"
    assert loaded[done.id].status is ExcelJobStatus.COMPLETED


async def test_list_expired_returns_only_jobs_finished_before_cutoff(database, repository, user_factory):
    user_id = await user_factory()
    now = now_naive_ist()
    old = await _add_job(database, repository, user_id, status=ExcelJobStatus.COMPLETED,
                         finished_at=now - timedelta(hours=25))
    await _add_job(database, repository, user_id, status=ExcelJobStatus.COMPLETED,
                   finished_at=now - timedelta(hours=1))
    await _add_job(database, repository, user_id, status=ExcelJobStatus.RUNNING)

    expired = await _in_new_transaction(database, lambda: repository.list_expired(now - timedelta(hours=24)))

    assert [job.id for job in expired] == [old.id]


async def test_delete_removes_the_row(database, repository, user_factory):
    user_id = await user_factory()
    job = await _add_job(database, repository, user_id, status=ExcelJobStatus.COMPLETED)

    await _in_new_transaction(database, lambda: repository.delete(job.id))

    assert await _in_new_transaction(database, lambda: repository.get(job.id)) is None
