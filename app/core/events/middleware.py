"""
RealTimeTransfer
================

Enterprise Event Middleware

Python 3.13+
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from collections.abc import Awaitable
from collections.abc import Callable

from app.core.events.base import Event


Next = Callable[[Event], Awaitable[None]]


class EventMiddleware(ABC):
    """
    Base event middleware.
    """

    @abstractmethod
    async def invoke(
        self,
        event: Event,
        next_handler: Next,
    ) -> None:
        ...


import time


class LoggingMiddleware(
    EventMiddleware,
):

    async def invoke(

        self,

        event,

        next_handler,

    ):

        started = time.perf_counter()

        print(
            f"Start {type(event).__name__}"
        )

        await next_handler(
            event
        )

        elapsed = (

            time.perf_counter()

            - started
        )

        print(

            f"Finished {elapsed:.3f}s"
        )

class MetricsMiddleware(
    EventMiddleware,
):

    async def invoke(

        self,

        event,

        next_handler,

    ):

        #
        # Increment Counter
        #

        await next_handler(
            event
        )

        #
        # Record Metrics
        #

class TracingMiddleware(
    EventMiddleware,
):

    async def invoke(

        self,

        event,

        next_handler,

    ):

        #
        # Start Span
        #

        await next_handler(
            event
        )

        #
        # Finish Span
        #

import uuid


class CorrelationMiddleware(
    EventMiddleware,
):

    async def invoke(

        self,

        event,

        next_handler,

    ):

        if not hasattr(

            event,

            "correlation_id",

        ):

            event.correlation_id = (

                uuid.uuid4().hex
            )

        await next_handler(
            event
        )