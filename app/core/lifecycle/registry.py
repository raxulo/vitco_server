"""
RealTimeTransfer
================

Lifecycle Service Registry

Enterprise Service Registry

Python 3.13
"""

from __future__ import annotations

from collections.abc import Iterator

from app.core.lifecycle.service import LifecycleService


class LifecycleRegistry:
    """
    Enterprise Service Registry.

    Responsibilities
    ----------------
    • Register services
    • Prevent duplicate registration
    • Sort services by priority
    • Expose startup order
    • Expose shutdown order
    """

    __slots__ = ("_services",)

    def __init__(self) -> None:
        self._services: dict[str, LifecycleService] = {}

    def register(
        self,
        service: LifecycleService,
    ) -> None:
        """
        Register a lifecycle service.
        """

        if service.name in self._services:
            raise ValueError(
                f"Service '{service.name}' already registered."
            )

        self._services[service.name] = service

    def unregister(
        self,
        service_name: str,
    ) -> None:
        """
        Remove a service.
        """

        self._services.pop(service_name, None)

    def get(
        self,
        service_name: str,
    ) -> LifecycleService:
        """
        Return registered service.
        """

        return self._services[service_name]

    def exists(
        self,
        service_name: str,
    ) -> bool:
        return service_name in self._services

    @property
    def startup(self) -> list[LifecycleService]:
        """
        Startup order.
        """

        return sorted(
            self._services.values(),
            key=lambda service: service.priority,
        )

    @property
    def shutdown(self) -> list[LifecycleService]:
        """
        Shutdown order.
        """

        return list(reversed(self.startup))

    def clear(self) -> None:
        """
        Remove all services.
        """

        self._services.clear()

    def __len__(self) -> int:
        return len(self._services)

    def __iter__(self) -> Iterator[LifecycleService]:
        return iter(self.startup)


registry = LifecycleRegistry()