"""
Exchange Worker Supervisor

Runs inside the API process (lifespan) and keeps the exchange worker alive
(DECISION-008):

- starts `python -m app.worker.exchange --parent-pid <api pid>` as a child process;
- restarts it with back-off (1 s → 30 s) whenever it exits;
- watchdog: fails RUNNING jobs whose heartbeat went stale (frozen / killed worker);
- cleanup: deletes job / upload folders and job rows older than the TTL;
- startup recovery: fails RUNNING jobs whose worker process no longer exists.

The child is started with `subprocess.Popen` and polled, which works on every
event loop (Windows selector loops cannot run asyncio subprocesses).

Python 3.13+
"""

from __future__ import annotations

import asyncio
import contextlib
import contextvars
import os
import subprocess
import sys
import time
from collections.abc import Sequence
from datetime import timedelta
from pathlib import Path

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.core.logging.logger import get_logger
from app.modules.dataexchange.domain.enums import ExcelJobStatus
from app.modules.dataexchange.domain.irepository import IExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.worker.exchange import parent_alive

logger = get_logger("exchange_supervisor")

_HEALTHY_RESET_S = 300          # a worker alive this long resets the back-off
_STDERR_MAX_BYTES = 5 * 1024 * 1024


class WorkerSupervisor:

    __slots__ = (
        "_database",
        "_repository",
        "_storage",
        "_enabled",
        "_command",
        "_cwd",
        "_log_dir",
        "_heartbeat_timeout_s",
        "_file_ttl",
        "_watchdog_interval_s",
        "_cleanup_interval_s",
        "_process",
        "_started_at",
        "_backoff_s",
        "_tasks",
        "_stopping",
    )

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: IExcelJobRepository,
        storage: ExchangeStorage,
        enabled: bool,
        log_dir: Path,
        heartbeat_timeout_s: int,
        file_ttl_hours: int,
        watchdog_interval_s: float = 30.0,
        cleanup_interval_s: float = 3600.0,
        command: Sequence[str] | None = None,
        cwd: Path | None = None,
    ) -> None:
        self._database = database
        self._repository = repository
        self._storage = storage
        self._enabled = enabled
        self._command = tuple(command) if command else (sys.executable, "-m", "app.worker.exchange")
        self._cwd = cwd
        self._log_dir = log_dir
        self._heartbeat_timeout_s = heartbeat_timeout_s
        self._file_ttl = timedelta(hours=file_ttl_hours)
        self._watchdog_interval_s = watchdog_interval_s
        self._cleanup_interval_s = cleanup_interval_s
        self._process: subprocess.Popen | None = None
        self._started_at = 0.0
        self._backoff_s = 1.0
        self._tasks: list[asyncio.Task] = []
        self._stopping = False

    @property
    def worker_pid(self) -> int | None:
        process = self._process
        return process.pid if process is not None and process.poll() is None else None

    # =========================================================
    # LIFECYCLE
    # =========================================================

    async def start(self) -> None:
        self._stopping = False
        if self._enabled:
            try:
                self._spawn()
            except OSError:
                logger.exception("could not start the exchange worker; will retry")
            self._tasks.append(asyncio.create_task(self._monitor(), context=contextvars.Context()))
        self._tasks.append(asyncio.create_task(self._watchdog(), context=contextvars.Context()))

    async def stop(self) -> None:
        self._stopping = True
        for task in self._tasks:
            task.cancel()
        for task in self._tasks:
            with contextlib.suppress(asyncio.CancelledError):
                await task
        self._tasks.clear()
        await self._terminate()

    async def recover(self) -> int:
        """Fail RUNNING jobs whose worker process is gone (previous server run)."""
        now = now_naive_ist()
        failed = 0
        async with self._database.transaction():
            for job in await self._repository.list_running():
                if job.worker_pid and parent_alive(job.worker_pid):
                    continue
                await self._repository.mark_finished(
                    job.id,
                    status=ExcelJobStatus.FAILED,
                    finished_at=now,
                    error_message="Interrupted by server restart",
                )
                failed += 1
        if failed:
            logger.warning("recovered %s interrupted import / export job(s)", failed)
        return failed

    # =========================================================
    # MAINTENANCE (also called directly by tests)
    # =========================================================

    async def watchdog_once(self) -> int:
        now = now_naive_ist()
        async with self._database.transaction():
            failed = await self._repository.fail_stale(now - timedelta(seconds=self._heartbeat_timeout_s), now)
        if failed:
            logger.warning("watchdog failed %s job(s) with a stale heartbeat", failed)
        return failed

    async def cleanup_once(self) -> int:
        cutoff = now_naive_ist() - self._file_ttl
        async with self._database.transaction():
            expired = await self._repository.list_expired(cutoff)
        removed = 0
        for job in expired:
            await asyncio.to_thread(self._storage.delete_dir, self._storage.root / "jobs" / str(job.id))
            async with self._database.transaction():
                await self._repository.delete(job.id)
            removed += 1
        await asyncio.to_thread(self._remove_old_uploads)
        return removed

    # =========================================================
    # INTERNALS
    # =========================================================

    def _spawn(self) -> None:
        self._log_dir.mkdir(parents=True, exist_ok=True)
        stderr_path = self._log_dir / "exchange_worker.stderr.log"
        if stderr_path.exists() and stderr_path.stat().st_size > _STDERR_MAX_BYTES:
            stderr_path.unlink(missing_ok=True)
        with open(stderr_path, "ab") as stderr:
            stderr.write(f"\n--- exchange worker starting {now_naive_ist():%Y-%m-%d %H:%M:%S} ---\n".encode())
            stderr.flush()
            # stdout to DEVNULL and stderr to a file: a pipe nobody reads would block the child when full
            self._process = subprocess.Popen(
                [*self._command, "--parent-pid", str(os.getpid())],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=stderr,
                cwd=self._cwd,
                close_fds=True,
            )
        self._started_at = time.monotonic()
        logger.info("exchange worker started (pid %s)", self._process.pid)

    async def _monitor(self) -> None:
        while not self._stopping:
            await asyncio.sleep(1.0)
            process = self._process
            if process is not None and process.poll() is None:
                if time.monotonic() - self._started_at > _HEALTHY_RESET_S:
                    self._backoff_s = 1.0
                continue
            code = process.returncode if process is not None else None
            logger.error("exchange worker exited (code %s); restarting in %.0f s", code, self._backoff_s)
            await asyncio.sleep(self._backoff_s)
            self._backoff_s = min(self._backoff_s * 2, 30.0)
            if self._stopping:
                return
            try:
                self._spawn()
            except OSError:
                logger.exception("could not restart the exchange worker")

    async def _watchdog(self) -> None:
        last_cleanup = 0.0
        while True:
            try:
                await self.watchdog_once()
                if time.monotonic() - last_cleanup >= self._cleanup_interval_s:
                    last_cleanup = time.monotonic()
                    await self.cleanup_once()
            except asyncio.CancelledError:
                raise
            except Exception:
                logger.exception("exchange watchdog / cleanup failed; retrying")
            await asyncio.sleep(self._watchdog_interval_s)

    async def _terminate(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        process.terminate()                     # SIGTERM on POSIX, TerminateProcess on Windows
        deadline = time.monotonic() + 10.0
        while process.poll() is None and time.monotonic() < deadline:
            await asyncio.sleep(0.1)
        if process.poll() is None:
            process.kill()
            await asyncio.to_thread(process.wait, 5)
        logger.info("exchange worker stopped (code %s)", process.returncode)

    def _remove_old_uploads(self) -> None:
        uploads = self._storage.root / "uploads"
        if not uploads.exists():
            return
        cutoff = time.time() - self._file_ttl.total_seconds()
        for folder in uploads.iterdir():
            with contextlib.suppress(OSError):
                if folder.is_dir() and folder.stat().st_mtime < cutoff:
                    self._storage.delete_dir(folder)
