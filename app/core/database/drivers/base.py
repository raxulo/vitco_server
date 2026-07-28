"""
RealTimeTransfer
================

Enterprise Base Database Driver

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
)

from app.core.database.exceptions import (
    DatabaseConnectionError,
)
from app.core.database.session import SessionManager
from app.core.database.interface import DatabaseDriver


class BaseDatabaseDriver(DatabaseDriver, ABC):
    """
    Enterprise Database Driver Base Class.

    Responsibilities
    ----------------
    • Engine lifecycle
    • SessionManager ownership
    • Health Check
    • Driver Metadata
    """

    __slots__ = (
        "_engine",
        "_session_manager",
        "_connected",
        "_telemetry",
    )

    def __init__(self) -> None:
        from app.core.database.metrics import DatabaseMetricsCollector

        self._engine: AsyncEngine | None = None
        self._session_manager: SessionManager | None = None
        self._connected = False
        self._telemetry = DatabaseMetricsCollector()

    @property
    @abstractmethod
    def name(self) -> str:
        """
        Driver name.
        """

    @property
    def engine(self) -> AsyncEngine:
        if self._engine is None:
            raise DatabaseConnectionError(
                "Database engine is not initialized."
            )
        return self._engine

    @property
    def session_manager(self) -> SessionManager:
        if self._session_manager is None:
            raise DatabaseConnectionError(
                "SessionManager is not initialized."
            )
        return self._session_manager

    @property
    def connected(self) -> bool:
        return self._connected

    @abstractmethod
    async def connect(self) -> None:
        """
        Create engine.
        """

    @abstractmethod
    async def disconnect(self) -> None:
        """
        Dispose engine.
        """

    async def start(self) -> None:
        await self.connect()

    async def stop(self) -> None:
        await self.disconnect()

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:
        async with self.session_manager.session() as session:
            yield session

    async def ping(self) -> bool:
        try:
            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))
            return True
        except Exception:
            return False

    async def ping_latency(self) -> float:
        import time
        start = time.perf_counter()
        success = await self.ping()
        return (time.perf_counter() - start) * 1000.0 if success else -1.0

    def _start_telemetry(self) -> None:
        self._telemetry.instrument_engine(self.engine)
        self._telemetry.instrument_session_factory(self.session_manager.factory)

    async def health(self) -> dict[str, Any]:
        import datetime
        from app.core.database.types import HealthStatus

        latency = await self.ping_latency()
        connected = latency >= 0

        status = HealthStatus.HEALTHY
        if not connected:
            status = HealthStatus.UNHEALTHY
        elif latency > 200:
            status = HealthStatus.DEGRADED

        if self._engine:
            self._telemetry.collect_pool_stats(self._engine)

        stats = self._telemetry.statistics

        return {
            "status": status.value,
            "connected": connected,
            "latency_ms": round(latency, 2),
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
            "message": "Database is operational" if connected else "Database connection lost",
            "statistics": {
                "active_connections": stats.active_connections,
                "idle_connections": stats.idle_connections,
                "total_connections": stats.total_connections,
                "checked_out_connections": stats.checked_out_connections,
                "overflow_connections": stats.overflow_connections,
                "total_transactions": stats.total_transactions,
                "committed_transactions": stats.committed_transactions,
                "rolled_back_transactions": stats.rolled_back_transactions,
                "failed_transactions": stats.failed_transactions,
                "retry_count": stats.retry_count,
                "timeout_count": stats.timeout_count,
                "total_queries": stats.total_queries,
                "failed_queries": stats.failed_queries,
            },
            "details": {
                "driver": self.name,
            }
        }