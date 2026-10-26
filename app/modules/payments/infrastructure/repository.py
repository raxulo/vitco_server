from app.modules.payments.application.dto import PaymentCollectionSummaryViaPeriodDto
from sqlalchemy import case
from uuid import uuid4
from datetime import datetime
from app.modules.payments.domain.enums import PaymentTransferStatus
from app.modules.payments.infrastructure.models import PaymentTransferModel
from app.modules.payments.domain.enums import PaymentMethod
from app.modules.payments.domain.enums import PaymentSourceType
from app.modules.payments.infrastructure.models import PaymentLedgerEntryModel
from app.modules.payments.domain.enums import LedgerEntryType
from app.modules.payments.infrastructure.models import PaymentPairBalanceModel
from sqlalchemy import update
from sqlalchemy import func
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select, or_
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.payments.infrastructure.models import (
    AccountBalanceModel,
)
from sqlalchemy.orm import aliased
from app.modules.administration.infrastructure.models import UserModel
from app.core.clock import now_naive_ist


class AccountBalanceRepository:

    __slots__ = ("_session",)

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        user_id: UUID,
    ) -> AccountBalanceModel | None:

        stmt = (
            select(AccountBalanceModel)
            .where(
                AccountBalanceModel.user_id == user_id,
            )
        )

        return await self._session.scalar(stmt)

    async def get_balance(
        self,
        user_id: UUID,
    ) -> Decimal:
        model = await self.get(user_id)
        return model.balance if model is not None else Decimal("0.00")

    # =========================================================
    # GET FOR UPDATE
    #
    # Used only when service needs current balance snapshot.
    # =========================================================

    async def get_for_update(
        self,
        user_id: UUID,
    ) -> tuple[Decimal, int] | None:

        stmt = (
            select(
                AccountBalanceModel.balance,
                AccountBalanceModel.version,
            )
            .where(
                AccountBalanceModel.user_id == user_id,
            )
            .with_for_update()
        )

        row = await self._session.execute(stmt)

        return row.one_or_none()

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        user_id: UUID,
        balance: Decimal = Decimal("0.00"),
    ) -> AccountBalanceModel:

        # No RETURNING: not all SQLite builds support it. Use the ORM so the
        # row is inserted and the populated instance (with its id) comes back.
        model = AccountBalanceModel(
            user_id=user_id,
            balance=balance,
            version=0,
        )
        self._session.add(model)
        await self._session.flush()
        return model

    # =========================================================
    # ATOMIC BALANCE UPDATE
    #
    # balance = balance + delta
    #
    # delta > 0  => CREDIT
    # delta < 0  => DEBIT
    # =========================================================

    async def apply_delta(
        self,
        user_id: UUID,
        delta: Decimal,
        ledger_id: UUID,
    ) -> Decimal:

        result = await self._session.execute(
            update(AccountBalanceModel)
            .where(
                AccountBalanceModel.user_id == user_id,
            )
            .values(
                balance=AccountBalanceModel.balance + delta,
                version=AccountBalanceModel.version + 1,
                last_ledger_id=ledger_id,
            )
        )

        if result.rowcount == 0:
            raise ValueError(f"Account balance not found: {user_id}")

        # Read the new balance back (no RETURNING for SQLite compatibility).
        return await self._session.scalar(
            select(AccountBalanceModel.balance).where(
                AccountBalanceModel.user_id == user_id,
            )
        )

    # =========================================================
    # UPSERT + DELTA
    #
    # Fastest method when account may not exist.
    #
    # Existing:
    #     balance += delta
    #
    # Missing:
    #     balance = initial + delta
    # =========================================================

    async def upsert_delta(
        self,
        user_id: UUID,
        delta: Decimal,
        ledger_id: UUID | None = None,
    ) -> AccountBalanceModel:

        stmt = insert(AccountBalanceModel).values(
            user_id=user_id,
            balance=delta,
            version=1,
            last_ledger_id=ledger_id,
        )

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                AccountBalanceModel.user_id,
            ],
            set_={
                "balance": (
                    AccountBalanceModel.balance + delta
                ),
                "version": (
                    AccountBalanceModel.version + 1
                ),
                "last_ledger_id": ledger_id,
                "updated_at": now_naive_ist(),
            },
        )

        await self._session.execute(stmt)

        # Read the row back (no RETURNING for SQLite compatibility).
        return await self._session.scalar(
            select(AccountBalanceModel).where(
                AccountBalanceModel.user_id == user_id,
            )
        )

    # =========================================================
    # BULK UPDATE
    #
    # Useful for:
    #
    # A -> B
    #
    # A = -5000
    # B = +5000
    # =========================================================

    async def apply_deltas(
        self,
        changes: list[
            tuple[UUID, Decimal, UUID | None]
        ],
    ) -> list[AccountBalanceModel]:

        if not changes:
            return []

        values = [
            {
                "user_id": user_id,
                "balance": delta,
                "version": 1,
                "last_ledger_id": ledger_id,
            }
            for user_id, delta, ledger_id in changes
        ]

        stmt = insert(AccountBalanceModel).values(values)

        stmt = stmt.on_conflict_do_update(
            index_elements=[
                AccountBalanceModel.user_id,
            ],
            set_={
                "balance": (
                    AccountBalanceModel.balance
                    + stmt.excluded.balance
                ),
                "version": (
                    AccountBalanceModel.version + 1
                ),
                "last_ledger_id": (
                    stmt.excluded.last_ledger_id
                ),
                "updated_at": now_naive_ist(),
            },
        )

        await self._session.execute(stmt)

        # Read the affected rows back (no RETURNING for SQLite compatibility).
        user_ids = [user_id for user_id, _, _ in changes]
        rows = await self._session.scalars(
            select(AccountBalanceModel).where(
                AccountBalanceModel.user_id.in_(user_ids),
            )
        )
        return list(rows)


class PaymentTransferRepository:

    __slots__ = ("_session",)

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    # =========================================================
    # CREATE
    # =========================================================

    async def create_idempotent(
        self,
        *,
        sender_id: UUID,
        receiver_id: UUID,
        amount: Decimal,
        source_type: PaymentSourceType,
        payment_method: PaymentMethod,
        idempotency_key: str,
        source_id: UUID | None = None,
        reference: str | None = None,
        description: str | None = None,
    ) -> tuple[UUID, bool]:
        """
        Create a payment transfer atomically.

        Returns:
            (transfer_id, True)
                New transfer created.

            (transfer_id, False)
                Idempotency key already existed.

        IMPORTANT:
        No SELECT-before-INSERT is performed.

        PostgreSQL UNIQUE constraint is the source of truth.
        """

        transfer_id = uuid4()

        stmt = (
            insert(PaymentTransferModel)
            .values(
                id=transfer_id,
                sender_id=sender_id,
                receiver_id=receiver_id,
                amount=amount,
                source_type=source_type,
                payment_method=payment_method,
                source_id=source_id,
                idempotency_key=idempotency_key,
                reference=reference,
                description=description,
                status=PaymentTransferStatus.POSTED,
            )
            .on_conflict_do_nothing(
                index_elements=(
                    PaymentTransferModel.idempotency_key,
                ),
            )
        )

        result = await self._session.execute(stmt)

        # rowcount is 1 when the row was inserted, 0 when the idempotency key
        # already existed. RETURNING is intentionally not used: SQLite rejects
        # "RETURNING" together with "ON CONFLICT DO NOTHING", and the id is
        # already known (we generated transfer_id above).
        if result.rowcount and result.rowcount > 0:
            return transfer_id, True

        # -----------------------------------------------------
        # Existing idempotent transaction.
        #
        # This SELECT is executed ONLY on duplicate requests.
        # Normal successful payment path = 1 SQL statement.
        # -----------------------------------------------------

        existing_id = await self._get_id_by_idempotency_key(
            idempotency_key
        )

        if existing_id is None:
            raise RuntimeError(
                "Idempotency conflict detected but "
                "existing transfer was not found"
            )

        return existing_id, False

    # =========================================================
    # PRIVATE IDEMPOTENCY LOOKUP
    # =========================================================

    async def _get_id_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> UUID | None:

        stmt = (
            select(
                PaymentTransferModel.id,
            )
            .where(
                PaymentTransferModel.idempotency_key
                == idempotency_key,
            )
            .limit(1)
        )

        return await self._session.scalar(stmt)

    # =========================================================
    # GET ID
    # =========================================================

    async def get_id(
        self,
        transfer_id: UUID,
    ) -> UUID | None:

        stmt = (
            select(
                PaymentTransferModel.id,
            )
            .where(
                PaymentTransferModel.id == transfer_id,
            )
            .limit(1)
        )

        return await self._session.scalar(stmt)

    # =========================================================
    # GET STATUS
    # =========================================================

    async def get_status(
        self,
        transfer_id: UUID,
    ) -> PaymentTransferStatus | None:

        stmt = (
            select(
                PaymentTransferModel.status,
            )
            .where(
                PaymentTransferModel.id == transfer_id,
            )
            .limit(1)
        )

        return await self._session.scalar(stmt)

    # =========================================================
    # GET BASIC TRANSFER
    # =========================================================

    async def get_basic(
        self,
        transfer_id: UUID,
    ) -> tuple[
        UUID,
        UUID,
        Decimal,
        PaymentTransferStatus,
    ] | None:

        stmt = (
            select(
                PaymentTransferModel.sender_id,
                PaymentTransferModel.receiver_id,
                PaymentTransferModel.amount,
                PaymentTransferModel.status,
            )
            .where(
                PaymentTransferModel.id == transfer_id,
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)

        return result.one_or_none()

    # =========================================================
    # GET BY IDEMPOTENCY KEY
    # =========================================================

    async def get_by_idempotency_key(
        self,
        idempotency_key: str,
    ) -> UUID | None:

        return await self._get_id_by_idempotency_key(
            idempotency_key
        )

    # =========================================================
    # UPDATE STATUS
    # =========================================================

    async def update_status(
        self,
        *,
        transfer_id: UUID,
        expected_status: PaymentTransferStatus,
        new_status: PaymentTransferStatus,
    ) -> bool:
        """
        Compare-and-set status.

        Example:

            PENDING -> POSTED

        If another worker has already changed the status,
        this UPDATE changes zero rows.
        """

        stmt = (
            update(PaymentTransferModel)
            .where(
                PaymentTransferModel.id == transfer_id,
                PaymentTransferModel.status == expected_status,
            )
            .values(
                status=new_status,
            )
        )

        result = await self._session.execute(stmt)

        return result.rowcount == 1

    # =========================================================
    # MARK POSTED
    # =========================================================

    async def mark_posted(
        self,
        transfer_id: UUID,
    ) -> bool:

        return await self.update_status(
            transfer_id=transfer_id,
            expected_status=PaymentTransferStatus.PENDING,
            new_status=PaymentTransferStatus.POSTED,
        )

    # =========================================================
    # MARK FAILED
    # =========================================================

    async def mark_failed(
        self,
        transfer_id: UUID,
    ) -> bool:

        return await self.update_status(
            transfer_id=transfer_id,
            expected_status=PaymentTransferStatus.PENDING,
            new_status=PaymentTransferStatus.FAILED,
        )

    # =========================================================
    # USER HISTORY
    # =========================================================

    async def get_user_history(
        self,
        *,
        user_id: UUID,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
        limit: int = 50,
    ):

        limit = min(max(limit, 1), 100)

        stmt = (
            select(
                PaymentTransferModel.id,
                PaymentTransferModel.sender_id,
                PaymentTransferModel.receiver_id,
                PaymentTransferModel.amount,
                PaymentTransferModel.source_type,
                PaymentTransferModel.payment_method,
                PaymentTransferModel.source_id,
                PaymentTransferModel.reference,
                PaymentTransferModel.description,
                PaymentTransferModel.status,
                PaymentTransferModel.created_at,
            )
            .where(
                (
                    (PaymentTransferModel.sender_id == user_id)
                    |
                    (PaymentTransferModel.receiver_id == user_id)
                )
            )
        )

        # -----------------------------------------------------
        # KEYSET PAGINATION
        # -----------------------------------------------------

        if (
            cursor_created_at is not None
            and cursor_id is not None
        ):
            stmt = stmt.where(
                (
                    PaymentTransferModel.created_at,
                    PaymentTransferModel.id,
                )
                < (
                    cursor_created_at,
                    cursor_id,
                )
            )

        stmt = (
            stmt
            .order_by(
                PaymentTransferModel.created_at.desc(),
                PaymentTransferModel.id.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return result.all()

class PaymentLedgerRepository:

    __slots__ = ("_session",)

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    # =========================================================
    # INSERT TWO ENTRIES
    # =========================================================

    async def add_transfer_entries(
        self,
        *,
        transfer_id: UUID,
        sender_id: UUID,
        receiver_id: UUID,
        amount: Decimal,
        sender_before: Decimal,
        sender_after: Decimal,
        receiver_before: Decimal,
        receiver_after: Decimal,
        created_at: datetime,
    ) -> tuple[UUID, UUID]:

        sender_entry_id = uuid4()
        receiver_entry_id = uuid4()

        rows = (
            {
                "id": sender_entry_id,
                "transfer_id": transfer_id,
                "user_id": sender_id,
                "counterparty_id": receiver_id,
                "entry_type": LedgerEntryType.DEBIT,
                "amount": amount,
                "balance_before": sender_before,
                "balance_after": sender_after,
                "created_at": created_at,
            },
            {
                "id": receiver_entry_id,
                "transfer_id": transfer_id,
                "user_id": receiver_id,
                "counterparty_id": sender_id,
                "entry_type": LedgerEntryType.CREDIT,
                "amount": amount,
                "balance_before": receiver_before,
                "balance_after": receiver_after,
                "created_at": created_at,
            },
        )

        stmt = (
            insert(PaymentLedgerEntryModel)
            .values(rows)
        )

        await self._session.execute(stmt)

        return (
            sender_entry_id,
            receiver_entry_id,
        )

    # =========================================================
    # GET ONE ENTRY
    # =========================================================

    async def get(
        self,
        entry_id: UUID,
    ) -> PaymentLedgerEntryModel | None:

        stmt = (
            select(PaymentLedgerEntryModel)
            .where(
                PaymentLedgerEntryModel.id == entry_id,
            )
            .limit(1)
        )

        return await self._session.scalar(stmt)

    # =========================================================
    # GET ENTRY ID ONLY
    # =========================================================

    async def get_id(
        self,
        entry_id: UUID,
    ) -> UUID | None:

        stmt = (
            select(
                PaymentLedgerEntryModel.id,
            )
            .where(
                PaymentLedgerEntryModel.id == entry_id,
            )
            .limit(1)
        )

        return await self._session.scalar(stmt)

    # =========================================================
    # TRANSFER ENTRIES
    # =========================================================

    async def get_transfer_entries(
        self,
        transfer_id: UUID,
    ):
        """
        Returns the two ledger entries belonging
        to one payment transfer.
        """

        stmt = (
            select(
                PaymentLedgerEntryModel.id,
                PaymentLedgerEntryModel.user_id,
                PaymentLedgerEntryModel.counterparty_id,
                PaymentLedgerEntryModel.entry_type,
                PaymentLedgerEntryModel.amount,
                PaymentLedgerEntryModel.balance_before,
                PaymentLedgerEntryModel.balance_after,
                PaymentLedgerEntryModel.created_at,
            )
            .where(
                PaymentLedgerEntryModel.transfer_id
                == transfer_id,
            )
            .order_by(
                PaymentLedgerEntryModel.id,
            )
        )

        result = await self._session.execute(stmt)

        return result.all()

    # =========================================================
    # USER HISTORY - KEYSET PAGINATION
    # =========================================================

    async def get_user_history(
        self,
        *,
        user_id: UUID,
        counterparty_id: UUID | None = None,
        search_q: str | None = None,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
        limit: int = 50,
    ):
        """
        High-performance user ledger history.

        Uses keyset pagination:

            (created_at, id) < cursor

        Never use OFFSET for large ledger tables.
        """

        limit = min(
            max(limit, 1),
            100,
        )

        Counterparty = aliased(UserModel, name="counterparty")
        stmt = (
            select(
                PaymentLedgerEntryModel.id,
                PaymentLedgerEntryModel.transfer_id,
                PaymentLedgerEntryModel.counterparty_id,
                Counterparty.name.label("counterparty_name"),
                PaymentLedgerEntryModel.entry_type,
                PaymentLedgerEntryModel.amount,
                PaymentLedgerEntryModel.balance_before,
                PaymentLedgerEntryModel.balance_after,
                PaymentLedgerEntryModel.created_at,
                PaymentTransferModel.source_type,
                PaymentTransferModel.payment_method,
            )
            .outerjoin(Counterparty, Counterparty.id == PaymentLedgerEntryModel.counterparty_id)
            .outerjoin(PaymentTransferModel, PaymentTransferModel.id == PaymentLedgerEntryModel.transfer_id)
            .where(
                PaymentLedgerEntryModel.user_id
                == user_id,
            )
        )

        if counterparty_id is not None:
            stmt = stmt.where(
                PaymentLedgerEntryModel.counterparty_id == counterparty_id
            )

        if search_q and search_q.strip():
            kw = f"%{search_q.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    Counterparty.name.ilike(kw),
                    Counterparty.mobile.ilike(kw)
                )
            )

        if start_date is not None:
            stmt = stmt.where(PaymentLedgerEntryModel.created_at >= start_date)
        if end_date is not None:
            stmt = stmt.where(PaymentLedgerEntryModel.created_at <= end_date)

        if (
            cursor_created_at is not None
            and cursor_id is not None
        ):
            stmt = stmt.where(
                (
                    PaymentLedgerEntryModel.created_at,
                    PaymentLedgerEntryModel.id,
                )
                < (
                    cursor_created_at,
                    cursor_id,
                )
            )

        stmt = (
            stmt
            .order_by(
                PaymentLedgerEntryModel.created_at.desc(),
                PaymentLedgerEntryModel.id.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return result.all()

    # =========================================================
    # USER + COUNTERPARTY HISTORY
    # =========================================================

    async def get_pair_history(
        self,
        *,
        user_id: UUID,
        counterparty_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
        cursor_created_at: datetime | None = None,
        cursor_id: UUID | None = None,
        limit: int = 50,
    ):
        """
        Example:

            A -> B
            B -> A

        Both sides are returned from A's perspective.
        """

        limit = min(
            max(limit, 1),
            100,
        )

        stmt = (
            select(
                PaymentLedgerEntryModel.id,
                PaymentLedgerEntryModel.transfer_id,
                PaymentLedgerEntryModel.entry_type,
                PaymentLedgerEntryModel.amount,
                PaymentLedgerEntryModel.balance_before,
                PaymentLedgerEntryModel.balance_after,
                PaymentLedgerEntryModel.created_at,
                PaymentTransferModel.source_type,
                PaymentTransferModel.payment_method,
                PaymentTransferModel.reference,
                PaymentTransferModel.description,
            )
            .outerjoin(
                PaymentTransferModel,
                PaymentTransferModel.id == PaymentLedgerEntryModel.transfer_id,
            )
            .where(
                PaymentLedgerEntryModel.user_id == user_id,
                PaymentLedgerEntryModel.counterparty_id
                == counterparty_id,
            )
        )

        if start_date is not None:
            stmt = stmt.where(PaymentLedgerEntryModel.created_at >= start_date)
        if end_date is not None:
            stmt = stmt.where(PaymentLedgerEntryModel.created_at <= end_date)

        if (
            cursor_created_at is not None
            and cursor_id is not None
        ):
            stmt = stmt.where(
                (
                    PaymentLedgerEntryModel.created_at,
                    PaymentLedgerEntryModel.id,
                )
                < (
                    cursor_created_at,
                    cursor_id,
                )
            )

        stmt = (
            stmt
            .order_by(
                PaymentLedgerEntryModel.created_at.desc(),
                PaymentLedgerEntryModel.id.desc(),
            )
            .limit(limit)
        )

        result = await self._session.execute(stmt)

        return result.all()

    async def get_payment_summary_by_period(
        self,
        user_id: UUID,
        start_date: datetime | None = None,
        end_date: datetime | None = None,
    )->PaymentCollectionSummaryViaPeriodDto:
        ledger = PaymentLedgerEntryModel
        transfer = PaymentTransferModel

        stmt = (
            select(
                func.coalesce(
                    func.sum(
                        case(
                            (ledger.entry_type == LedgerEntryType.CREDIT, ledger.amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_credit_amount"),

                func.coalesce(
                    func.sum(
                        case(
                            (ledger.entry_type == LedgerEntryType.DEBIT, ledger.amount),
                            else_=0,
                        )
                    ),
                    0,
                ).label("total_debit_amount"),

                func.coalesce(
                    func.sum(
                        case(
                            (
                                (ledger.entry_type == LedgerEntryType.DEBIT)
                                & (transfer.source_type == PaymentSourceType.MILK_COLLECTION),
                                ledger.amount,
                            ),
                            else_=0,
                        )
                    ),
                    0,
                ).label("milk_collection_debit_amount"),
            )
            .outerjoin(
                transfer,
                transfer.id == ledger.transfer_id,
            )
            .where(ledger.user_id == user_id)
        )

        if start_date is not None:
            stmt = stmt.where(ledger.created_at >= start_date)

        if end_date is not None:
            stmt = stmt.where(ledger.created_at <= end_date)

        result = (await self._session.execute(stmt)).one()

        return PaymentCollectionSummaryViaPeriodDto(
            total_credit_amount=result.total_credit_amount,
            total_debit_amount=result.total_debit_amount,
            total_collection_amount=result.milk_collection_debit_amount,
        )
        


# class PaymentPairBalanceRepository:

#     __slots__ = ("_session",)

#     def __init__(self, session: AsyncSession) -> None:
#         self._session = session

#     async def upsert_delta(
#         self,
#         *,
#         user_id: UUID,
#         counterparty_id: UUID,
#         delta: Decimal,
#         transfer_id: UUID,
#     ) -> Decimal:

#         stmt = insert(
#             PaymentPairBalanceModel
#         ).values(
#             user_id=user_id,
#             counterparty_id=counterparty_id,
#             balance=delta,
#             version=1,
#             last_transfer_id=transfer_id,
#         )

#         stmt = stmt.on_conflict_do_update(
#             constraint="uq_payment_pair_user_counterparty",
#             set_={
#                 "balance": (
#                     PaymentPairBalanceModel.balance
#                     + stmt.excluded.balance
#                 ),
#                 "version": (
#                     PaymentPairBalanceModel.version + 1
#                 ),
#                 "last_transfer_id": (
#                     stmt.excluded.last_transfer_id
#                 ),
#                 "updated_at": now_naive_ist(),
#             },
#         ).returning(
#             PaymentPairBalanceModel.balance
#         )

#         result = await self._session.execute(stmt)

#         return result.scalar_one()

class PaymentPairBalanceRepository:

    __slots__ = ("_session",)

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session

    # =========================================================
    # UPSERT DELTA
    # =========================================================

    async def upsert_delta(
        self,
        *,
        user_id: UUID,
        counterparty_id: UUID,
        delta: Decimal,
        transfer_id: UUID,
    ) -> Decimal:
        """
        Atomically applies delta to a user/counterparty pair.

        Example:

            A -> B ₹5000

            A → B = -5000
            B → A = +5000

        Existing pair:
            balance = old_balance + delta

        New pair:
            balance = delta

        Returns:
            New pair balance.
        """

        insert_stmt = (
            insert(PaymentPairBalanceModel)
            .values(
                user_id=user_id,
                counterparty_id=counterparty_id,
                balance=delta,
                version=1,
                last_transfer_id=transfer_id,
            )
        )

        stmt = (
            insert_stmt.on_conflict_do_update(
                # Name the conflict columns, not the constraint name: SQLite does
                # not support "ON CONFLICT ON CONSTRAINT <name>".
                index_elements=[
                    PaymentPairBalanceModel.user_id,
                    PaymentPairBalanceModel.counterparty_id,
                ],
                set_={
                    "balance": (
                        PaymentPairBalanceModel.balance
                        + insert_stmt.excluded.balance
                    ),
                    "version": (
                        PaymentPairBalanceModel.version
                        + 1
                    ),
                    "last_transfer_id": (
                        insert_stmt.excluded.last_transfer_id
                    ),
                    "updated_at": now_naive_ist(),
                },
            )
        )

        await self._session.execute(stmt)

        # Read the resulting balance back (no RETURNING for SQLite compatibility).
        return await self._session.scalar(
            select(PaymentPairBalanceModel.balance).where(
                PaymentPairBalanceModel.user_id == user_id,
                PaymentPairBalanceModel.counterparty_id == counterparty_id,
            )
        )

    # =========================================================
    # UPSERT TWO SIDES
    # =========================================================

    async def apply_transfer(
        self,
        *,
        sender_id: UUID,
        receiver_id: UUID,
        amount: Decimal,
        transfer_id: UUID,
    ) -> tuple[Decimal, Decimal]:
        """
        Updates both sides:

            sender   -> receiver = -amount
            receiver -> sender   = +amount

        """

        sender_pair = (
            sender_id,
            receiver_id,
        )

        receiver_pair = (
            receiver_id,
            sender_id,
        )

        # -----------------------------------------------------
        # Deterministic ordering
        #
        # Important for concurrency/deadlock avoidance.
        # -----------------------------------------------------

        pairs = sorted(
            (
                (
                    sender_pair[0],
                    sender_pair[1],
                    -amount,
                ),
                (
                    receiver_pair[0],
                    receiver_pair[1],
                    amount,
                ),
            ),
            key=lambda item: (
                item[0],
                item[1],
            ),
        )

        results: dict[
            tuple[UUID, UUID],
            Decimal,
        ] = {}

        for (
            user_id,
            counterparty_id,
            delta,
        ) in pairs:

            balance = await self.upsert_delta(
                user_id=user_id,
                counterparty_id=counterparty_id,
                delta=delta,
                transfer_id=transfer_id,
            )

            results[
                (
                    user_id,
                    counterparty_id,
                )
            ] = balance

        return (
            results[sender_pair],
            results[receiver_pair],
        )

    # =========================================================
    # GET CURRENT PAIR BALANCE
    # =========================================================

    async def get(
        self,
        *,
        user_id: UUID,
        counterparty_id: UUID,
    ) -> Decimal | None:

        stmt = (
            select(
                PaymentPairBalanceModel.balance,
            )
            .where(
                PaymentPairBalanceModel.user_id
                == user_id,
                PaymentPairBalanceModel.counterparty_id
                == counterparty_id,
            )
            .limit(1)
        )

        return await self._session.scalar(stmt)

    # =========================================================
    # GET FULL PAIR ROW
    # =========================================================

    async def get_details(
        self,
        *,
        user_id: UUID,
        counterparty_id: UUID,
    ):

        stmt = (
            select(
                PaymentPairBalanceModel.id,
                PaymentPairBalanceModel.user_id,
                PaymentPairBalanceModel.counterparty_id,
                PaymentPairBalanceModel.balance,
                PaymentPairBalanceModel.version,
                PaymentPairBalanceModel.last_transfer_id,
                PaymentPairBalanceModel.updated_at,
            )
            .where(
                PaymentPairBalanceModel.user_id
                == user_id,
                PaymentPairBalanceModel.counterparty_id
                == counterparty_id,
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)

        return result.one_or_none()

    # =========================================================
    # LOCK PAIR
    # =========================================================

    async def get_for_update(
        self,
        *,
        user_id: UUID,
        counterparty_id: UUID,
    ):

        stmt = (
            select(
                PaymentPairBalanceModel.id,
                PaymentPairBalanceModel.balance,
                PaymentPairBalanceModel.version,
            )
            .where(
                PaymentPairBalanceModel.user_id
                == user_id,
                PaymentPairBalanceModel.counterparty_id
                == counterparty_id,
            )
            .with_for_update()
        )

        result = await self._session.execute(stmt)

        return result.one_or_none()

    # =========================================================
    # USER ALL OUTSTANDING
    # =========================================================

    async def get_user_outstanding(
        self,
        *,
        user_id: UUID,
        include_zero: bool = False,
    ):

        Counterparty = aliased(UserModel, name="counterparty")
        stmt = (
            select(
                PaymentPairBalanceModel.counterparty_id,
                Counterparty.name.label("counterparty_name"),
                PaymentPairBalanceModel.balance,
                PaymentPairBalanceModel.updated_at,
            )
            .outerjoin(Counterparty, Counterparty.id == PaymentPairBalanceModel.counterparty_id)
            .where(
                PaymentPairBalanceModel.user_id
                == user_id,
            )
        )

        if not include_zero:
            stmt = stmt.where(
                PaymentPairBalanceModel.balance != 0
            )

        stmt = stmt.order_by(
            PaymentPairBalanceModel.updated_at.desc()
        )

        result = await self._session.execute(stmt)

        return result.all()

    # =========================================================
    # DELETE ZERO BALANCE PAIR
    # =========================================================

    async def delete_zero_balance(
        self,
        *,
        user_id: UUID,
        counterparty_id: UUID,
    ) -> bool:

        stmt = (
            update(PaymentPairBalanceModel)
            .where(
                PaymentPairBalanceModel.user_id
                == user_id,
                PaymentPairBalanceModel.counterparty_id
                == counterparty_id,
                PaymentPairBalanceModel.balance == 0,
            )
            .values(
                last_transfer_id=None,
            )
        )

        result = await self._session.execute(stmt)

        return result.rowcount == 1