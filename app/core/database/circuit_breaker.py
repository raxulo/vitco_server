"""
RealTimeTransfer
================

Enterprise Database Circuit Breaker Pattern

Prevents cascading outages under high load or network partitions.

Python 3.13+
"""

from __future__ import annotations

import time
from enum import Enum
from threading import Lock
from typing import Callable, TypeVar, Awaitable

T = TypeVar("T")


class CircuitState(str, Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


class CircuitBreakerOpenError(Exception):
    """
    Raised when an operation is executed while the circuit breaker is OPEN.
    """


class DatabaseCircuitBreaker:
    """
    Thread-safe Circuit Breaker for database queries and transactions.
    """

    __slots__ = (
        "_failure_threshold",
        "_recovery_time_sec",
        "_failure_count",
        "_last_failure_time",
        "_state",
        "_lock",
    )

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_time_sec: float = 30.0,
    ) -> None:
        self._failure_threshold = failure_threshold
        self._recovery_time_sec = recovery_time_sec
        self._failure_count = 0
        self._last_failure_time = 0.0
        self._state = CircuitState.CLOSED
        self._lock = Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            self._evaluate_state()
            return self._state

    def _evaluate_state(self) -> None:
        if self._state == CircuitState.OPEN:
            if time.time() - self._last_failure_time >= self._recovery_time_sec:
                self._state = CircuitState.HALF_OPEN

    async def execute(self, action: Callable[[], Awaitable[T]]) -> T:
        """
        Executes an async database action protected by circuit breaker rules.
        """
        with self._lock:
            self._evaluate_state()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerOpenError(
                    "Circuit breaker is OPEN. Database operations suspended for "
                    f"{self._recovery_time_sec}s."
                )

        try:
            result = await action()
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self._failure_threshold:
                self._state = CircuitState.OPEN
