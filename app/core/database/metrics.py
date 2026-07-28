"""
RealTimeTransfer
================

Enterprise Database Telemetry & Metrics Instrumentation

Tracks connection pools, transaction success rates, and query latencies.

Python 3.13+
"""

from __future__ import annotations

import time
from threading import Lock
from typing import Any

from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncEngine

from app.core.database.types import DatabaseStatistics


class DatabaseMetricsCollector:
    """
    Enterprise-grade Thread-Safe telemetry and metrics collector for SQLAlchemy.
    """

    __slots__ = (
        "_lock",
        "_stats",
    )

    def __init__(self) -> None:
        self._lock = Lock()
        self._stats = DatabaseStatistics()

    @property
    def statistics(self) -> DatabaseStatistics:
        """
        Retrieve a snapshot of the current database statistics.
        """
        with self._lock:
            return DatabaseStatistics(
                active_connections=self._stats.active_connections,
                idle_connections=self._stats.idle_connections,
                total_connections=self._stats.total_connections,
                checked_out_connections=self._stats.checked_out_connections,
                overflow_connections=self._stats.overflow_connections,
                total_transactions=self._stats.total_transactions,
                committed_transactions=self._stats.committed_transactions,
                rolled_back_transactions=self._stats.rolled_back_transactions,
                failed_transactions=self._stats.failed_transactions,
                retry_count=self._stats.retry_count,
                timeout_count=self._stats.timeout_count,
                total_queries=self._stats.total_queries,
                failed_queries=self._stats.failed_queries,
            )

    def instrument_engine(self, engine: AsyncEngine) -> None:
        """
        Instruments a SQLAlchemy engine with metric listeners.
        """
        sync_engine = engine.sync_engine

        @event.listens_for(sync_engine, "connect")
        def on_connect(dbapi_connection, connection_record) -> None:
            with self._lock:
                self._stats.total_connections += 1

        @event.listens_for(sync_engine, "before_cursor_execute")
        def before_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ) -> None:
            if context:
                context.info["query_start_time"] = time.perf_counter()

        @event.listens_for(sync_engine, "after_cursor_execute")
        def after_cursor_execute(
            conn, cursor, statement, parameters, context, executemany
        ) -> None:
            with self._lock:
                self._stats.total_queries += 1

        @event.listens_for(sync_engine, "handle_error")
        def handle_error(exception_context) -> None:
            with self._lock:
                self._stats.failed_queries += 1

    def instrument_session_factory(self, session_factory: Any) -> None:
        """
        Instruments session commit/rollback events to monitor transactions.
        """
        @event.listens_for(session_factory, "after_commit")
        def on_commit(session) -> None:
            with self._lock:
                self._stats.committed_transactions += 1
                self._stats.total_transactions += 1

        @event.listens_for(session_factory, "after_rollback")
        def on_rollback(session) -> None:
            with self._lock:
                self._stats.rolled_back_transactions += 1
                self._stats.total_transactions += 1

    def collect_pool_stats(self, engine: AsyncEngine) -> None:
        """
        Dynamically extracts connection pool metrics from SQLAlchemy engine.
        """
        pool = engine.sync_engine.pool
        with self._lock:
            try:
                self._stats.checked_out_connections = pool.checkedout()
                self._stats.idle_connections = pool.checkedin()
                self._stats.active_connections = (
                    pool.checkedout() + pool.checkedin()
                )
                if hasattr(pool, "overflow"):
                    self._stats.overflow_connections = pool.overflow()
            except (AttributeError, NotImplementedError):
                pass
