from __future__ import annotations

from typing import Final

from .interface import Resource


class ResourceManager:
    """
    Enterprise Resource Manager

    Features
    --------
    - O(1) registration
    - Duplicate protection
    - LIFO shutdown
    - Freeze after startup
    - Zero allocation runtime
    """

    __slots__ = (
        "_resources",
        "_registered",
        "_frozen",
    )

    def __init__(self) -> None:

        self._resources: list[Resource] = []
        self._registered: set[int] = set()
        self._frozen: bool = False

    # ---------------------------------------------------------

    def register(
        self,
        resource: Resource,
    ) -> None:

        if self._frozen:
            raise RuntimeError(
                "ResourceManager is frozen."
            )

        key = id(resource)

        if key in self._registered:
            return

        self._registered.add(key)
        self._resources.append(resource)

    # ---------------------------------------------------------

    async def startup(self) -> None:

        self._frozen = True

        for resource in self._resources:
            await resource.startup()

    # ---------------------------------------------------------

    async def shutdown(self) -> None:

        for resource in reversed(self._resources):
            try:
                await resource.shutdown()
            except Exception:
                # optional logger.exception(...)
                pass

    # ---------------------------------------------------------

    @property
    def resources(self) -> list[Resource]:
        return self._resources

    # ---------------------------------------------------------

    @property
    def frozen(self) -> bool:
        return self._frozen

    # ---------------------------------------------------------

    def __len__(self) -> int:
        return len(self._resources)