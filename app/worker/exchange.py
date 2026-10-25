"""
Exchange Worker Process

Runs Excel import / export jobs outside the API process (DECISION-008):

    python -m app.worker.exchange --parent-pid <api pid>

- claims QUEUED jobs atomically from `excel_jobs` (at most N at a time);
- runs each job's processor with a heartbeat, cooperative cancel and memory guard;
- exits on its own when the API process (its parent) is gone, or on SIGTERM / SIGINT.

The worker builds the same IoC container as the API but never creates the
FastAPI app or serves HTTP.

Python 3.13+
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import contextvars
import os
import signal
import sys
from logging.handlers import RotatingFileHandler
from typing import Any
from uuid import UUID

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.core.logging.logger import get_logger
from app.modules.dataexchange.application.batching import (
    AdaptiveBatcher,
    MemoryGuard,
    WorkerMemoryLimitError,
    read_rss_bytes,
)
from app.modules.dataexchange.application.processor import (
    ExchangeProcessor,
    JobCancelled,
    JobContext,
    JobInterrupted,
)
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus
from app.modules.dataexchange.domain.irepository import IExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage

logger = get_logger("exchange_worker")

_PARENT_CHECK_S = 2.0
_SHUTDOWN_GRACE_S = 3.0


class ExchangeWorker:

    __slots__ = (
        "_database",
        "_repository",
        "_storage",
        "_processors",
        "_max_concurrent",
        "_poll_s",
        "_heartbeat_s",
        "_budget_ms",
        "_max_batch",
        "_pause_ms",
        "_memory_guard",
        "_parent_pid",
        "_running",
        "_contexts",
        "_stop",
    )

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: IExcelJobRepository,
        storage: ExchangeStorage,
        max_concurrent: int,
        poll_interval_ms: int,
        tx_budget_ms: int,
        max_batch_size: int,
        batch_pause_ms: int,
        max_memory_mb: int,
        heartbeat_interval_s: float = 10.0,
        parent_pid: int | None = None,
        rss_reader=read_rss_bytes,
    ) -> None:
        self._database = database
        self._repository = repository
        self._storage = storage
        self._processors: dict[ExcelJobKind, ExchangeProcessor] = {}
        self._max_concurrent = max(1, max_concurrent)
        self._poll_s = poll_interval_ms / 1000
        self._heartbeat_s = heartbeat_interval_s
        self._budget_ms = tx_budget_ms
        self._max_batch = max_batch_size
        self._pause_ms = batch_pause_ms
        self._memory_guard = MemoryGuard(hard_mb=max_memory_mb, reader=rss_reader)
        self._parent_pid = parent_pid
        self._running: dict[UUID, asyncio.Task] = {}
        self._contexts: dict[UUID, JobContext] = {}
        self._stop = asyncio.Event()

    # =========================================================
    # PUBLIC
    # =========================================================

    def register(self, processor: ExchangeProcessor) -> None:
        self._processors[processor.kind] = processor

    @property
    def running_jobs(self) -> int:
        return len(self._running)

    def stop(self) -> None:
        self._stop.set()

    async def run(self) -> None:
        """Main loop: claim and run jobs until stopped or the parent process is gone."""
        logger.info("exchange worker started (pid %s, max %s jobs)", os.getpid(), self._max_concurrent)
        watcher = asyncio.create_task(self._watch_parent(), context=contextvars.Context())
        try:
            while not self._stop.is_set():
                claimed = await self.claim_available()
                if not claimed:
                    with contextlib.suppress(TimeoutError):
                        await asyncio.wait_for(self._stop.wait(), timeout=self._poll_s)
        finally:
            watcher.cancel()
            await self._shutdown()
            logger.info("exchange worker stopped (pid %s)", os.getpid())

    async def claim_available(self) -> int:
        """Claim jobs into the free slots; returns how many were started."""
        started = 0
        while len(self._running) < self._max_concurrent and not self._stop.is_set():
            try:
                async with self._database.transaction():
                    job = await self._repository.claim_next(os.getpid(), now_naive_ist())
            except Exception:
                logger.exception("could not claim a job; retrying on the next poll")
                return started
            if job is None:
                return started
            task = asyncio.create_task(self._execute(job), context=contextvars.Context())
            self._running[job.id] = task
            task.add_done_callback(lambda _task, job_id=job.id: self._running.pop(job_id, None))
            started += 1
        return started

    # =========================================================
    # JOB EXECUTION
    # =========================================================

    async def _execute(self, job: ExcelJob) -> None:
        ctx = JobContext(
            job=job,
            job_dir=self._storage.job_dir(job.id),
            database=self._database,
            repository=self._repository,
            disk=self._storage,
            batcher=AdaptiveBatcher(budget_ms=self._budget_ms, maximum=self._max_batch),
            memory=self._memory_guard,
            pause_ms=self._pause_ms,
        )
        self._contexts[job.id] = ctx
        heartbeat = asyncio.create_task(self._heartbeat(job.id), context=contextvars.Context())

        status = ExcelJobStatus.COMPLETED
        error: str | None = None
        result_file: str | None = None
        report_file: str | None = None
        try:
            processor = self._processors.get(job.kind)
            if processor is None:
                raise LookupError(f"No processor for {job.kind.name}")
            logger.info("job %s (%s) started", job.id, job.kind.name)
            result = await processor.run(ctx)
            result_file, report_file = result.result_file, result.report_file
        except JobCancelled:
            status = ExcelJobStatus.CANCELLED
            error = "Cancelled by the user"
        except JobInterrupted as reason:
            status, error = ExcelJobStatus.FAILED, str(reason)
        except WorkerMemoryLimitError as reason:
            status, error = ExcelJobStatus.FAILED, str(reason)
            logger.error("job %s stopped: %s", job.id, reason)
        except Exception as exc:
            status, error = ExcelJobStatus.FAILED, (str(exc) or type(exc).__name__)
            logger.exception("job %s failed", job.id)
        finally:
            heartbeat.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await heartbeat
            self._contexts.pop(job.id, None)
            await self._finish(ctx, status, error, result_file, report_file)

    async def _finish(
        self,
        ctx: JobContext,
        status: ExcelJobStatus,
        error: str | None,
        result_file: str | None,
        report_file: str | None,
    ) -> None:
        now = now_naive_ist()
        try:
            async with self._database.transaction():
                await self._repository.save_progress(
                    ctx.job.id,
                    processed_rows=ctx.processed,
                    total_rows=max(ctx.total, ctx.processed),
                    inserted=ctx.inserted,
                    updated=ctx.updated,
                    discarded=ctx.discarded,
                    now=now,
                )
                await self._repository.mark_finished(
                    ctx.job.id,
                    status=status,
                    finished_at=now,
                    error_message=error,
                    result_file=result_file,
                    report_file=report_file,
                )
            logger.info("job %s finished: %s", ctx.job.id, status.name)
        except Exception:
            # The API watchdog fails the job once its heartbeat goes stale
            logger.exception("could not record the end of job %s", ctx.job.id)

    async def _heartbeat(self, job_id: UUID) -> None:
        while True:
            await asyncio.sleep(self._heartbeat_s)
            try:
                async with self._database.transaction():
                    await self._repository.heartbeat(job_id, now_naive_ist())
            except Exception:
                logger.exception("heartbeat for job %s failed", job_id)

    # =========================================================
    # SHUTDOWN
    # =========================================================

    async def _watch_parent(self) -> None:
        if self._parent_pid is None:
            return
        while True:
            await asyncio.sleep(_PARENT_CHECK_S)
            if not parent_alive(self._parent_pid):
                logger.warning("parent process %s gone, exchange worker exiting", self._parent_pid)
                self.stop()
                return

    async def _shutdown(self) -> None:
        if not self._running:
            return
        for ctx in list(self._contexts.values()):
            ctx.interrupt("Interrupted by server restart")
        _, pending = await asyncio.wait(list(self._running.values()), timeout=_SHUTDOWN_GRACE_S)
        for task in pending:
            task.cancel()
        if pending:
            await asyncio.wait(pending, timeout=1.0)


# =========================================================
# PROCESS HELPERS
# =========================================================

def parent_alive(pid: int) -> bool:
    """True while process `pid` exists."""
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        synchronize, wait_timeout, access_denied = 0x00100000, 0x00000102, 5
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        handle = kernel32.OpenProcess(synchronize, False, pid)
        if not handle:
            return ctypes.get_last_error() == access_denied
        try:
            return kernel32.WaitForSingleObject(handle, 0) == wait_timeout
        finally:
            kernel32.CloseHandle(handle)

    if os.getppid() != pid:                      # re-parented: the original parent is gone
        return False
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def register_processors(container: Any, worker: ExchangeWorker) -> None:
    """Entity processors; each phase adds its own (farmers: Phase 2, VLCCs: 3, prodata: 4)."""
    from app.modules.auth.infrastructure.password import PasswordService
    from app.modules.dataexchange.application.farmer_export import FarmerExportProcessor
    from app.modules.dataexchange.application.farmer_import import FarmerImportProcessor
    from app.modules.dataexchange.infrastructure.farmer_repository import FarmerExchangeRepository

    database = container.database
    passwords = container.resolve(PasswordService)

    farmers = FarmerExchangeRepository(database)
    worker.register(FarmerExportProcessor(database=database, repository=farmers))
    worker.register(FarmerImportProcessor(
        database=database, repository=farmers, password_service=passwords,
    ))

    from app.modules.dataexchange.application.vlcc_export import VlccExportProcessor
    from app.modules.dataexchange.application.vlcc_import import VlccImportProcessor
    from app.modules.dataexchange.infrastructure.vlcc_repository import VlccExchangeRepository

    vlccs = VlccExchangeRepository(database)
    worker.register(VlccExportProcessor(database=database, repository=vlccs))
    worker.register(VlccImportProcessor(
        database=database, repository=vlccs, password_service=passwords,
    ))

    from app.modules.dataexchange.application.prodata_export import ProdataExportProcessor
    from app.modules.dataexchange.application.prodata_import import ProdataImportProcessor
    from app.modules.dataexchange.infrastructure.prodata_repository import ProdataExchangeRepository

    prodata_repo = ProdataExchangeRepository(database)
    worker.register(ProdataExportProcessor(database=database, repository=prodata_repo))
    worker.register(ProdataImportProcessor(database=database, repository=prodata_repo))

    from app.modules.dataexchange.application.formula_export import FormulaExportProcessor
    from app.modules.dataexchange.application.formula_import import FormulaImportProcessor
    from app.modules.dataexchange.infrastructure.formula_repository import FormulaExchangeRepository

    formula_repo = FormulaExchangeRepository(database)
    worker.register(FormulaExportProcessor(database=database, repository=formula_repo))
    worker.register(FormulaImportProcessor(database=database, repository=formula_repo))



def _configure_logging() -> None:
    from app.config.logging import LOGGER_CONFIG
    from app.config.settings import settings
    from app.core.logging.formatter import JsonFormatter
    from app.core.logging.handlers import HandlerFactory

    settings.LOG_PATH.mkdir(parents=True, exist_ok=True)
    # Own rotating file: two processes must never rotate the API's log file
    file_handler = RotatingFileHandler(
        settings.LOG_PATH / "exchange_worker.log",
        maxBytes=LOGGER_CONFIG.max_file_size,
        backupCount=5,
        encoding=LOGGER_CONFIG.encoding,
    )
    file_handler.setFormatter(JsonFormatter())
    root = get_logger()
    root.handlers.clear()
    root.addHandler(file_handler)
    root.addHandler(HandlerFactory.console())
    root.setLevel(LOGGER_CONFIG.level)
    root.propagate = False


def _limit_address_space(max_memory_mb: int) -> None:
    """Last-resort OS limit (Linux); the RSS-based MemoryGuard is the primary guard."""
    if not sys.platform.startswith("linux"):
        return
    try:
        import resource

        limit = (max_memory_mb * 2 + 512) * 1024 * 1024        # virtual memory has headroom for mmap / threads
        resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
    except (ValueError, OSError):
        logger.warning("could not set the worker address-space limit")


def build_worker(parent_pid: int | None) -> tuple[ExchangeWorker, DatabaseManager]:
    """Build the API's IoC container (without the FastAPI app) and the worker on top of it."""
    from app.bootstrap.infrastructure import InfrastructureConfigurator
    from app.bootstrap.state import ApplicationState
    from app.config.settings import settings
    from app.modules.configurator import ModuleConfigurator
    from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository

    state = ApplicationState()
    InfrastructureConfigurator.configure(state.container)
    ModuleConfigurator.configure(state)
    container = state.container

    worker = ExchangeWorker(
        database=container.database,
        repository=container.resolve(ExcelJobRepository),
        storage=container.resolve(ExchangeStorage),
        max_concurrent=settings.EXCHANGE_MAX_CONCURRENT_JOBS,
        poll_interval_ms=settings.EXCHANGE_POLL_INTERVAL_MS,
        tx_budget_ms=settings.EXCHANGE_TX_BUDGET_MS,
        max_batch_size=settings.EXCHANGE_MAX_BATCH_SIZE,
        batch_pause_ms=settings.EXCHANGE_BATCH_PAUSE_MS,
        max_memory_mb=settings.EXCHANGE_WORKER_MAX_MEMORY_MB,
        parent_pid=parent_pid,
    )
    register_processors(container, worker)
    return worker, container.database


async def _main(parent_pid: int | None) -> None:
    from app.config.settings import settings

    from app.modules.dataexchange.infrastructure.indexes import ensure_indexes

    _limit_address_space(settings.EXCHANGE_WORKER_MAX_MEMORY_MB)
    worker, database = build_worker(parent_pid)
    await database.startup()
    try:
        await ensure_indexes(database)          # one-time build happens here, never in the API process
    except Exception:
        logger.exception("could not create exchange indexes; imports still work, only slower")

    loop = asyncio.get_running_loop()
    for signum in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError, RuntimeError):   # Windows has no add_signal_handler
            loop.add_signal_handler(signum, worker.stop)
    try:
        await worker.run()
    finally:
        await database.shutdown()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m app.worker.exchange",
        description="Quickyee Excel import / export worker (started and supervised by the API).",
    )
    parser.add_argument("--parent-pid", type=int, default=None, help="exit when this process ends")
    args = parser.parse_args(argv)

    _configure_logging()
    try:
        asyncio.run(_main(args.parent_pid))
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
