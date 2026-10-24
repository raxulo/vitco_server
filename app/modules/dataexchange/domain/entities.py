"""
Data Exchange Domain Entities

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.dataexchange.domain.enums import (
    ExcelJobKind,
    ExcelJobStatus,
    ImportMode,
)


@dataclass(slots=True, kw_only=True)
class ExcelJob:
    """One Excel import / export, executed by the exchange worker process."""

    id: UUID
    kind: ExcelJobKind
    status: ExcelJobStatus

    # Requesting user — the worker rebuilds its access scope from these
    created_by: UUID
    owner_role: int
    owner_own_id: UUID | None = None

    # Selected VLCC (farmers), owner user (VLCCs) or rate chart (prodata)
    target_id: UUID | None = None

    mode: ImportMode | None = None
    dry_run: bool = False

    # File names relative to the job folder
    source_file: str | None = None
    result_file: str | None = None
    report_file: str | None = None

    total_rows: int = 0
    processed_rows: int = 0
    inserted: int = 0
    updated: int = 0
    discarded: int = 0

    error_message: str | None = None
    cancel_requested: bool = False
    worker_pid: int | None = None
    heartbeat_at: datetime | None = None

    created_at: datetime | None = None
    started_at: datetime | None = None
    finished_at: datetime | None = None
    updated_at: datetime | None = None
