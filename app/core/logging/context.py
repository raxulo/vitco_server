"""
RealTimeTransfer
================

Enterprise Logging Context

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import uuid

from contextvars import (
    ContextVar,
    Token,
)
from dataclasses import dataclass


@dataclass(slots=True)
class LogContext:

    request_id: str

    trace_id: str

    correlation_id: str

    user_id: str | None = None

    tenant_id: str | None = None

    session_id: str | None = None

    ip: str | None = None


_CURRENT_CONTEXT: ContextVar[
    LogContext | None
] = ContextVar(

    "logging_context",

    default=None,
)


class LoggingContext:

    __slots__ = ()

    @staticmethod
    def create(

        *,

        request_id: str | None = None,

        trace_id: str | None = None,

        correlation_id: str | None = None,

        user_id: str | None = None,

        tenant_id: str | None = None,

        session_id: str | None = None,

        ip: str | None = None,

    ) -> Token:

        context = LogContext(

            request_id=request_id or uuid.uuid4().hex,

            trace_id=trace_id or uuid.uuid4().hex,

            correlation_id=correlation_id or uuid.uuid4().hex,

            user_id=user_id,

            tenant_id=tenant_id,

            session_id=session_id,

            ip=ip,
        )

        return _CURRENT_CONTEXT.set(
            context
        )

    @staticmethod
    def current() -> LogContext | None:

        return _CURRENT_CONTEXT.get()

    @staticmethod
    def reset(
        token: Token,
    ) -> None:

        _CURRENT_CONTEXT.reset(
            token
        )

    @staticmethod
    def update(
        **kwargs,
    ) -> None:

        context = _CURRENT_CONTEXT.get()

        if context is None:
            return

        for key, value in kwargs.items():

            if hasattr(context, key):

                setattr(
                    context,
                    key,
                    value,
                )