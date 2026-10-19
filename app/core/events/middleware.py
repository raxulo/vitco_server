"""
RealTimeTransfer
================

Enterprise Event Middleware

Python 3.13+
"""

from __future__ import annotations

import time
import uuid
from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable

from app.core.events.base import Event
from app.core.logging.logger import logger

Next = Callable[[Event], Awaitable[None]]


class EventMiddleware(ABC):
    """
    Base class for all event middlewares in the pipeline.
    """

    @abstractmethod
    async def invoke(
        self,
        event: Event,
        next_handler: Next,
    ) -> None:
        """
        Invoke middleware logic and delegate to next_handler in the pipeline.
        """
        ...


class LoggingMiddleware(EventMiddleware):
    """
    Middleware that logs event processing lifecycle and performance.
    """

    async def invoke(
        self,
        event: Event,
        next_handler: Next,
    ) -> None:
        started = time.perf_counter()
        logger.info(
            "Event processing started. Event: %s, ID: %s",
            type(event).__name__,
            event.event_id,
        )

        try:
            await next_handler(event)
            elapsed = time.perf_counter() - started
            logger.success(
                "Event processing succeeded. Event: %s, ID: %s, Duration: %.3fs",
                type(event).__name__,
                event.event_id,
                elapsed,
            )
        except Exception as exc:
            elapsed = time.perf_counter() - started
            logger.error(
                "Event processing failed. Event: %s, ID: %s, Duration: %.3fs, Error: %s",
                type(event).__name__,
                event.event_id,
                elapsed,
                str(exc),
            )
            raise


class MetricsMiddleware(EventMiddleware):
    """
    Middleware for registering operational metrics.
    """

    async def invoke(
        self,
        event: Event,
        next_handler: Next,
    ) -> None:
        # Placeholder for OpenTelemetry / Prometheus metric collection
        # e.g., metrics.increment("events_published", tags={"event": type(event).__name__})
        await next_handler(event)


class TracingMiddleware(EventMiddleware):
    """
    Middleware for distributed tracing (OpenTelemetry span).
    """

    async def invoke(
        self,
        event: Event,
        next_handler: Next,
    ) -> None:
        # Placeholder for distributed tracing context propagation
        # with tracer.start_as_current_span(f"Event {type(event).__name__}"):
        await next_handler(event)


class CorrelationMiddleware(EventMiddleware):
    """
    Middleware ensuring every event carries a unique Correlation ID.
    """

    async def invoke(
        self,
        event: Event,
        next_handler: Next,
    ) -> None:
        if not hasattr(event, "correlation_id"):
            setattr(event, "correlation_id", uuid.uuid4().hex)

        await next_handler(event)