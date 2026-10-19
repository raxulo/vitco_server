from __future__ import annotations

from app.modules.masters.advanced.domain.entities import (
    AdvanceMaster,
    AdvancePayItem,
    AdvancePayment,
)
from app.modules.masters.advanced.infrastructure.models import (
    AdvanceMasterModel,
    AdvancePayItemModel,
    AdvancePaymentModel,
)


class AdvanceMapper:

    @staticmethod
    def to_master_entity(model: AdvanceMasterModel) -> AdvanceMaster:
        return AdvanceMaster(
            id=model.id,
            advance_number=model.advance_number,
            advance_date=model.advance_date,
            user_id=model.user_id,
            total_amount=model.total_amount,
            paid_amount=model.paid_amount,
            outstanding_amount=model.outstanding_amount,
            status=model.status,
            notes=model.notes,
            is_active=model.is_active,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_master_model(entity: AdvanceMaster) -> AdvanceMasterModel:
        return AdvanceMasterModel(
            id=entity.id,
            advance_number=entity.advance_number,
            advance_date=entity.advance_date,
            user_id=entity.user_id,
            total_amount=entity.total_amount,
            paid_amount=entity.paid_amount,
            outstanding_amount=entity.outstanding_amount,
            status=entity.status,
            notes=entity.notes,
            is_active=entity.is_active,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_item_entity(model: AdvancePayItemModel) -> AdvancePayItem:
        return AdvancePayItem(
            id=model.id,
            advance_id=model.advance_id,
            item_id=model.item_id,
            item_name=model.item_name,
            quantity=model.quantity,
            unit_rate=model.unit_rate,
            total_amount=model.total_amount,
        )

    @staticmethod
    def to_item_model(entity: AdvancePayItem) -> AdvancePayItemModel:
        return AdvancePayItemModel(
            id=entity.id,
            advance_id=entity.advance_id,
            item_id=entity.item_id,
            item_name=entity.item_name,
            quantity=entity.quantity,
            unit_rate=entity.unit_rate,
            total_amount=entity.total_amount,
        )

    @staticmethod
    def to_payment_entity(model: AdvancePaymentModel) -> AdvancePayment:
        return AdvancePayment(
            id=model.id,
            advance_id=model.advance_id,
            payment_date=model.payment_date,
            amount=model.amount,
            payment_mode=model.payment_mode,
            reference_number=model.reference_number,
            notes=model.notes,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_payment_model(entity: AdvancePayment) -> AdvancePaymentModel:
        return AdvancePaymentModel(
            id=entity.id,
            advance_id=entity.advance_id,
            payment_date=entity.payment_date,
            amount=entity.amount,
            payment_mode=entity.payment_mode,
            reference_number=entity.reference_number,
            notes=entity.notes,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )