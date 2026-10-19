"""
RealTimeTransfer
================

Enterprise Logger Queue

Python 3.13+
"""

from __future__ import annotations

import logging
from logging.handlers import (
    QueueHandler,
    QueueListener,
)

from queue import Queue


class LoggerQueue:
    """
    High-performance asynchronous logging queue.
    """

    __slots__ = (
        "_queue",
        "_handler",
        "_listener",
    )

    def __init__(
        self,
        maxsize: int = 50_000,
    ) -> None:

        self._queue: Queue[logging.LogRecord] = Queue(
            maxsize=maxsize,
        )

        self._handler = QueueHandler(
            self._queue,
        )

        self._listener: QueueListener | None = None

    # -----------------------------------------------------

    @property
    def handler(
        self,
    ) -> QueueHandler:

        return self._handler

    # -----------------------------------------------------

    @property
    def listener(
        self,
    ) -> QueueListener | None:

        return self._listener

    # -----------------------------------------------------

    def start(
        self,
        *handlers: logging.Handler,
    ) -> None:

        if self._listener is not None:
            return

        self._listener = QueueListener(
            self._queue,
            *handlers,
            respect_handler_level=True,
        )

        self._listener.start()

    # -----------------------------------------------------

    def stop(
        self,
    ) -> None:

        listener = self._listener

        if listener is None:
            return

        listener.stop()

        self._listener = None