"""
RealTimeTransfer
================

Enterprise Event Dispatcher

Google / Uber / Microsoft Style

Python 3.13+
"""

from __future__ import annotations

import asyncio
import time

from dataclasses import dataclass, field

from app.core.container.container import Container
from app.core.events.base import Event
from app.core.events.registry import EventRegistry


# ============================================================
# Result
# ============================================================

@dataclass(slots=True)
class DispatchResult:

    event: Event

    success: bool

    duration: float

    handlers: int

    exceptions: list[Exception] = field(
        default_factory=list
    )


# ============================================================
# Dispatcher
# ============================================================

class EventDispatcher:

    __slots__ = (

        "_container",

        "_registry",
    )

    def __init__(

        self,

        container: Container,

        registry: EventRegistry,

    ):

        self._container = container

        self._registry = registry

    # -------------------------------------------------------

    async def dispatch(

        self,

        event: Event,

    ) -> DispatchResult:

        started = time.perf_counter()

        exceptions: list[Exception] = []

        handlers = self._registry.handlers(

            type(event)
        )

        if not handlers:

            return DispatchResult(

                event=event,

                success=True,

                duration=0,

                handlers=0,
            )

        tasks = [

            self._run(

                handler,

                event,

                exceptions,
            )

            for handler in handlers
        ]

        await asyncio.gather(

            *tasks,

            return_exceptions=True,
        )

        return DispatchResult(

            event=event,

            success=not exceptions,

            duration=(
                time.perf_counter()
                - started
            ),

            handlers=len(handlers),

            exceptions=exceptions,
        )

    # -------------------------------------------------------

    async def _run(

        self,

        handler,

        event,

        exceptions,

    ):

        try:

            #
            # DI
            #

            instance = self._container.resolve(
                handler
            )

            await instance.handle(
                event
            )

        except Exception as exc:

            exceptions.append(exc)