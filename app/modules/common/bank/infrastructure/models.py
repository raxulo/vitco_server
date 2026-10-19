"""
Admin Entity
"""

from sqlalchemy import ForeignKey
from app.core.database.base import Base
from app.core.database.mixins import TimestampMixin, UUIDMixin

from sqlalchemy import String
from sqlalchemy.orm import mapped_column

class BankAccountModel( Base, UUIDMixin, TimestampMixin ):

    __tablename__ = "bank_accounts"

    user_id = mapped_column(
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    account_holder = mapped_column(
        String(150),
        nullable=False,
    )

    bank_name = mapped_column(
        String(150),
        nullable=True,
    )

    account_number = mapped_column(
        String(30),
        nullable=True,
    )

    ifsc_code = mapped_column(
        String(20),
        nullable=True,
    )

    upi_id = mapped_column(
        String(100),
        nullable=True
    )