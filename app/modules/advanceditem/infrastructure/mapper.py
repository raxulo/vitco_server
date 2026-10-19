from app.modules.advanceditem.domain.entities import AdvanceItem, AdvanceRecord
from app.modules.advanceditem.infrastructure.models import AdvanceItemModel, AdvanceRecordModel

class AdvanceRecordMapper:
    """
    Maps AdvanceRecord domain entity <-> SQLAlchemy model.

    Relationship items are intentionally not mapped here.

    Items should be loaded explicitly by repository/service
    when required.
    """

    __slots__ = ()

    @staticmethod
    def to_entity(
        model: AdvanceRecordModel,
    ) -> AdvanceRecord:

        return AdvanceRecord(
            id=model.id,
            user_id=model.user_id,
            advance_date=model.advance_date,
            notes=model.notes,
            created_by=model.created_by,
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(
        entity: AdvanceRecord,
    ) -> AdvanceRecordModel:

        return AdvanceRecordModel(
            id=entity.id,
            user_id=entity.user_id,
            advance_date=entity.advance_date,
            notes=entity.notes,
            total_amount=entity.total_amount,
            created_by=entity.created_by,
        )

    @staticmethod
    def update_model(
        model: AdvanceRecordModel,
        entity: AdvanceRecord,
    ) -> AdvanceRecordModel:

        model.user_id = entity.user_id
        model.advance_date = entity.advance_date
        model.notes = entity.notes
        model.created_by = entity.created_by

        return model


class AdvanceItemMapper:
    """
    Maps AdvanceItem domain entity <-> SQLAlchemy model.

    No business logic.
    No database access.
    No calculations.
    """

    __slots__ = ()

    @staticmethod
    def to_entity(
        model: AdvanceItemModel,
    ) -> AdvanceItem:

        return AdvanceItem(
            id=model.id,
            advance_record_id=model.advance_record_id,
            item_master_id=model.item_master_id,
            quantity=model.quantity,
            unit_rate=model.unit_rate,
            amount=model.amount,
            created_at=model.created_at,
        )

    @staticmethod
    def to_model(
        entity: AdvanceItem,
    ) -> AdvanceItemModel:

        return AdvanceItemModel(
            id=entity.id,
            advance_record_id=entity.advance_record_id,
            item_master_id=entity.item_master_id,
            quantity=entity.quantity,
            unit_rate=entity.unit_rate,
            amount=entity.amount,
        )

    @staticmethod
    def update_model(
        model: AdvanceItemModel,
        entity: AdvanceItem,
    ) -> AdvanceItemModel:

        model.advance_record_id = (
            entity.advance_record_id
        )

        model.item_master_id = (
            entity.item_master_id
        )

        model.quantity = entity.quantity
        model.unit_rate = entity.unit_rate
        model.amount = entity.amount

        return model