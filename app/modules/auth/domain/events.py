"""
Auth Domain Events

Enterprise Authentication Module

Python 3.13+
"""

from __future__ import annotations


from dataclasses import (
    dataclass,
)

from datetime import (
    datetime,
    timezone,
)

from uuid import UUID



__all__ = (
    "DomainEvent",
    "UserRegisteredEvent",
    "UserLoginEvent",
    "PasswordResetEvent",
    "EmailVerifiedEvent",
)



# ============================================================
# Base Event
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class DomainEvent:
    """
    Base domain event.
    """

    occurred_at: datetime = (
        datetime.now(
            timezone.utc
        )
    )



# ============================================================
# User Registered
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UserRegisteredEvent(
    DomainEvent,
):

    user_id: UUID

    email: str



# ============================================================
# User Login
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class UserLoginEvent(
    DomainEvent,
):

    user_id: UUID

    ip_address: str | None = None



# ============================================================
# Password Reset
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class PasswordResetEvent(
    DomainEvent,
):

    user_id: UUID



# ============================================================
# Email Verification
# ============================================================


@dataclass(
    frozen=True,
    slots=True,
)
class EmailVerifiedEvent(
    DomainEvent,
):

    user_id: UUID