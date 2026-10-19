from __future__ import annotations
from uuid import uuid4, UUID
from app.modules.common.device_item_version.domain.entities import DeviceItemVersion
from app.modules.common.device_item_version.domain.exceptions import DeviceItemVersionNotFoundError
from app.modules.common.device_item_version.domain.repository import IDeviceItemVersionRepository
from app.modules.common.device_item_version.application.command import (
    BulkCreateDeviceItemVersionsCommand,
    BulkUpdateDeviceItemVersionsCommand,
    BulkDeleteDeviceItemVersionsCommand,
)

class DeviceItemVersionHandler:
    __slots__ = ("_repository",)

    def __init__(self, repository: IDeviceItemVersionRepository) -> None:
        self._repository = repository

    async def create_bulk(self, command: BulkCreateDeviceItemVersionsCommand) -> list[DeviceItemVersion]:
        entities = [
            DeviceItemVersion(
                id=uuid4(),
                device_type=command.device_type,
                device_id=command.device_id,
                item_name=item.item_name,
                version=item.version,
            )
            for item in command.items
        ]
        return await self._repository.create_bulk(entities)

    async def update_bulk(self, command: BulkUpdateDeviceItemVersionsCommand) -> list[DeviceItemVersion]:
        updated_entities = [
            DeviceItemVersion(
                id=update.id,
                device_type=None,
                device_id=None,
                item_name=update.item_name,
                version=update.version,
            )
            for update in command.updates
        ]
        return await self._repository.update_bulk(updated_entities)

    async def get_by_device_id(self, device_id: UUID) -> list[DeviceItemVersion]:
        return await self._repository.get_by_device_id(device_id)

    async def delete_bulk(self, command: BulkDeleteDeviceItemVersionsCommand) -> bool:
        return await self._repository.delete_bulk(command.ids)
