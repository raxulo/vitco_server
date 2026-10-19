from sqlalchemy import update
from uuid import UUID
from sqlalchemy import select, delete
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database.manager import DatabaseManager
from app.modules.common.device_item_version.domain.entities import DeviceItemVersion
from app.modules.common.device_item_version.domain.repository import IDeviceItemVersionRepository
from app.modules.common.device_item_version.infrastructure.mapper import DeviceItemVersionMapper
from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel

class DeviceItemVersionRepository(IDeviceItemVersionRepository):
    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    async def create(self, device_item_version: DeviceItemVersion) -> DeviceItemVersion:
        model = DeviceItemVersionMapper.to_model(device_item_version)
        self._session.add(model)
        return device_item_version

    async def create_bulk(self, device_item_versions: list[DeviceItemVersion]) -> list[DeviceItemVersion]:
        models = [DeviceItemVersionMapper.to_model(entity) for entity in device_item_versions]
        self._session.add_all(models)
        return device_item_versions

    async def get_by_id(self, id: UUID) -> DeviceItemVersion | None:
        stmt = select(DeviceItemVersionModel).where(DeviceItemVersionModel.id == id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return DeviceItemVersionMapper.to_entity(model) if model else None

    async def get_by_device_id(self, device_id: UUID) -> list[DeviceItemVersion]:
        stmt = select(DeviceItemVersionModel).where(DeviceItemVersionModel.device_id == device_id)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [DeviceItemVersionMapper.to_entity(model) for model in models]

    async def get_by_device_and_item(
        self,
        device_id: UUID,
        device_type: int,
        item_name: str,
    ) -> DeviceItemVersion | None:
        stmt = select(DeviceItemVersionModel).where(
            DeviceItemVersionModel.device_id == device_id,
            DeviceItemVersionModel.device_type == device_type,
            DeviceItemVersionModel.item_name == item_name
        )
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return DeviceItemVersionMapper.to_entity(model) if model else None

    async def update(self, device_item_version: DeviceItemVersion) -> DeviceItemVersion:
        values = {}
        if device_item_version.device_type is not None:
            values["device_type"] = device_item_version.device_type
        if device_item_version.device_id is not None:
            values["device_id"] = device_item_version.device_id
        if device_item_version.item_name is not None:
            values["item_name"] = device_item_version.item_name
        if device_item_version.version is not None:
            values["version"] = device_item_version.version

        if values:
            stmt = (
                update(DeviceItemVersionModel)
                .where(DeviceItemVersionModel.id == device_item_version.id)
                .values(**values)
            )
            await self._session.execute(stmt)
        return device_item_version

    async def update_bulk(self, device_item_versions: list[DeviceItemVersion]) -> list[DeviceItemVersion]:
        for entity in device_item_versions:
            await self.update(entity)
        return device_item_versions

    async def delete(self, id: UUID) -> bool:
        model = await self._session.get(DeviceItemVersionModel, id)
        if model:
            await self._session.delete(model)
            return True
        return False

    async def delete_bulk(self, ids: list[UUID]) -> bool:
        if not ids:
            return False
        stmt = delete(DeviceItemVersionModel).where(DeviceItemVersionModel.id.in_(ids))
        result = await self._session.execute(stmt)
        return result.rowcount > 0
