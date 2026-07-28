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
            list[EventHandler],
        ] = defaultdict(list)

        self._lock = threading.RLock()

    # -------------------------------------------------

    def subscribe(
        self,
        event_type: type[Event],
        handler: EventHandler,
    ) -> None:

        with self._lock:

            handlers = self._handlers[event_type]

            if handler in handlers:
                return

            handlers.append(handler)

    # -------------------------------------------------

    def unsubscribe(
        self,
        event_type: type[Event],
        handler: EventHandler,
    ) -> None:

        with self._lock:

            handlers = self._handlers.get(
                event_type
            )

            if handlers is None:
                return

            try:
                handlers.remove(handler)

            except ValueError:
                return

            if not handlers:

                del self._handlers[event_type]

    # -------------------------------------------------

    def handlers(
        self,
        event_type: type[Event],
    ) -> tuple[EventHandler, ...]:

        with self._lock:

            return tuple(

                self._handlers.get(
                    event_type,
                    (),
                )
            )

    # -------------------------------------------------

    def registered_events(
        self,
    ) -> Iterable[type[Event]]:

        with self._lock:

            return tuple(
                self._handlers.keys()
            )

    # -------------------------------------------------

    def clear(
        self,
    ) -> None:

        with self._lock:

            self._handlers.clear()