"""
Data Exchange Application DTOs

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.core.clock import now_naive_ist
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus, ImportMode


@dataclass(slots=True, kw_only=True)
class ExcelJobDto:

    id: UUID
    kind: ExcelJobKind
    status: ExcelJobStatus
    mode: ImportMode | None
    dry_run: bool
    target_id: UUID | None
    total_rows: int
    processed_rows: int
    inserted: int
    updated: int
    discarded: int
    unchanged: int                          # imports: matched rows whose values were already the same
    progress: int                           # 0 - 100
    rows_per_second: float | None
    eta_seconds: int | None
    poll_after_ms: int | None               # None once the job has finished
    has_file: bool
    file_name: str | None
    error_message: str | None
    created_at: datetime | None
    started_at: datetime | None
    finished_at: datetime | None

    @classmethod
    def from_job(cls, job: ExcelJob) -> ExcelJobDto:
        file_name = job_file_name(job)
        rate, eta = _throughput(job)
        if job.total_rows > 0:
            progress = min(100, int(job.processed_rows * 100 / job.total_rows))
        else:
            progress = 100 if job.status is ExcelJobStatus.COMPLETED else 0
        return cls(
            id=job.id,
            kind=job.kind,
            status=job.status,
            mode=job.mode,
            dry_run=job.dry_run,
            target_id=job.target_id,
            total_rows=job.total_rows,
            processed_rows=job.processed_rows,
            inserted=job.inserted,
            updated=job.updated,
            discarded=job.discarded,
            unchanged=(
                max(job.processed_rows - job.inserted - job.updated - job.discarded, 0) if job.kind.is_import else 0
            ),
            progress=progress,
            rows_per_second=rate,
            eta_seconds=eta,
            poll_after_ms=_poll_after_ms(job),
            has_file=file_name is not None,
            file_name=file_name,
            error_message=job.error_message,
            created_at=job.created_at,
            started_at=job.started_at,
            finished_at=job.finished_at,
        )


def job_file_name(job: ExcelJob) -> str | None:
    """The downloadable file: the export result, else the discarded-rows report."""
    if job.status is ExcelJobStatus.COMPLETED and job.result_file:
        return job.result_file
    if job.status in (ExcelJobStatus.COMPLETED, ExcelJobStatus.FAILED) and job.report_file:
        return job.report_file
    return None


def _throughput(job: ExcelJob) -> tuple[float | None, int | None]:
    if job.started_at is None or job.processed_rows <= 0:
        return None, None
    end = job.finished_at or now_naive_ist()
    seconds = max((end - job.started_at).total_seconds(), 0.001)
    rate = round(job.processed_rows / seconds, 1)
    if job.status.is_finished or job.total_rows <= job.processed_rows:
        return rate, None
    return rate, int((job.total_rows - job.processed_rows) / rate)


def _poll_after_ms(job: ExcelJob) -> int | None:
    if job.status.is_finished:
        return None
    started = job.started_at or job.created_at
    if started is None:
        return 1000
    elapsed = (now_naive_ist() - started).total_seconds()
    if elapsed < 120:
        return 1000
    if elapsed < 600:
        return 2000
    return 5000
