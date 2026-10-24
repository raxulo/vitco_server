from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus


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
