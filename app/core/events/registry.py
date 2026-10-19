"""
RealTimeTransfer
================

Enterprise Event Registry

Python 3.13+
"""

from __future__ import annotations

import threading
from collections import defaultdict
from collections.abc import Iterable

from app.core.events.base import Event
from app.core.events.handler import EventHandler


class EventRegistry:
    """
    Thread-safe registry for event handlers.
    """

    __slots__ = (
        "_handlers",
        "_lock",
    )

    def __init__(self) -> None:
        self._handlers: dict[
            type[Event],
            list[type[EventHandler]],
        ] = defaultdict(list)
        self._lock = threading.RLock()

    def subscribe(
        self,
        event_type: type[Event],
        handler: type[EventHandler],
    ) -> None:
        """
        Subscribe a handler class to an event type.
        """
        with self._lock:
            handlers = self._handlers[event_type]
            if handler in handlers:
                return
            handlers.append(handler)

    def unsubscribe(
        self,
        event_type: type[Event],
        handler: type[EventHandler],
    ) -> None:
        """
        Unsubscribe a handler class from an event type.
        """
        with self._lock:
            handlers = self._handlers.get(event_type)
            if handlers is None:
                return

            try:
                handlers.remove(handler)
            except ValueError:
                return

            if not handlers:
                del self._handlers[event_type]

    def handlers(
        self,
        event_type: type[Event],
    ) -> tuple[type[EventHandler], ...]:
        """
        Get all handler classes subscribed to the given event type.
        """
        with self._lock:
            return tuple(self._handlers.get(event_type, ()))

    def registered_events(self) -> Iterable[type[Event]]:
        """
        Get all event types that have registered subscriptions.
        """
        with self._lock:
            return tuple(self._handlers.keys())

    def clear(self) -> None:
        """
        Clear all event subscriptions.
        """
        with self._lock:
            self._handlers.clear()