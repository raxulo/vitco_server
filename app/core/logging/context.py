"""
Request Scoped Logging Context

Python 3.13+
"""

from __future__ import annotations

from contextvars import ContextVar
from dataclasses import dataclass


@dataclass(slots=True)
class LogContext:
    request_id: str = "-"
    user_id: str = "-"
    ip: str = "-"
    path: str = "-"

_CONTEXT: ContextVar[LogContext] = ContextVar("log_context",default=LogContext())


class LoggerContext:
    __slots__ = ()
    
    @staticmethod
    def get() -> LogContext:
        return _CONTEXT.get()

    @staticmethod
    def set(context: LogContext):
        return _CONTEXT.set(context)

    @staticmethod
    def reset(token):
        _CONTEXT.reset(token)

    @staticmethod
    def clear():
        _CONTEXT.set(LogContext())