"""
RealTimeTransfer
================

Enterprise Event Handler Interface

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from app.core.events.base import Event


class EventHandler(ABC):
    """
    Interface for all event handlers.
    """

    # If True, the handler is executed in the background without blocking the dispatcher response.
    async_run: bool = False

    @abstractmethod
    async def handle(self, event: Event) -> None:
        """
        Handle the domain event.
        """
        ...