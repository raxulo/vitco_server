"""
RealTimeTransfer
================

UserRepository subclassing BaseRepository

Python 3.13+
"""

from __future__ import annotations

from app.core.database.repository.base import BaseRepository
from app.models.user import User


class UserRepository(BaseRepository[User]):
    """
    User entity repository for database operations.
    """
    __slots__ = ()
