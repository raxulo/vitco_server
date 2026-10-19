from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.common.device_item_version.domain.entities import DeviceItemVersion


class IDeviceItemVersionRepository(ABC):

    @abstractmethod
    async def create(
        self,
        device_item_version: DeviceItemVersion,
    ) -> DeviceItemVersion:
        raise NotImplementedError

    @abstractmethod
    async def create_bulk(
        self,
        device_item_versions: list[DeviceItemVersion],
    ) -> list[DeviceItemVersion]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_id(
        self,
        id: UUID,
    ) -> DeviceItemVersion | None:
        raise NotImplementedError

    @abstractmethod
    async def get_by_device_id(
        self,
        device_id: UUID,
    ) -> list[DeviceItemVersion]:
        raise NotImplementedError

    @abstractmethod
    async def get_by_device_and_item(
        self,
        device_id: UUID,
        device_type: int,
        item_name: str,
    ) -> DeviceItemVersion | None:
        raise NotImplementedError

    @abstractmethod
    async def update(
        self,
        device_item_version: DeviceItemVersion,
    ) -> DeviceItemVersion:
        raise NotImplementedError

    @abstractmethod
    async def update_bulk(
        self,
        device_item_versions: list[DeviceItemVersion],
    ) -> list[DeviceItemVersion]:
        raise NotImplementedError

    @abstractmethod
    async def delete(
        self,
        id: UUID,
    ) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def delete_bulk(
        self,
        ids: list[UUID],
    ) -> bool:
        raise NotImplementedError
