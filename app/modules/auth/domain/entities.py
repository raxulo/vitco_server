"""
Auth Domain Entities

Enterprise Authentication Module

Python 3.13+
"""

from __future__ import annotations


from dataclasses import (
    dataclass,
    field,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import UUID



__all__ = (
    "User",
    "RefreshToken",
    "OTP",
)



# ============================================================
# User Entity
# ============================================================


@dataclass(
    slots=True,
)
class User:
    """
    User business entity.
    """


    id: UUID | None

    email: str

    username: str

    password_hash: str


    is_active: bool = True

    is_verified: bool = False


    created_at: datetime | None = None

    updated_at: datetime | None = None


    last_login_at: datetime | None = None



    # --------------------------------------------------------

    def activate(self) -> None:
        """
        Activate user account.
        """

        self.is_active = True



    def deactivate(self) -> None:
        """
        Disable user account.
        """

        self.is_active = False



    def verify_email(self) -> None:
        """
        Mark email verified.
        """

        self.is_verified = True



    def update_last_login(self) -> None:
        """
        Update login timestamp.
        """

        self.last_login_at = datetime.now(
            timezone.utc
        )



    def can_login(self) -> bool:
        """
        Login eligibility rule.
        """

        return (
            self.is_active
            and
            self.is_verified
        )



# ============================================================
# Refresh Token Entity
# ============================================================


@dataclass(
    slots=True,
)
class RefreshToken:
    """
    Refresh token business entity.
    """


    id: UUID | None


    user_id: UUID


    token_hash: str


    expires_at: datetime


    revoked: bool = False



    def revoke(self) -> None:
        """
        Invalidate token.
        """

        self.revoked = True



    def is_expired(self) -> bool:

        return (
            datetime.now(
                timezone.utc
            )
            >
            self.expires_at
        )



    def is_valid(self) -> bool:

        return (
            not self.revoked
            and
            not self.is_expired()
        )



# ============================================================
# OTP Entity
# ============================================================


@dataclass(
    slots=True,
)
class OTP:
    """
    OTP verification entity.
    """


    id: UUID | None


    user_id: UUID


    otp_hash: str


    purpose: str


    expires_at: datetime


    attempts: int = 0


    verified: bool = False



    MAX_ATTEMPTS: int = field(
        default=5,
        init=False,
        repr=False,
    )



    def increase_attempt(
        self,
    ) -> None:

        self.attempts += 1



    def verify(
        self,
    ) -> None:

        self.verified = True



    def is_expired(
        self,
    ) -> bool:


        return (
            datetime.now(
                timezone.utc
            )
            >
            self.expires_at
        )



    def can_attempt(
        self,
    ) -> bool:


        return (
            self.attempts
            <
            self.MAX_ATTEMPTS
        )