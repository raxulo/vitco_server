"""
RealTimeTransfer
================

Enterprise Distributed Tracing

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import time
import uuid

from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass, field


@dataclass(slots=True)
class Span:

    trace_id: str

    span_id: str

    parent_id: str | None

    operation: str

    started: float

    ended: float | None = None

    duration_ms: float | None = None


_CURRENT_SPAN: ContextVar[
    Span | None
] = ContextVar(

    "current_span",

    default=None,
)


class Tracer:

    __slots__ = ()

    @staticmethod
    def trace_id() -> str:

        return uuid.uuid4().hex

    @staticmethod
    def span_id() -> str:

        return uuid.uuid4().hex[:16]

    @contextmanager
    def start_span(
        self,
        operation: str,
    ):

        parent = _CURRENT_SPAN.get()

        span = Span(

            trace_id=(
                parent.trace_id
                if parent
                else self.trace_id()
            ),

            span_id=self.span_id(),

            parent_id=(
                parent.span_id
                if parent
                else None
            ),

            operation=operation,

            started=time.perf_counter(),
        )

        token = _CURRENT_SPAN.set(span)

        try:

            yield span

        finally:

            span.ended = time.perf_counter()

            span.duration_ms = (

                span.ended
                - span.started

            ) * 1000

            _CURRENT_SPAN.reset(token)

    @property
    def current(
        self,
    ) -> Span | None:

        return _CURRENT_SPAN.get()


tracer = Tracer()