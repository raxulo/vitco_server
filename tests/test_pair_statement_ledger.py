import pytest
from datetime import datetime
from decimal import Decimal
from uuid import uuid4
from sqlalchemy import insert

from app.core.clock import now_naive_ist
from app.modules.payments.domain.enums import (
    LedgerEntryType,
    PaymentMethod,
    PaymentSourceType,
    PaymentTransferStatus,
)
from app.modules.payments.infrastructure.models import (
    PaymentLedgerEntryModel,
    PaymentTransferModel,
)
from app.modules.payments.infrastructure.repository import PaymentLedgerRepository
from app.modules.administration.infrastructure.models import UserModel
from app.modules.administration.domain.enums import Role


@pytest.mark.asyncio
async def test_get_pair_history_with_payment_source_type(database):
    u1_id = uuid4()
    u2_id = uuid4()

    async with database.transaction() as session:
        await session.execute(
            insert(UserModel).values([
                {
                    "id": u1_id,
                    "name": "Dairy Admin",
                    "email": f"admin-{u1_id.hex[:6]}@test.local",
                    "mobile": f"9{str(u1_id.int)[-9:]}",
                    "password_hash": "dummy-hash",
                    "role": Role.ADMIN.value,
                    "created_at": now_naive_ist(),
                    "updated_at": now_naive_ist(),
                },
                {
                    "id": u2_id,
                    "name": "Farmer Ramesh",
                    "email": f"farmer-{u2_id.hex[:6]}@test.local",
                    "mobile": f"9{str(u2_id.int)[-9:]}",
                    "password_hash": "dummy-hash",
                    "role": Role.FARMER.value,
                    "created_at": now_naive_ist(),
                    "updated_at": now_naive_ist(),
                },
            ])
        )

        t_id = uuid4()
        await session.execute(
            insert(PaymentTransferModel).values({
                "id": t_id,
                "sender_id": u1_id,
                "receiver_id": u2_id,
                "amount": Decimal("450.00"),
                "source_type": PaymentSourceType.MILK_COLLECTION,
                "payment_method": PaymentMethod.SYSTEM,
                "idempotency_key": str(uuid4()),
                "reference": "BATCH-01",
                "description": "Morning shift milk collection",
                "status": PaymentTransferStatus.COMPLETED,
                "created_at": now_naive_ist(),
                "updated_at": now_naive_ist(),
            })
        )

        # Insert user1 ledger entry (debit)
        await session.execute(
            insert(PaymentLedgerEntryModel).values({
                "id": uuid4(),
                "transfer_id": t_id,
                "user_id": u1_id,
                "counterparty_id": u2_id,
                "entry_type": LedgerEntryType.DEBIT,
                "amount": Decimal("450.00"),
                "balance_before": Decimal("5000.00"),
                "balance_after": Decimal("4550.00"),
                "created_at": now_naive_ist(),
                "updated_at": now_naive_ist(),
            })
        )

        # Insert user2 ledger entry (credit)
        await session.execute(
            insert(PaymentLedgerEntryModel).values({
                "id": uuid4(),
                "transfer_id": t_id,
                "user_id": u2_id,
                "counterparty_id": u1_id,
                "entry_type": LedgerEntryType.CREDIT,
                "amount": Decimal("450.00"),
                "balance_before": Decimal("100.00"),
                "balance_after": Decimal("550.00"),
                "created_at": now_naive_ist(),
                "updated_at": now_naive_ist(),
            })
        )

    async with database.transaction():
        repo = PaymentLedgerRepository(database.session)
        entries = await repo.get_pair_history(
            user_id=u1_id,
            counterparty_id=u2_id,
            limit=10,
        )

        assert len(entries) == 1
        row = entries[0]
        assert row.transfer_id == t_id
        assert row.amount == Decimal("450.00")
        assert row.source_type == PaymentSourceType.MILK_COLLECTION
        assert row.payment_method == PaymentMethod.SYSTEM
        assert row.reference == "BATCH-01"
        assert row.description == "Morning shift milk collection"

