"""
RealTimeTransfer
================

Enterprise Logging Manager

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import logging

from app.core.lifecycle.service import LifecycleService

from app.core.logging.handlers import LoggingHandlers
from app.core.logging.queue import LoggingQueue


class LoggingManager(
    LifecycleService,
):
    """
    Enterprise Logging Bootstrap.

    Responsibilities
    ----------------

    • Configure logging

    • Create handlers

    • Start queue listener

    • Configure root logger

    • Graceful shutdown
    """

    priority = 5

    __slots__ = (
        "_application",
        "_level",
        "_started",
    )

    def __init__(
        self,
        *,
        application: str,
        level: int = logging.INFO,
    ) -> None:

        self._application = application

        self._level = level

        self._started = False

    @property
    def started(
        self,
    ) -> bool:

        return self._started

    async def start(
        self,
    ) -> None:

        if self._started:
            return

        #
        # Create handlers
        #

        console = LoggingHandlers.console(

            application=self._application,

            level=self._level,
        )

        application = LoggingHandlers.rotating_file(

            application=self._application,

            file="logs/application.log",

            level=self._level,
        )

        error = LoggingHandlers.error_file(

            application=self._application,

            file="logs/error.log",
        )

        #
        # Start queue
        #

        LoggingQueue.start(

            console,

            application,

            error,
        )

        #
        # Configure root logger
        #

        root = logging.getLogger()

        root.handlers.clear()

        root.setLevel(self._level)

        root.addHandler(

            LoggingQueue.handler()
        )

        self._started = True

    async def stop(
        self,
    ) -> None:

        if not self._started:
            return

        LoggingQueue.stop()

        logging.shutdown()

        self._started = False