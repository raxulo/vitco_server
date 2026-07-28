"""
RealTimeTransfer
================

OTPRepository subclassing BaseRepository

Python 3.13+
"""

from __future__ import annotations

from app.core.database.repository.base import BaseRepository
from app.models.otp import OTP


class OTPRepository(BaseRepository[OTP]):
    """
    OTP entity repository for database operations.
    """
    __slots__ = ()
