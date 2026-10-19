from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .entities import MilkQualityConfig


class IMilkQualityConfigRepository(ABC):

    @abstractmethod
    async def create(
        self,
        config: MilkQualityConfig,
    ) -> None:
        ...

    @abstractmethod
    async def get_by_id(
        self,
        config_id: UUID,
    ) -> MilkQualityConfig | None:
        ...

    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> MilkQualityConfig | None:
        ...

    @abstractmethod
    async def update(
        self,
        config: MilkQualityConfig,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        config_id: UUID,
    ) -> None:
        ...

    @abstractmethod
    async def exists(
        self,
        config_id: UUID,
    ) -> bool:
        ...