from __future__ import annotations

from app.modules.masters.units.domain.entities import UnitMaster
from app.modules.masters.units.infrastructure.models import UnitMasterModel


class UnitMasterMapper:

    @staticmethod
    def to_entity(model: UnitMasterModel, owner_name: str | None = None, can_modify: bool = False) -> UnitMaster:
        return UnitMaster(
            id=model.id,
            name=model.name,
            is_active=model.is_active,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            owner_name=owner_name,
            can_modify=can_modify,
        )

    @staticmethod
    def to_model(entity: UnitMaster) -> UnitMasterModel:
        return UnitMasterModel(
            id=entity.id,
            name=entity.name,
            is_active=entity.is_active,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )