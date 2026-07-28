"""
RealTimeTransfer
================

Enterprise Logging Queue

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import atexit
import logging
from logging.handlers import (
    QueueHandler,
    QueueListener,
)
from queue import Queue
from threading import RLock


class LoggingQueue:

    """
    Singleton Queue Listener.

    One Queue

    One Listener

    Unlimited Loggers
    """

    __slots__ = ()

    _queue: Queue | None = None

    _listener: QueueListener | None = None

    _lock = RLock()

    @classmethod
    def start(
        cls,
        *handlers: logging.Handler,
    ) -> None:

        if cls._listener is not None:
            return

        with cls._lock:

            if cls._listener is not None:
                return

            cls._queue = Queue(
                maxsize=50000
            )

            cls._listener = QueueListener(

                cls._queue,

                *handlers,

                respect_handler_level=True,
            )

            cls._listener.start()

            atexit.register(
                cls.stop
            )

    @classmethod
    def stop(
        cls,
    ) -> None:

        with cls._lock:

            if cls._listener is None:
                return

            cls._listener.stop()

            cls._listener = None

            cls._queue = None

    @classmethod
    def handler(
        cls,
    ) -> QueueHandler:

        if cls._queue is None:

            raise RuntimeError(

                "LoggingQueue not started."
            )

        return QueueHandler(
            cls._queue
        )