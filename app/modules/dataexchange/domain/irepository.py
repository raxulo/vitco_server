from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.dataexchange.domain.column_layout import LayoutUser
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus


class IColumnLayoutRepository(ABC):
    """Stored export column layouts, one row per (user, sheet) (REQ-55, DECISION-030)."""

    @abstractmethod
    async def get(self, user_id: UUID, sheet: str) -> list[dict[str, Any]] | None:
        """The stored columns, or None when the user still has the default."""
        ...

    @abstractmethod
    async def save(self, user_id: UUID, sheet: str, columns: list[dict[str, Any]], actor_id: UUID) -> None:
        """Insert or replace the user's layout."""
        ...

    @abstractmethod
    async def delete(self, user_id: UUID, sheet: str) -> None:
        """Back to the default."""
        ...

    @abstractmethod
    async def layout_owner(self, user: Any) -> UUID | None:
        """
        Whose layout an export by `user` follows: a manager's own; an MCC's creator;
        a VLCC's creator, or the MCC's creator when an MCC user made the VLCC.
        None (the default layout) for anyone else or a deleted owner.
        """
        ...

    @abstractmethod
    async def manageable_user(self, actor: Any, user_id: UUID) -> LayoutUser | None:
        """
        `user_id` when `actor` may change its layout: itself; any Admin / Sub Admin for
        a Super Admin; its own Sub Admins for an Admin. None otherwise.
        """
        ...


class IExcelJobRepository(ABC):

    # =========================================================
    # CREATE / READ
    # =========================================================

    @abstractmethod
    async def create(self, job: ExcelJob) -> None:
        ...

    @abstractmethod
    async def get(self, job_id: UUID) -> ExcelJob | None:
        ...

    @abstractmethod
    async def list_for_user(
        self,
        user_id: UUID,
        *,
        kind: ExcelJobKind | None = None,
        status: ExcelJobStatus | None = None,
        limit: int = 20,
        offset: int = 0,
    ) -> list[ExcelJob]:
        ...

    @abstractmethod
    async def count_for_user(
        self,
        user_id: UUID,
        *,
        kind: ExcelJobKind | None = None,
        status: ExcelJobStatus | None = None,
    ) -> int:
        ...

    @abstractmethod
    async def find_active(self, user_id: UUID, kind: ExcelJobKind) -> ExcelJob | None:
        ...

    @abstractmethod
    async def count_running(self) -> int:
        ...

    @abstractmethod
    async def list_running(self) -> list[ExcelJob]:
        ...

    @abstractmethod
    async def count_queued(self) -> int:
        ...

    # =========================================================
    # WORKER LIFECYCLE
    # =========================================================

    @abstractmethod
    async def claim_next(self, worker_pid: int, now: datetime) -> ExcelJob | None:
        """Atomically move the oldest QUEUED job to RUNNING for this worker."""
        ...

    @abstractmethod
    async def heartbeat(self, job_id: UUID, now: datetime) -> None:
        ...

    @abstractmethod
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
        ...

    @abstractmethod
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
        ...

    @abstractmethod
    async def request_cancel(self, job_id: UUID) -> None:
        ...

    @abstractmethod
    async def is_cancel_requested(self, job_id: UUID) -> bool:
        ...

    # =========================================================
    # RECOVERY / CLEANUP
    # =========================================================

    @abstractmethod
    async def fail_stale(self, before: datetime, now: datetime) -> int:
        """Fail RUNNING jobs whose heartbeat is older than `before`."""
        ...

    @abstractmethod
    async def fail_interrupted(self, now: datetime) -> int:
        """Fail every QUEUED / RUNNING job (server restart)."""
        ...

    @abstractmethod
    async def list_expired(self, before: datetime) -> list[ExcelJob]:
        ...

    @abstractmethod
    async def delete(self, job_id: UUID) -> None:
        ...
