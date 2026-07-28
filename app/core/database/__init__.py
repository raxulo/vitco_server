"""
RealTimeTransfer
================

Enterprise Database Layer Entrypoint.

Exposes the unified Database Manager, Specifications, Outbox, and Resilience patterns.

Python 3.13+
"""

from __future__ import annotations

from app.core.database.factory import database
from app.core.database.manager import DatabaseManager
from app.core.database.unit_of_work import UnitOfWork
from app.core.database.repository.base import BaseRepository
from app.core.database.specification import Specification
from app.core.database.outbox import OutboxMessage, OutboxRepository
from app.core.database.circuit_breaker import (
    DatabaseCircuitBreaker,
    CircuitBreakerOpenError,
)

__all__ = (
    "database",
    "DatabaseManager",
    "UnitOfWork",
    "BaseRepository",
    "Specification",
    "OutboxMessage",
    "OutboxRepository",
    "DatabaseCircuitBreaker",
    "CircuitBreakerOpenError",
)
