"""
RealTimeTransfer
================

Enterprise Logging Metrics

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass


@dataclass(slots=True)
class LoggingSnapshot:

    processed_logs: int

    dropped_logs: int

    formatter_errors: int

    handler_errors: int

    queue_size: int

    queue_capacity: int

    startup_time: float

    uptime: float


class LoggingMetrics:

    """
    Thread-safe metrics collector.
    """

    __slots__ = (
        "_processed",
        "_dropped",
        "_formatter_errors",
        "_handler_errors",
        "_queue_size",
        "_queue_capacity",
        "_started",
        "_lock",
    )

    def __init__(
        self,
        *,
        queue_capacity: int,
    ) -> None:

        self._processed = 0

        self._dropped = 0

        self._formatter_errors = 0

        self._handler_errors = 0

        self._queue_size = 0

        self._queue_capacity = queue_capacity

        self._started = time.monotonic()

        self._lock = threading.Lock()

    def increment_processed(self) -> None:

        with self._lock:

            self._processed += 1

    def increment_dropped(self) -> None:

        with self._lock:

            self._dropped += 1

    def increment_formatter_error(self) -> None:

        with self._lock:

            self._formatter_errors += 1

    def increment_handler_error(self) -> None:

        with self._lock:

            self._handler_errors += 1

    def update_queue_size(
        self,
        size: int,
    ) -> None:

        with self._lock:

            self._queue_size = size

    @property
    def snapshot(
        self,
    ) -> LoggingSnapshot:

        with self._lock:

            return LoggingSnapshot(

                processed_logs=self._processed,

                dropped_logs=self._dropped,

                formatter_errors=self._formatter_errors,

                handler_errors=self._handler_errors,

                queue_size=self._queue_size,

                queue_capacity=self._queue_capacity,

                startup_time=self._started,

                uptime=time.monotonic() - self._started,
            )