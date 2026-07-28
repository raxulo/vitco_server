"""
RealTimeTransfer
================

Enterprise Event Bus

Python 3.13+
"""

from __future__ import annotations

from app.core.events.base import Event
from app.core.events.dispatcher import (
    DispatchResult,
    EventDispatcher,
)


class EventBus:
    """
    Enterprise Event Bus.

    Public entry point for publishing events.
    """

    __slots__ = (
        "_dispatcher",
    )

    def __init__(
        self,
        dispatcher: EventDispatcher,
    ) -> None:

        self._dispatcher = dispatcher

    # -------------------------------------------------

    async def publish(
        self,
        event: Event,
    ) -> DispatchResult:

        return await self._dispatcher.dispatch(
            event
        )

    # -------------------------------------------------

    async def publish_many(
        self,
        *events: Event,
    ) -> list[DispatchResult]:

        results: list[DispatchResult] = []

        for event in events:

            result = await self.publish(
                event
            )

            results.append(result)

        return results