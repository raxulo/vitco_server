"""
RealTimeTransfer Core Infrastructure
===================================

Google, Microsoft, Uber, Netflix scale architecture primitives.

Python 3.13+
"""

from __future__ import annotations

from app.core.cqrs import (
    Command,
    Query,
    CommandHandler,
    QueryHandler,
    Mediator,
)
from app.core.tracing import TraceContext
from app.core.idempotency import IdempotencyEngine

__all__ = (
    "Command",
    "Query",
    "CommandHandler",
    "QueryHandler",
    "Mediator",
    "TraceContext",
    "IdempotencyEngine",
)
