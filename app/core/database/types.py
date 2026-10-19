"""
RealTimeTransfer
================

Enterprise Database Types

Python 3.13+
"""

from __future__ import annotations

import uuid

from sqlalchemy import String
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, NewType
from uuid import UUID
from sqlalchemy.types import (
    TypeDecorator,
)

__all__ = (
    "GUID",
)

RequestId = NewType("RequestId", UUID)

TraceId = NewType("TraceId", UUID)

SpanId = NewType("SpanId", UUID)

CorrelationId = NewType("CorrelationId", UUID)

TransactionId = NewType("TransactionId", UUID)

SessionId = NewType("SessionId", UUID)

QueryId = NewType("QueryId", UUID)

TenantId = NewType("TenantId", UUID)

ConnectionId = NewType("ConnectionId", UUID)


# ==========================================================
# Database Driver
# ==========================================================

class DatabaseDriver(str, Enum):
    """
    Supported database drivers.
    """

    SQLITE = "sqlite"

    POSTGRESQL = "postgresql"

    COCKROACH = "cockroach"


# ==========================================================
# Health Status
# ==========================================================

class HealthStatus(str, Enum):
    """
    Database health state.
    """

    HEALTHY = "healthy"

    DEGRADED = "degraded"

    UNHEALTHY = "unhealthy"


# ==========================================================
# Transaction State
# ==========================================================

class TransactionState(str, Enum):
    """
    Transaction lifecycle.
    """

    CREATED = "created"

    STARTED = "started"

    COMMITTED = "committed"

    ROLLED_BACK = "rolled_back"

    FAILED = "failed"

    TIMEOUT = "timeout"


# ==========================================================
# Connection Info
# ==========================================================

@dataclass(slots=True)
class ConnectionInfo:
    """
    Database connection information.
    """

    driver: DatabaseDriver

    url: str

    database: str

    host: str | None = None

    port: int | None = None

    username: str | None = None


# ==========================================================
# Database Statistics
# ==========================================================

@dataclass(slots=True)
class DatabaseStatistics:
    """
    Runtime database statistics.
    """

    active_connections: int = 0

    idle_connections: int = 0

    total_connections: int = 0

    checked_out_connections: int = 0

    overflow_connections: int = 0

    total_transactions: int = 0

    committed_transactions: int = 0

    rolled_back_transactions: int = 0

    failed_transactions: int = 0

    retry_count: int = 0

    timeout_count: int = 0

    total_queries: int = 0

    failed_queries: int = 0


# ==========================================================
# Database Health
# ==========================================================

@dataclass(slots=True)
class DatabaseHealth:
    """
    Database health report.
    """

    status: HealthStatus

    connected: bool

    latency_ms: float

    timestamp: datetime

    message: str = ""

    statistics: DatabaseStatistics = field(
        default_factory=DatabaseStatistics,
    )

    details: dict[str, Any] = field(
        default_factory=dict,
    )


# ==========================================================
# Query Result
# ==========================================================

@dataclass(slots=True)
class QueryResult:
    """
    Generic query metadata.
    """

    success: bool

    execution_time_ms: float

    affected_rows: int = 0

    message: str = ""


# ==========================================================
# Retry Information
# ==========================================================

@dataclass(slots=True)
class RetryInformation:
    """
    Retry execution details.
    """

    attempts: int

    max_attempts: int

    delay: float

    last_exception: str | None = None



class GUID(
    TypeDecorator,
):
    """
    Platform independent UUID type.

    Supports:

    PostgreSQL:
        UUID

    SQLite/MySQL:
        CHAR(36)
    """


    impl = String(36)


    cache_ok = True


    # ---------------------------------------------------------

    def process_bind_param(
        self,
        value: uuid.UUID | str | None,
        dialect: Any,
    ) -> str | None:

        if value is None:

            return None


        if isinstance(
            value,
            uuid.UUID,
        ):

            return str(value)


        return str(
            uuid.UUID(value)
        )


    # ---------------------------------------------------------

    def process_result_value(
        self,
        value: str | None,
        dialect: Any,
    ) -> uuid.UUID | None:


        if value is None:

            return None


        return uuid.UUID(
            value
        )