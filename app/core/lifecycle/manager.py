"""
RealTimeTransfer
================

Lifecycle Manager

Python 3.13+
"""

from __future__ import annotations

import asyncio

from collections.abc import Iterable

from app.core.lifecycle.exceptions import (
    DuplicateServiceError,
    ServiceStartError,
    ServiceStopError,
)
from app.core.lifecycle.service import (
    LifecycleService,
    ServiceState,
)


class LifecycleManager:
    """
    Enterprise Lifecycle Manager.
    """

    __slots__ = (
        "_services",
        "_started",
        "_lock",
    )

    def __init__(self) -> None:

        self._services: dict[
            str,
            LifecycleService,
        ] = {}

        self._started: list[
            LifecycleService
        ] = []

        self._lock = asyncio.Lock()

    # --------------------------------------------------
    # Registration
    # --------------------------------------------------

    def register(
        self,
        service: LifecycleService,
    ) -> None:

        name = service.name

        if name in self._services:

            raise DuplicateServiceError(
                f"{name} already registered."
            )

        self._services[name] = service

    def register_many(
        self,
        services: Iterable[
            LifecycleService
        ],
    ) -> None:

        for service in services:

            self.register(service)

    # --------------------------------------------------
    # Access
    # --------------------------------------------------

    def get(
        self,
        service_type: type,
    ):

        for service in self._services.values():

            if isinstance(
                service,
                service_type,
            ):
                return service

        raise KeyError(
            service_type.__name__
        )

    @property
    def services(
        self,
    ) -> tuple[
        LifecycleService,
        ...
    ]:

        return tuple(
            self._services.values()
        )

    # --------------------------------------------------
    # Ordering
    # --------------------------------------------------

    def _ordered_services(
        self,
    ) -> list[
        LifecycleService
    ]:

        return sorted(

            self._services.values(),

            key=lambda s: s.priority,
        )

    # --------------------------------------------------
    # Startup
    # --------------------------------------------------

    async def start(
        self,
    ) -> None:

        async with self._lock:

            ordered = (
                self._ordered_services()
            )

            for service in ordered:

                try:

                    service._set_state(
                        ServiceState.STARTING
                    )

                    await service.start()

                    service._set_state(
                        ServiceState.RUNNING
                    )

                    self._started.append(
                        service
                    )

                except Exception as ex:

                    service._set_state(
                        ServiceState.FAILED
                    )

                    await self._rollback()

                    raise ServiceStartError(
                        f"Failed to start "
                        f"{service.name}"
                    ) from ex

    # --------------------------------------------------
    # Shutdown
    # --------------------------------------------------

    async def stop(
        self,
    ) -> None:

        async with self._lock:

            for service in reversed(
                self._started
            ):

                try:

                    service._set_state(
                        ServiceState.STOPPING
                    )

                    await service.stop()

                    service._set_state(
                        ServiceState.STOPPED
                    )

                except Exception as ex:

                    service._set_state(
                        ServiceState.FAILED
                    )

                    raise ServiceStopError(
                        f"Failed to stop "
                        f"{service.name}"
                    ) from ex

            self._started.clear()

    # --------------------------------------------------
    # Rollback
    # --------------------------------------------------

    async def _rollback(
        self,
    ) -> None:

        for service in reversed(
            self._started
        ):

            try:

                await service.stop()

            except Exception:

                pass

        self._started.clear()

    # --------------------------------------------------
    # Health
    # --------------------------------------------------

    async def health(
        self,
    ) -> dict:

        return {

            service.name: service.state.value

            for service in self.services
        }
# """
# RealTimeTransfer
# ================

# Lifecycle Manager

# Coordinates application startup and shutdown.

# Python : 3.13
# """

# from __future__ import annotations

# from time import monotonic

# from loguru import logger

# from app.core.lifecycle.registry import registry
# from app.core.lifecycle.service import LifecycleService


# class LifecycleManager:
#     """
#     Coordinates lifecycle-aware services.
#     """

#     __slots__ = (
#         "_started_at",
#         "_running",
#     )

#     def __init__(self) -> None:

#         self._started_at: float | None = None
#         self._running = False

#     @property
#     def running(self) -> bool:
#         return self._running

#     @property
#     def uptime(self) -> float:

#         if self._started_at is None:
#             return 0.0

#         return monotonic() - self._started_at

#     async def startup(self) -> None:

#         if self._running:
#             return

#         logger.info("Starting application services...")

#         for service in registry.startup:

#             logger.info(
#                 f"Starting [{service.name}]..."
#             )

#             started = monotonic()

#             await service.start()

#             elapsed = (
#                 monotonic() - started
#             ) * 1000

#             logger.success(
#                 f"[{service.name}] started "
#                 f"({elapsed:.2f} ms)"
#             )

#         self._running = True
#         self._started_at = monotonic()

#         logger.success(
#             "Application startup complete."
#         )

#     async def shutdown(self) -> None:

#         if not self._running:
#             return

#         logger.info("Stopping services...")

#         for service in registry.shutdown:

#             logger.info(
#                 f"Stopping [{service.name}]..."
#             )

#             started = monotonic()

#             try:

#                 await service.stop()

#             except Exception:

#                 logger.exception(
#                     f"Failed stopping {service.name}"
#                 )

#             elapsed = (
#                 monotonic() - started
#             ) * 1000

#             logger.success(
#                 f"[{service.name}] stopped "
#                 f"({elapsed:.2f} ms)"
#             )

#         self._running = False

#         logger.success(
#             "Application stopped."
#         )

#     async def health(self) -> dict:

#         services = {}

#         for service in registry:

#             services[
#                 service.name
#             ] = await service.health()

#         return {

#             "running": self.running,

#             "uptime": round(
#                 self.uptime,
#                 2,
#             ),

#             "services": services,
#         }
