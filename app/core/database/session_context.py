"""
RealTimeTransfer
================

Session Context Holder using ContextVars.

Python 3.13+
"""

from __future__ import annotations

from contextvars import ContextVar
from typing import Any, Callable

# Context var storing a callable that resolves the database session lazily.
_SESSION_RESOLVER: ContextVar[Callable[[], Any] | None] = ContextVar(
    "session_resolver",
    default=None,
)


class SessionContext:
    """
    Context Manager helper for request-scoped database session access.
    """

    __slots__ = ()

    @staticmethod
    def set(resolver: Callable[[], Any]) -> Any:
        return _SESSION_RESOLVER.set(resolver)

    @staticmethod
    def reset(token: Any) -> None:
        _SESSION_RESOLVER.reset(token)

    @staticmethod
    def exists() -> bool:
        return _SESSION_RESOLVER.get() is not None

    @staticmethod
    def get() -> Any:
        resolver = _SESSION_RESOLVER.get()
        if resolver is None:
            raise RuntimeError("No active session context.")
        return resolver()
