from __future__ import annotations

from app.modules.collections.vlcc_collection.domain.dispatch_entities import Dispatch
from app.modules.collections.vlcc_collection.infrastructure.models import DispatchModel


class DispatchMapper:

    @staticmethod
    def to_model(entity: Dispatch) -> DispatchModel:
        return DispatchModel(
            id=entity.id,
            vlcc_id=entity.vlcc_id,
            collected_at=entity.collected_at,
            shift=entity.shift,
            fat_percent=entity.fat_percent,
            snf_percent=entity.snf_percent,
            quantity=entity.quantity,
            can_count=entity.can_count,
            quantity_collection_mode=entity.quantity_collection_mode,
            measurement_mode=entity.measurement_mode,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_entity(model: DispatchModel) -> Dispatch:
        return Dispatch(
            id=model.id,
            vlcc_id=model.vlcc_id,
            collected_at=model.collected_at,
            shift=model.shift,
            fat_percent=model.fat_percent,
            snf_percent=model.snf_percent,
            quantity=model.quantity,
            can_count=model.can_count,
            quantity_collection_mode=model.quantity_collection_mode,
            measurement_mode=model.measurement_mode,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
