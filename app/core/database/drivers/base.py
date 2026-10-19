# """
# RealTimeTransfer
# ================

# Enterprise Base Database Driver

# Python 3.13+
# """

# from __future__ import annotations

# import time
# from abc import ABC, abstractmethod
# from collections.abc import AsyncIterator
# from contextlib import asynccontextmanager
# from typing import Any

# from sqlalchemy import text
# from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

# from app.core.database.exceptions import DatabaseConnectionError
# from app.core.database.interface import DatabaseDriver
# from app.core.database.session import SessionManager


# class DatabaseMetrics:
#     def __getattr__(self, name: str) -> int:
#         return 0


# class DatabaseMetricsCollector:
#     def __init__(self) -> None:
#         self.statistics = DatabaseMetrics()

#     def instrument_engine(self, engine: Any) -> None:
#         pass

#     def instrument_session_factory(self, factory: Any) -> None:
#         pass

#     def collect_pool_stats(self, engine: Any) -> None:
#         pass


# class BaseDatabaseDriver(DatabaseDriver, ABC):
#     """
#     Enterprise Database Driver Base Class.
#     """

#     __slots__ = (
#         "_engine",
#         "_replica_engine",
#         "_session_manager",
#         "_connected",
#         "_telemetry",
#     )

#     def __init__(self) -> None:

#         self._engine: AsyncEngine | None = None
#         self._replica_engine: AsyncEngine | None = None
#         self._session_manager: SessionManager | None = None
#         self._connected = False
#         self._telemetry = DatabaseMetricsCollector()

#     @property
#     @abstractmethod
#     def name(self) -> str:
#         """
#         Driver name.
#         """

#     @property
#     def engine(self) -> AsyncEngine:
#         if self._engine is None:
#             raise DatabaseConnectionError("Primary database engine is not initialized.")
#         return self._engine

#     @property
#     def replica_engine(self) -> AsyncEngine:
#         if self._replica_engine is None:
#             # Fallback to primary if replica is not configured
#             return self.engine
#         return self._replica_engine

#     @property
#     def session_manager(self) -> SessionManager:
#         if self._session_manager is None:
#             raise DatabaseConnectionError("SessionManager is not initialized.")
#         return self._session_manager

#     @property
#     def connected(self) -> bool:
#         return self._connected

#     @abstractmethod
#     async def connect(self) -> None:
#         """
#         Create primary and replica engines.
#         """

#     @abstractmethod
#     async def disconnect(self) -> None:
#         """
#         Dispose engines.
#         """

#     async def start(self) -> None:
#         await self.connect()

#     async def stop(self) -> None:
#         await self.disconnect()

#     @asynccontextmanager
#     async def session(self) -> AsyncIterator[AsyncSession]:
#         async with self.session_manager.session() as session:
#             yield session

#     async def ping(self) -> bool:
#         try:
#             async with self.engine.connect() as conn:
#                 await conn.execute(text("SELECT 1"))
#             return True
#         except Exception:
#             return False

#     async def ping_latency(self) -> float:
#         start = time.perf_counter()
#         success = await self.ping()
#         return (time.perf_counter() - start) * 1000.0 if success else -1.0

#     def _start_telemetry(self) -> None:
#         self._telemetry.instrument_engine(self.engine)
#         if self._replica_engine:
#             self._telemetry.instrument_engine(self._replica_engine)
#         self._telemetry.instrument_session_factory(self.session_manager.factory)

#     async def health(self) -> dict[str, Any]:
#         import datetime
#         from app.core.database.types import HealthStatus

#         latency = await self.ping_latency()
#         connected = latency >= 0

#         status = HealthStatus.HEALTHY
#         if not connected:
#             status = HealthStatus.UNHEALTHY
#         elif latency > 200:
#             status = HealthStatus.DEGRADED

#         if self._engine:
#             self._telemetry.collect_pool_stats(self._engine)

#         stats = self._telemetry.statistics

#         return {
#             "status": status.value,
#             "connected": connected,
#             "latency_ms": round(latency, 2),
#             "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
#             "message": "Database is operational" if connected else "Database connection lost",
#             "statistics": {
#                 "active_connections": stats.active_connections,
#                 "idle_connections": stats.idle_connections,
#                 "total_connections": stats.total_connections,
#                 "checked_out_connections": stats.checked_out_connections,
#                 "overflow_connections": stats.overflow_connections,
#                 "total_transactions": stats.total_transactions,
#                 "committed_transactions": stats.committed_transactions,
#                 "rolled_back_transactions": stats.rolled_back_transactions,
#                 "failed_transactions": stats.failed_transactions,
#                 "retry_count": stats.retry_count,
#                 "timeout_count": stats.timeout_count,
#                 "total_queries": stats.total_queries,
#                 "failed_queries": stats.failed_queries,
#             },
#             "details": {
#                 "driver": self.name,
#             },
#         }


from __future__ import annotations

import time

from abc import ABC
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.interface import DatabaseDriver
from app.core.database.session import SessionManager
from app.core.database.exceptions import DatabaseConnectionError


class BaseDatabaseDriver(DatabaseDriver, ABC):

    __slots__ = (
        "_engine",
        "_replica_engine",
        "_session_manager",
        "_connected",
    )

    def __init__(self) -> None:

        self._engine: AsyncEngine | None = None
        self._replica_engine: AsyncEngine | None = None
        self._session_manager: SessionManager | None = None
        self._connected = False

    # --------------------------------------------------

    @property
    def engine(self) -> AsyncEngine:

        engine = self._engine

        if engine is None:
            raise DatabaseConnectionError()

        return engine

    # --------------------------------------------------

    @property
    def replica_engine(self) -> AsyncEngine:

        return self._replica_engine or self.engine

    # --------------------------------------------------

    @property
    def session_manager(self) -> SessionManager:

        manager = self._session_manager

        if manager is None:
            raise DatabaseConnectionError()

        return manager

    # --------------------------------------------------

    @property
    def connected(self) -> bool:

        return self._connected

    # --------------------------------------------------

    async def start(self) -> None:

        if not self._connected:

            await self.connect()

    # --------------------------------------------------

    async def stop(self) -> None:

        if self._connected:

            await self.disconnect()

    # --------------------------------------------------

    @asynccontextmanager
    async def session(self) -> AsyncIterator[AsyncSession]:

        async with self.session_manager.session() as session:
            yield session

    # --------------------------------------------------

    async def ping(self) -> bool:

        try:

            async with self.engine.connect() as conn:
                await conn.execute(text("SELECT 1"))

            return True

        except Exception:

            return False

    # --------------------------------------------------

    async def ping_latency(self) -> float:

        start = time.perf_counter()

        if not await self.ping():
            return -1

        return (time.perf_counter() - start) * 1000

    async def health(self) -> dict:
        latency = await self.ping_latency()
        connected = latency >= 0
        return {
            "status": "healthy" if connected else "unhealthy",
            "connected": connected,
            "latency_ms": round(latency, 2) if connected else -1.0,
            "message": "Database is operational" if connected else "Database connection lost",
        }