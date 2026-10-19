"""
Enterprise Lifecycle Manager

Ultra High Performance

Python 3.13+
"""

from __future__ import annotations

from threading import RLock

from app.core.logging.logger import logger
from .interface import Resource


class LifecycleManager:
    """
    Enterprise lifecycle manager.

    Features
    --------
    ✔ Priority startup
    ✔ Reverse shutdown
    ✔ Duplicate protection
    ✔ Freeze support
    ✔ O(1) registration
    ✔ Thread-safe registration
    """

    __slots__ = (
        "_resources",
        "_registered",
        "_lock",
        "_frozen",
        "_sorted",
    )

    def __init__(self) -> None:

        self._resources: list[Resource] = []

        self._registered: set[int] = set()

        self._lock = RLock()

        self._frozen = False

        self._sorted = False

    # ---------------------------------------------------------

    def register(
        self,
        resource: Resource,
    ) -> None:

        with self._lock:

            if self._frozen:
                raise RuntimeError(
                    "LifecycleManager is frozen."
                )

            key = id(resource)

            if key in self._registered:
                return

            self._registered.add(key)

            self._resources.append(resource)

            self._sorted = False

    # ---------------------------------------------------------

    def freeze(self) -> None:

        self._frozen = True

    # ---------------------------------------------------------

    def _sort(self) -> None:

        if self._sorted:
            return

        self._resources.sort(
            key=lambda r: r.priority,
        )

        self._sorted = True

    # ---------------------------------------------------------

    async def startup(self) -> None:

        self.freeze()

        self._sort()

        for resource in self._resources:

            logger.info(
                "Starting %s",
                resource.__class__.__name__,
            )

            await resource.startup()

    # ---------------------------------------------------------

    async def shutdown(self) -> None:

        for resource in reversed(self._resources):

            try:

                logger.info(
                    "Stopping %s",
                    resource.__class__.__name__,
                )

                await resource.shutdown()

            except Exception:

                logger.exception(
                    "Failed stopping %s",
                    resource.__class__.__name__,
                )

    # ---------------------------------------------------------

    @property
    def resources(self):

        return self._resources

    # ---------------------------------------------------------

    @property
    def frozen(self) -> bool:

        return self._frozen

    # ---------------------------------------------------------

    def __len__(self):

        return len(self._resources)