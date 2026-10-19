"""
RealTimeTransfer
================

Enterprise Event Bus

Python 3.13+
"""

from __future__ import annotations

import asyncio
import json
from dataclasses import asdict, is_dataclass
from typing import Sequence

from app.core.events.base import Event
from app.core.events.dispatcher import (
    DispatchResult,
    EventDispatcher,
)


class EventBus:
    """
    Enterprise Event Bus.

    Public entry point for publishing events. Supports transactional outbox
    integration if running within an active database transaction.
    """

    __slots__ = (
        "_dispatcher",
    )

    def __init__(
        self,
        dispatcher: EventDispatcher,
    ) -> None:
        self._dispatcher = dispatcher

    def _serialize_event(self, event: Event) -> str:
        """
        Helper method to serialize event data to JSON.
        """
        if is_dataclass(event):
            body = asdict(event)
        else:
            body = getattr(event, "__dict__", {})

        try:
            import orjson
            return orjson.dumps(body).decode()
        except ImportError:
            from datetime import datetime
            def default_converter(o):
                if isinstance(o, datetime):
                    return o.isoformat()
                raise TypeError(f"Object of type {o.__class__.__name__} is not JSON serializable")
            return json.dumps(body, default=default_converter)

    async def publish(
        self,
        event: Event,
    ) -> DispatchResult:
        """
        Publish a single event. If an active transaction exists,
        diverts the event to the transactional outbox.
        """
        try:
            from app.core.database import database
            tx_manager = database.transactions
            if tx_manager.current is not None:
                # Active transaction found! Divert event to outbox repository
                session = tx_manager.session
                from app.core.database.outbox import OutboxRepository
                outbox_repo = OutboxRepository(session)
                
                payload_json = self._serialize_event(event)
                await outbox_repo.add_event(
                    event_type=type(event).__name__,
                    payload_json=payload_json,
                )

                return DispatchResult(
                    event=event,
                    success=True,
                    duration=0.0,
                    handlers=0,
                )
        except (ImportError, RuntimeError):
            pass

        return await self._dispatcher.dispatch(event)

    async def publish_many(
        self,
        *events: Event,
    ) -> list[DispatchResult]:
        """
        Publish multiple events.
        Leverages single bulk inserts on active database transactions,
        or dispatches events concurrently using asyncio.gather otherwise.
        """
        if not events:
            return []

        try:
            from app.core.database import database
            tx_manager = database.transactions
            if tx_manager.current is not None:
                session = tx_manager.session
                from app.core.database.outbox import OutboxRepository
                outbox_repo = OutboxRepository(session)

                serialized_events = [
                    (type(ev).__name__, self._serialize_event(ev))
                    for ev in events
                ]
                await outbox_repo.add_events(serialized_events)

                return [
                    DispatchResult(
                        event=event,
                        success=True,
                        duration=0.0,
                        handlers=0,
                    )
                    for event in events
                ]
        except (ImportError, RuntimeError):
            pass

        # Dispatches events concurrently when non-transactional
        tasks = [self._dispatcher.dispatch(event) for event in events]
        return list(await asyncio.gather(*tasks))