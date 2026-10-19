from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from .entities import Address


class IAddressRepository(ABC):

    @abstractmethod
    async def create(
        self,
        address: Address,
    ) -> None:
        ...

    @abstractmethod
    async def get_by_id(
        self,
        address_id: UUID,
    ) -> Address | None:
        ...

    @abstractmethod
    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> Address | None:
        ...

    @abstractmethod
    async def update(
        self,
        address: Address,
    ) -> None:
        ...

    @abstractmethod
    async def delete(
        self,
        address_id: UUID,
    ) -> None:
        ...

    @abstractmethod
    async def exists(
        self,
        address_id: UUID,
    ) -> bool:
        ...