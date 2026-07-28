"""
RealTimeTransfer
================

Dependency Injection Registry

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Iterator

from app.core.container.provider import ServiceProvider
from app.core.container.exceptions import (
    ProviderAlreadyRegisteredError,
    ProviderNotFoundError,
)


class ProviderRegistry:
    """
    Stores all registered service providers.
    """

    __slots__ = (
        "_providers",
    )

    def __init__(self) -> None:

        self._providers: dict[
            type,
            ServiceProvider,
        ] = {}

    # --------------------------------------------------
    # Register
    # --------------------------------------------------

    def register(
        self,
        provider: ServiceProvider,
    ) -> None:

        service = provider.service_type

        if service in self._providers:

            raise ProviderAlreadyRegisteredError(
                f"{service.__name__} already registered."
            )

        self._providers[service] = provider

    # --------------------------------------------------
    # Replace
    # --------------------------------------------------

    def replace(
        self,
        provider: ServiceProvider,
    ) -> None:

        self._providers[
            provider.service_type
        ] = provider

    # --------------------------------------------------
    # Remove
    # --------------------------------------------------

    def remove(
        self,
        service: type,
    ) -> None:

        self._providers.pop(
            service,
            None,
        )

    # --------------------------------------------------
    # Lookup
    # --------------------------------------------------

    def get(
        self,
        service: type,
    ) -> ServiceProvider:

        provider = self._providers.get(
            service,
        )

        if provider is None:

            raise ProviderNotFoundError(
                f"{service.__name__} is not registered."
            )

        return provider

    def contains(
        self,
        service: type,
    ) -> bool:

        return service in self._providers

    # --------------------------------------------------
    # Utilities
    # --------------------------------------------------

    def clear(self) -> None:

        self._providers.clear()

    def __len__(self) -> int:

        return len(self._providers)

    def __contains__(
        self,
        service: type,
    ) -> bool:

        return service in self._providers

    def __iter__(
        self,
    ) -> Iterator[
        ServiceProvider
    ]:

        return iter(
            self._providers.values()
        )

    @property
    def providers(
        self,
    ) -> tuple[
        ServiceProvider,
        ...
    ]:

        return tuple(
            self._providers.values()
        )