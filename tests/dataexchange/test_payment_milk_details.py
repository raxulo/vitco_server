"""
Payment history: a Milk Payment entry carries the quantity / FAT / SNF / rate
of the collection it paid for; other payment types carry none.
"""

from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import select

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.payments.domain.enums import (
    LedgerEntryType,
    PaymentMethod,
    PaymentSourceType,
    PaymentTransferStatus,
)
from app.modules.payments.infrastructure.models import PaymentLedgerEntryModel, PaymentTransferModel
from app.modules.ratechart.domain.enums import MilkType
from tests.dataexchange.factories import create_farmers, create_vlcc


async def _transfer(session, sender: UUID, receiver: UUID, amount: Decimal, *,
                    source_type: PaymentSourceType, method: PaymentMethod, source_id: UUID | None) -> None:
    transfer_id = uuid4()
    session.add(PaymentTransferModel(
        id=transfer_id, sender_id=sender, receiver_id=receiver, amount=amount, source_type=source_type,
        payment_method=method, idempotency_key=uuid4().hex, source_id=source_id,
        status=PaymentTransferStatus.COMPLETED,
    ))
    await session.flush()
    for user_id, other, entry in ((sender, receiver, LedgerEntryType.DEBIT), (receiver, sender, LedgerEntryType.CREDIT)):
        session.add(PaymentLedgerEntryModel(
            id=uuid4(), transfer_id=transfer_id, user_id=user_id, counterparty_id=other, entry_type=entry,
            amount=amount, balance_before=Decimal(0), balance_after=Decimal(0),
        ))


async def test_history_returns_milk_details_for_milk_payments(api, database, token_for):
    vlcc = await create_vlcc(database)
    farmers = await create_farmers(database, vlcc, 1, prefix=f"PM{vlcc.code}")
    farmer_user = farmers[0]["user_id"]
    collection_id = uuid4()

    async with database.transaction() as session:
        farmer_id = await session.scalar(select(FarmerModel.id).where(FarmerModel.vlcc_id == vlcc.id))
        session.add(VlccCollectionModel(
            id=collection_id, vlcc_id=vlcc.id, farmer_id=farmer_id, milk_type=MilkType.COW,
            # Values at the columns' own scale (VLCC FAT / SNF keep 1 decimal, qty / rate 2)
            shift=CollectionShift.MORNING, quantity=Decimal("12.34"), fat_percent=Decimal("4.5"),
            snf_percent=Decimal("8.5"), rate_per_unit=Decimal("41.78"), total_amount=Decimal("515.88"),
        ))
        await session.flush()
        await _transfer(session, vlcc.user_id, farmer_user, Decimal("515.88"),
                        source_type=PaymentSourceType.MILK_COLLECTION, method=PaymentMethod.SYSTEM,
                        source_id=collection_id)
        await _transfer(session, vlcc.user_id, farmer_user, Decimal("100.00"),
                        source_type=PaymentSourceType.MANUAL, method=PaymentMethod.CASH, source_id=None)

    response = await api.get("/api/v1/payments/history", headers=token_for(farmer_user, Role.FARMER))
    assert response.status_code == 200, response.text
    items = response.json()["items"]
    assert len(items) == 2

    milk = next(item for item in items if item["payment_type_label"] == "Milk Payment")
    assert milk["milk_details"] == {
        "collection_id": str(collection_id),
        "quantity": 12.34,
        "fat": 4.5,
        "snf": 8.5,
        "rate": 41.78,
    }

    cash = next(item for item in items if item["payment_type_label"] != "Milk Payment")
    assert cash["milk_details"] is None
