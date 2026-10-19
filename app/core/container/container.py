"""
RealTimeTransfer
================

Enterprise Service Container

Python 3.13+
"""

from __future__ import annotations
from threading import RLock
from typing import Any, TypeVar

from app.core.database import DatabaseManager

T = TypeVar("T")


class ServiceNotRegisteredError(LookupError):
    """Raised when a requested service is not registered."""
    pass


class ServiceAlreadyRegisteredError(RuntimeError):
    """Raised when attempting to register an existing service."""
    pass


class ContainerFrozenError(RuntimeError):
    """Raised when attempting to modify a frozen container."""
    pass


class ServiceContainer:
    """
    Application infrastructure container.

    Fast path:
        container.database
        container.cache

    Generic path:
        container.resolve(MQTTClient)
    """

    __slots__ = (
        "database",
        "cache",
        "storage",
        "scheduler",
        "telemetry",
        "event_bus",
        "_services",
        "_lock",
        "_frozen",
    )

    def __init__(self) -> None:
        # Core infrastructure properties (Fastest direct access)
        self.database: DatabaseManager | None = None
        self.cache: Any | None = None
        self.storage: Any | None = None
        self.scheduler: Any | None = None
        self.telemetry: Any | None = None
        self.event_bus: Any | None = None

        # Optional infrastructure dictionary
        self._services: dict[type[Any], Any] = {}
        self._lock = RLock()
        self._frozen = False

    # ---------------------------------------------------------
    # Lifecycle
    # ---------------------------------------------------------

    def freeze(self) -> None:
        """
        Prevent further registrations.
        """
        with self._lock:
            self._frozen = True

    @property
    def frozen(self) -> bool:
        # Read is atomic; no lock needed
        return self._frozen

    # ---------------------------------------------------------
    # Registration
    # ---------------------------------------------------------

    def register(self, service: type[T], instance: T, *, replace: bool = False) -> None:
        """
        Register a service instance. Write operations are thread-safe.
        """
        with self._lock:
            if self._frozen:
                raise ContainerFrozenError()

            if not replace and service in self._services:
                raise ServiceAlreadyRegisteredError(service.__name__)

            self._services[service] = instance

    # ---------------------------------------------------------
    # Resolution
    # ---------------------------------------------------------

    def resolve(self, service: type[T]) -> T:
        """
        Resolve a service instance. Lock-free fast read path for high traffic.
        """
        try:
            return self._services[service]
        except KeyError as exc:
            raise ServiceNotRegisteredError(service.__name__) from exc

    # ---------------------------------------------------------
    # Helpers
    # ---------------------------------------------------------

    def contains(self, service: type[Any]) -> bool:
        """
        Check if a service is registered. Lock-free read path.
        """
        return service in self._services

    def remove(self, service: type[Any]) -> None:
        """
        Remove a registered service. Write operations are thread-safe.
        """
        with self._lock:
            if self._frozen:
                raise ContainerFrozenError()
            self._services.pop(service, None)

    def clear(self) -> None:
        """
        Clear all registered services. Write operations are thread-safe.
        """
        with self._lock:
            if self._frozen:
                raise ContainerFrozenError()
            self._services.clear()

    @property
    def size(self) -> int:
        """
        Get the number of registered services. Lock-free read path.
        """
        return len(self._services)