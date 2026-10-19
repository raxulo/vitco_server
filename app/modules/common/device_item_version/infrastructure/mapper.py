from __future__ import annotations
from app.modules.common.device_item_version.domain.entities import DeviceItemVersion
from app.modules.common.device_item_version.infrastructure.models import DeviceItemVersion as DeviceItemVersionModel

class DeviceItemVersionMapper:
    @staticmethod
    def to_entity(model: DeviceItemVersionModel) -> DeviceItemVersion:
        return DeviceItemVersion(
            id=model.id,
            device_type=model.device_type,
            device_id=model.device_id,
            item_name=model.item_name,
            version=model.version,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: DeviceItemVersion) -> DeviceItemVersionModel:
        return DeviceItemVersionModel(
            id=entity.id,
            device_type=entity.device_type,
            device_id=entity.device_id,
            item_name=entity.item_name,
            version=entity.version,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )
