"""
MCC Collection ViewModel Assembler
"""

from decimal import Decimal
from app.modules.mcc.domain.enums import MccType
from uuid import UUID
from app.modules.collections.mcc_collection.application.command import (
    CreateMccCollectionCommand,
    UpdateMccCollectionCommand,
)
from app.modules.collections.mcc_collection.presentation.requests import (
    CreateMccCollectionRequest,
    UpdateMccCollectionRequest,
)


class MccCollectionAssembler:

    __slots__ = ()

    @staticmethod
    def create(
        data: CreateMccCollectionRequest,
    ) -> CreateMccCollectionCommand:
        if data.mcc_type == MccType.WEIGHT:
            return CreateMccCollectionCommand(
                mcc_id=data.mcc_id,
                vlcc_id=data.vlcc_id,
                collected_at=data.collection_date,
                shift=data.shift,
                quantity=data.quantity,
                quantity_collection_mode=data.quantity_collection_mode,
                measurement_mode=data.measurement_mode,
                sample_number=data.sample_number,
                can_count=data.can_count,
                mcc_type=data.mcc_type
            )
        return CreateMccCollectionCommand(
            mcc_id=data.mcc_id,
            vlcc_id=data.vlcc_id,
            collected_at=data.collection_date,
            shift=data.shift,
            milk_type=data.milk_type,
            fat_percent=data.fat_percent,
            snf_percent=data.snf_percent,
            clr_value=data.clr_value,
            quantity=data.quantity,
            quantity_collection_mode=data.quantity_collection_mode,
            measurement_mode=data.measurement_mode,
            rate_per_unit=data.rate_per_unit,
            total_amount=MccCollectionAssembler.get_total_amount(data),
            payment_mode=data.payment_mode,
            status=data.status,
            sample_number=data.sample_number,
            can_count=data.can_count,
            mcc_type=data.mcc_type
        )

    @staticmethod
    def update(
        collection_id: UUID,
        data: UpdateMccCollectionRequest,
    ) -> UpdateMccCollectionCommand:
        return UpdateMccCollectionCommand(
            id=collection_id,
            collection_number=data.collection_number,
            mcc_id=data.mcc_id,
            vlcc_id=data.vlcc_id,
            collected_at=data.collection_date,
            shift=data.shift,
            milk_type=data.milk_type,
            fat_percent=data.fat_percent,
            snf_percent=data.snf_percent,
            clr_value=data.clr_value,
            quantity=data.quantity,
            quantity_collection_mode=data.quantity_collection_mode,
            measurement_mode=data.measurement_mode,
            rate_per_unit=data.rate_per_unit,
            total_amount=MccCollectionAssembler.get_total_amount(data),
            payment_mode=data.payment_mode,
            status=data.status,
            sample_number=data.sample_number,
            can_count=data.can_count,
        )
    @staticmethod
    def get_total_amount(data):
        if data.mcc_type != MccType.WEIGHT:
            return Decimal(data.rate_per_unit) * Decimal(data.quantity)
        return Decimal(data.rate_per_unit)
