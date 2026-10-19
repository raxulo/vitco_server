from __future__ import annotations

from typing import Protocol


class Resource(Protocol):

    priority: int

    async def startup(self) -> None: ...

    async def shutdown(self) -> None: ...