from __future__ import annotations

from app.modules.masters.items.domain.entities import ItemMaster
from app.modules.masters.items.infrastructure.models import ItemMasterModel


class ItemMasterMapper:

    @staticmethod
    def to_entity(model: ItemMasterModel, owner_name: str | None = None, can_modify: bool = False) -> ItemMaster:
        return ItemMaster(
            id=model.id,
            item_code=model.item_code,
            item_name=model.item_name,
            unit_id=model.unit_id,
            rate=model.rate,
            is_active=model.is_active,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            owner_name=owner_name,
            can_modify=can_modify,
        )

    @staticmethod
    def to_model(entity: ItemMaster) -> ItemMasterModel:
        return ItemMasterModel(
            id=entity.id,
            item_code=entity.item_code,
            item_name=entity.item_name,
            unit_id=entity.unit_id,
            rate=entity.rate,
            is_active=entity.is_active,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )