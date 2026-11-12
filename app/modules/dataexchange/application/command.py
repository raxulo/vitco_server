"""
Data Exchange Commands & Queries (CQRS)

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from app.middleware.authentication import CurrentUser
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus, ImportMode


@dataclass(slots=True, kw_only=True)
class SubmitExportCommand:
    kind: ExcelJobKind
    owner: CurrentUser
    target_id: UUID | None = None
    params: dict[str, Any] | None = None    # JSON-safe options, stored as the job's params.json (DECISION-028)


@dataclass(slots=True, kw_only=True)
class SubmitImportCommand:
    kind: ExcelJobKind
    owner: CurrentUser
    source: Path                        # completed, owner-checked upload (moved into the job folder)
    target_id: UUID | None = None
    mode: ImportMode = ImportMode.UPSERT
    dry_run: bool = False


@dataclass(slots=True, kw_only=True)
class GetExcelJobQuery:
    id: UUID
    owner: CurrentUser


@dataclass(slots=True, kw_only=True)
class ListExcelJobsQuery:
    owner: CurrentUser
    kind: ExcelJobKind | None = None
    status: ExcelJobStatus | None = None
    limit: int = 20
    offset: int = 0


@dataclass(slots=True, kw_only=True)
class CancelExcelJobCommand:
    id: UUID
    owner: CurrentUser


@dataclass(slots=True, kw_only=True)
class GetExcelJobFileQuery:
    id: UUID
    owner: CurrentUser
