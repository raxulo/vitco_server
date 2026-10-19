
from dataclasses import field
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4


@dataclass(slots=True)
class AdvanceRecord:
    """
    Domain entity representing an advance operation.

    One AdvanceRecord can contain multiple AdvanceItems.
    """

    id: UUID

    user_id: UUID

    advance_date: datetime

    created_by: UUID

    total_amount: Decimal

    notes: str | None = None

    items: list["AdvanceItem"] = field(
        default_factory=list
    )

    created_at: datetime | None = None

    # =========================================================
    # FACTORY
    # =========================================================

    @classmethod
    def create(
        cls,
        *,
        user_id: UUID,
        advance_date: datetime,
        created_by: UUID,
        notes: str | None = None,
    ) -> "AdvanceRecord":

        return cls(
            id=uuid4(),
            user_id=user_id,
            advance_date=advance_date,
            created_by=created_by,
            total_amount=Decimal("0.00"),
            notes=notes,
        )

    # =========================================================
    # ADD ITEM
    # =========================================================

    def add_item(
        self,
        item_master_id: UUID,
        quantity: Decimal,
        unit_rate: Decimal,
    ) -> "AdvanceItem":

        item = AdvanceItem.create(
            advance_record_id=self.id,
            item_master_id=item_master_id,
            quantity=quantity,
            unit_rate=unit_rate,
        )

        self.items.append(item)

        self.total_amount += item.amount

        return item


@dataclass(slots=True)
class AdvanceItem:
    """
    Domain entity representing one item inside an advance record.

    This entity is completely independent of SQLAlchemy.
    """

    id: UUID

    advance_record_id: UUID

    item_master_id: UUID

    quantity: Decimal

    unit_rate: Decimal

    amount: Decimal

    created_at: datetime | None = None


    # =========================================================
    # FACTORY
    # =========================================================

    @classmethod
    def create(
        cls,
        *,
        advance_record_id: UUID,
        item_master_id: UUID,
        quantity: Decimal,
        unit_rate: Decimal,
    ) -> "AdvanceItem":

        amount = (
            quantity * unit_rate
        ).quantize(
            Decimal("0.01")
        )

        return cls(
            id=uuid4(),
            advance_record_id=advance_record_id,
            item_master_id=item_master_id,
            quantity=quantity,
            unit_rate=unit_rate,
            amount=amount,
        )