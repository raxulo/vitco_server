# =========================================================
# ACCOUNT BALANCE
# =========================================================

from app.modules.payments.domain.enums import PaymentTransferStatus
from sqlalchemy import Text
from sqlalchemy import String
from app.modules.payments.domain.enums import PaymentMethod
from app.modules.payments.domain.enums import PaymentSourceType
from sqlalchemy import UniqueConstraint
from sqlalchemy import BigInteger
from sqlalchemy import ForeignKey
from sqlalchemy import Enum
from uuid import UUID
from app.modules.payments.domain.enums import LedgerEntryType
from sqlalchemy import Numeric
from decimal import Decimal
from sqlalchemy import DateTime
from datetime import datetime
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column
from sqlalchemy import CheckConstraint
from sqlalchemy import Index
from app.core.database.mixins import TimestampMixin
from app.core.database.mixins import UUIDMixin
from app.core.database.base import Base


class AccountBalanceModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    __tablename__ = "account_balances"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
        unique=True,
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_ledger_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "payment_ledger_entries.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )


class PaymentTransferModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    __tablename__ = "payment_transfers"

    # -----------------------------------------------------
    # SENDER
    # -----------------------------------------------------

    sender_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # -----------------------------------------------------
    # RECEIVER
    # -----------------------------------------------------

    receiver_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    # -----------------------------------------------------
    # AMOUNT
    # -----------------------------------------------------

    amount: Mapped[Decimal] = mapped_column(
        Numeric(
            precision=20,
            scale=2,
        ),
        nullable=False,
    )

    # -----------------------------------------------------
    # BUSINESS SOURCE
    #
    # MANUAL
    # MILK_COLLECTION
    # ADJUSTMENT
    # REVERSAL
    # -----------------------------------------------------

    source_type: Mapped[PaymentSourceType] = mapped_column(
        Enum(
            PaymentSourceType,
        ),
        nullable=False,
    )

    # -----------------------------------------------------
    # PAYMENT METHOD
    #
    # CASH
    # UPI
    # BANK
    # SYSTEM
    # -----------------------------------------------------

    payment_method: Mapped[PaymentMethod] = mapped_column(
        Enum(
            PaymentMethod,
            name="payment_method_enum",
        ),
        nullable=False,
    )

    # -----------------------------------------------------
    # SOURCE ID
    #
    # Example:
    # MilkCollection.id
    # Adjustment.id
    # -----------------------------------------------------

    source_id: Mapped[UUID | None] = mapped_column(
        nullable=True,
    )

    # -----------------------------------------------------
    # IDEMPOTENCY KEY
    # -----------------------------------------------------

    idempotency_key: Mapped[str] = mapped_column(
        String(100),
        nullable=False,
        unique=True,
    )

    # -----------------------------------------------------
    # EXTERNAL REFERENCE
    # -----------------------------------------------------

    reference: Mapped[str | None] = mapped_column(
        String(100),
        nullable=True,
    )

    # -----------------------------------------------------
    # DESCRIPTION
    # -----------------------------------------------------

    description: Mapped[str | None] = mapped_column(
        Text,
        nullable=True,
    )

    # -----------------------------------------------------
    # STATUS
    # -----------------------------------------------------

    status: Mapped[PaymentTransferStatus] = mapped_column(
        Enum(
            PaymentTransferStatus,
            name="payment_transfer_status_enum",
        ),
        nullable=False,
        default=PaymentTransferStatus.PENDING,
    )


    __table_args__ = (

        CheckConstraint(
            "amount > 0",
            name="ck_payment_transfer_positive_amount",
        ),

        CheckConstraint(
            "sender_id <> receiver_id",
            name="ck_payment_transfer_different_users",
        ),

        Index(
            "ix_payment_transfer_sender_created",
            "sender_id",
            "created_at",
        ),

        Index(
            "ix_payment_transfer_receiver_created",
            "receiver_id",
            "created_at",
        ),

        Index(
            "ix_payment_transfer_pair_created",
            "sender_id",
            "receiver_id",
            "created_at",
        ),

        Index(
            "ix_payment_transfer_source",
            "source_type",
            "source_id",
        ),
    )


class PaymentLedgerEntryModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    __tablename__ = "payment_ledger_entries"

    transfer_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "payment_transfers.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    counterparty_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="RESTRICT",
        ),
        nullable=False,
    )

    entry_type: Mapped[LedgerEntryType] = mapped_column(
        Enum(
            LedgerEntryType,
            name="payment_ledger_entry_type_enum",
        ),
        nullable=False,
    )

    amount: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
    )

    balance_before: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
    )

    balance_after: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
    )
    
    __table_args__ = (
        CheckConstraint(
            "amount > 0",
            name="ck_payment_ledger_positive_amount",
        ),

        CheckConstraint(
            "user_id <> counterparty_id",
            name="ck_payment_ledger_different_users",
        ),

        Index(
            "ix_payment_ledger_transfer",
            "transfer_id",
        ),

        Index(
            "ix_payment_ledger_user_created",
            "user_id",
            "created_at",
        ),

        Index(
            "ix_payment_ledger_user_counterparty_created",
            "user_id",
            "counterparty_id",
            "created_at",
        ),
    )
class PaymentPairBalanceModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):
    __tablename__ = "payment_pair_balances"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    counterparty_id: Mapped[UUID] = mapped_column(
        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),
        nullable=False,
    )

    balance: Mapped[Decimal] = mapped_column(
        Numeric(20, 2),
        nullable=False,
        default=Decimal("0.00"),
        server_default="0.00",
    )

    version: Mapped[int] = mapped_column(
        BigInteger,
        nullable=False,
        default=0,
        server_default="0",
    )

    last_transfer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey(
            "payment_transfers.id",
            ondelete="SET NULL",
        ),
        nullable=True,
    )

    __table_args__ = (
        UniqueConstraint(
            "user_id",
            "counterparty_id",
            name="uq_payment_pair_user_counterparty",
        ),

        CheckConstraint(
            "user_id <> counterparty_id",
            name="ck_payment_pair_different_users",
        ),

        Index(
            "ix_payment_pair_user_balance",
            "user_id",
            "balance",
        ),

        Index(
            "ix_payment_pair_user_updated",
            "user_id",
            "updated_at",
        ),
    )