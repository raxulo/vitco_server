"""
VLCC Collection ViewModel Assembler
"""

from decimal import Decimal
from app.modules.masters.advanced.domain.enums import PaymentMode
from uuid import UUID
from app.modules.collections.vlcc_collection.application.command import (
    CreateVlccCollectionCommand,
    UpdateVlccCollectionCommand,
)
from app.modules.collections.vlcc_collection.presentation.requests import (
    CreateVlccCollectionRequest,
    UpdateVlccCollectionRequest,
)


class VlccCollectionAssembler:

    __slots__ = ()

    @staticmethod
    def create(
        data: CreateVlccCollectionRequest,
    ) -> CreateVlccCollectionCommand:
        return CreateVlccCollectionCommand(
            vlcc_id=data.vlcc_id,
            farmer_id=data.farmer_id,
            collected_at=data.collection_date,
            shift=data.shift,
            milk_type=data.milk_type,
            fat_percent=data.fat_percent,
            snf_percent=data.snf_percent,
            quantity=data.quantity,
            quantity_collection_mode=data.quantity_collection_mode,
            measurement_mode=data.measurement_mode,
            rate_per_unit=data.rate_per_unit,
            total_amount=VlccCollectionAssembler.get_total_amount(data.rate_per_unit, data.quantity),
            payment_mode=data.payment_mode or PaymentMode.CASH,
            status=data.status,
            rank=data.rank,
        )

    @staticmethod
    def update(
        id: UUID,
        data: UpdateVlccCollectionRequest,
    ) -> UpdateVlccCollectionCommand:
        return UpdateVlccCollectionCommand(
            id=id,
            vlcc_id=data.vlcc_id,
            farmer_id=data.farmer_id,
            collected_at=data.collection_date,
            shift=data.shift,
            milk_type=data.milk_type,
            fat_percent=data.fat_percent,
            snf_percent=data.snf_percent,
            quantity=data.quantity,
            quantity_collection_mode=data.quantity_collection_mode,
            measurement_mode=data.measurement_mode,
            rate_per_unit=data.rate_per_unit,
            total_amount=VlccCollectionAssembler.get_total_amount(data.rate_per_unit, data.quantity),
            payment_mode=data.payment_mode or PaymentMode.CASH,
            status=data.status,
            rank=data.rank,
        )

    @staticmethod
    def get_total_amount(rate: Decimal, quantity: Decimal) -> Decimal:
        return rate * quantity
