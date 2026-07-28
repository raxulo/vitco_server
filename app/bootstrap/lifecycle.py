"""
RealTimeTransfer
================

Enterprise Lifecycle Manager

Coordinates application startup, shutdown, readiness,
and runtime state.

Python 3.13
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from enum import StrEnum, auto
from time import monotonic
from typing import Final

from fastapi import FastAPI

from app.core.logger import logger


LifecycleTask = Callable[[FastAPI], Awaitable[None]]


class ApplicationState(StrEnum):
    INITIALIZING = auto()
    STARTING = auto()
    RUNNING = auto()
    STOPPING = auto()
    STOPPED = auto()


class LifecycleManager:
    """
    Enterprise lifecycle coordinator.

    Responsibilities
    ----------------
    • Startup
    • Shutdown
    • Health
    • Runtime State
    • Uptime
    • Service Registration
    """

    __slots__ = (
        "_startup",
        "_shutdown",
        "_state",
        "_started",
        "_lock",
    )

    def __init__(self) -> None:

        self._startup: list[LifecycleTask] = []

        self._shutdown: list[LifecycleTask] = []

        self._state: ApplicationState = (
            ApplicationState.INITIALIZING
        )

        self._started: float = 0.0

        self._lock: Final = asyncio.Lock()

    @property
    def state(self) -> ApplicationState:
        return self._state

    @property
    def uptime(self) -> float:

        if self._started == 0:

            return 0

        return monotonic() - self._started

    def register_startup(
        self,
        task: LifecycleTask,
    ) -> None:

        self._startup.append(task)

    def register_shutdown(
        self,
        task: LifecycleTask,
    ) -> None:

        self._shutdown.append(task)

    async def startup(
        self,
        app: FastAPI,
    ) -> None:

        async with self._lock:

            logger.info("Application starting...")

            self._state = (
                ApplicationState.STARTING
            )

            for task in self._startup:
                await task(app)

            self._started = monotonic()

            self._state = (
                ApplicationState.RUNNING
            )

            logger.success(
                "Application started."
            )

    async def shutdown(
        self,
        app: FastAPI,
    ) -> None:

        async with self._lock:

            logger.info("Application stopping...")

            self._state = (
                ApplicationState.STOPPING
            )

            for task in reversed(
                self._shutdown
            ):

                try:
                    await task(app)
                except Exception:
                    logger.exception(
                        "Shutdown task failed."
                    )

            self._state = (
                ApplicationState.STOPPED
            )

            logger.success(
                "Application stopped."
            )

    def health(self) -> dict:
        return {
            "state": self.state,
            "uptime": round(
                self.uptime, 2,
            ),
        }


lifecycle = LifecycleManager()