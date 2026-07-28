"""
RealTimeTransfer
================

Enterprise Database Types

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any


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