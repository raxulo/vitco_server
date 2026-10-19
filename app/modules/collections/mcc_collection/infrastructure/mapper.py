from __future__ import annotations

from app.modules.collections.mcc_collection.domain.entities import MccCollection
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel


class MccCollectionMapper:

    @staticmethod
    def to_entity(model: MccCollectionModel) -> MccCollection:
        return MccCollection(
            id=model.id,
            mcc_id=model.mcc_id,
            vlcc_id=model.vlcc_id,
            collected_at=model.collected_at,
            shift=model.shift,
            milk_type=model.milk_type,
            fat_percent=model.fat_percent,
            snf_percent=model.snf_percent,
            clr_value=model.clr_value,
            quantity=model.quantity,
            quantity_collection_mode=model.quantity_collection_mode,
            measurement_mode=model.measurement_mode,
            rate_per_unit=model.rate_per_unit,
            total_amount=model.total_amount,
            payment_mode=model.payment_mode,
            status=model.status,
            rank=model.rank,
            sample_number=model.sample_number,
            can_count=model.can_count,
            detection_value=model.detection_value,
            calibration_fat=model.calibration_fat,
            calibration_snf=model.calibration_snf,
            is_deleted=model.is_deleted,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: MccCollection) -> MccCollectionModel:
        return MccCollectionModel(
            id=entity.id,
            mcc_id=entity.mcc_id,
            vlcc_id=entity.vlcc_id,
            collected_at=entity.collected_at,
            shift=entity.shift,
            milk_type=entity.milk_type,
            fat_percent=entity.fat_percent,
            snf_percent=entity.snf_percent,
            clr_value=entity.clr_value,
            quantity=entity.quantity,
            quantity_collection_mode=entity.quantity_collection_mode,
            measurement_mode=entity.measurement_mode,
            rate_per_unit=entity.rate_per_unit,
            total_amount=entity.total_amount,
            payment_mode=entity.payment_mode,
            status=entity.status,
            rank=entity.rank,
            sample_number=entity.sample_number,
            can_count=entity.can_count,
            detection_value=entity.detection_value,
            calibration_fat=entity.calibration_fat,
            calibration_snf=entity.calibration_snf,
            is_deleted=entity.is_deleted,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )