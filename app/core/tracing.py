"""
RealTimeTransfer
================

Enterprise Distributed Tracing Context (Google Dapper / Uber Jaeger Architecture)

Propagates trace_id and correlation_id across async execution trees using ContextVars.

Python 3.13+
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar
from typing import Optional

_trace_id_ctx: ContextVar[Optional[str]] = ContextVar("trace_id", default=None)
_correlation_id_ctx: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


class TraceContext:
    """
    ContextVar wrapper for zero-parameter propagation of Distributed Tracing identifiers.
    """

    @staticmethod
    def get_trace_id() -> str:
        """
        Get or generate current trace_id.
        """
        tid = _trace_id_ctx.get()
        if tid is None:
            tid = str(uuid.uuid4())
            _trace_id_ctx.set(tid)
        return tid

    @staticmethod
    def set_trace_id(trace_id: str) -> None:
        """
        Explicitly set trace_id for current request context.
        """
        _trace_id_ctx.set(trace_id)

    @staticmethod
    def get_correlation_id() -> str:
        """
        Get or generate current correlation_id.
        """
        cid = _correlation_id_ctx.get()
        if cid is None:
            cid = str(uuid.uuid4())
            _correlation_id_ctx.set(cid)
        return cid

    @staticmethod
    def set_correlation_id(correlation_id: str) -> None:
        """
        Explicitly set correlation_id for current request context.
        """
        _correlation_id_ctx.set(correlation_id)

    @staticmethod
    def current() -> dict[str, str]:
        """
        Retrieve active trace dictionary.
        """
        return {
            "trace_id": TraceContext.get_trace_id(),
            "correlation_id": TraceContext.get_correlation_id(),
        }
