"""
Auth Database Models

Enterprise Authentication Module

Python 3.13+
SQLAlchemy 2.x
"""

from __future__ import annotations


from datetime import datetime

from typing import TYPE_CHECKING


from sqlalchemy import (
    Boolean,
    ForeignKey,
    Index,
    String,
    Text,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
    relationship,
)


from app.core.database.base import Base

from app.core.database.mixins import (
    TimestampMixin,
    UUIDMixin,
)

from app.core.database.types import (
    GUID,
    NaiveDateTime,
)



if TYPE_CHECKING:

    from typing import List



# ============================================================
# User
# ============================================================


class UserModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    """
    Application User.
    """


    __tablename__ = "users"


    __table_args__ = (

        Index(
            "ix_users_email",
            "email",
            unique=True,
        ),

        Index(
            "ix_users_username",
            "username",
            unique=True,
        ),

    )


    email: Mapped[str] = mapped_column(

        String(255),

        nullable=False,

        unique=True,

    )


    username: Mapped[str] = mapped_column(

        String(100),

        nullable=False,

        unique=True,

    )


    password_hash: Mapped[str] = mapped_column(

        Text,

        nullable=False,

    )


    is_active: Mapped[bool] = mapped_column(

        Boolean,

        default=True,

        nullable=False,

    )


    is_verified: Mapped[bool] = mapped_column(

        Boolean,

        default=False,

        nullable=False,

    )


    last_login_at: Mapped[datetime | None] = mapped_column(
        NaiveDateTime(),
        nullable=True,
    )


    # --------------------------------------------------------
    # Relationships
    # --------------------------------------------------------


    refresh_tokens: Mapped[list["RefreshTokenModel"]] = relationship(

        back_populates="user",

        cascade="all, delete-orphan",

    )


    otps: Mapped[list["OTPModel"]] = relationship(

        back_populates="user",

        cascade="all, delete-orphan",

    )



# ============================================================
# Refresh Token
# ============================================================


class RefreshTokenModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    """
    JWT Refresh Token Storage.
    """


    __tablename__ = "refresh_tokens"


    __table_args__ = (

        Index(
            "ix_refresh_token_hash",
            "token_hash",
            unique=True,
        ),

        Index(
            "ix_refresh_token_user",
            "user_id",
        ),

    )



    user_id: Mapped[str] = mapped_column(

        GUID(),

        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),

        nullable=False,

    )



    token_hash: Mapped[str] = mapped_column(

        String(255),

        nullable=False,

    )



    expires_at: Mapped[datetime] = mapped_column(

        NaiveDateTime(),

        nullable=False,

    )


    revoked: Mapped[bool] = mapped_column(

        Boolean,

        default=False,

        nullable=False,

    )


    user: Mapped["UserModel"] = relationship(

        back_populates="refresh_tokens",

    )



# ============================================================
# OTP
# ============================================================


class OTPModel(
    Base,
    UUIDMixin,
    TimestampMixin,
):

    """
    One Time Password Storage.
    """


    __tablename__ = "otps"


    __table_args__ = (

        Index(
            "ix_otp_user",
            "user_id",
        ),

    )



    user_id: Mapped[str] = mapped_column(

        GUID(),

        ForeignKey(
            "users.id",
            ondelete="CASCADE",
        ),

        nullable=False,

    )


    otp_hash: Mapped[str] = mapped_column(

        String(255),

        nullable=False,

    )


    purpose: Mapped[str] = mapped_column(

        String(50),

        nullable=False,

    )


    expires_at: Mapped[datetime] = mapped_column(

        NaiveDateTime(),

        nullable=False,

    )


    attempts: Mapped[int] = mapped_column(

        default=0,

        nullable=False,

    )


    verified: Mapped[bool] = mapped_column(

        Boolean,

        default=False,

        nullable=False,

    )


    user: Mapped["UserModel"] = relationship(

        back_populates="otps",

    )