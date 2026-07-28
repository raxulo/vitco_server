"""
RealTimeTransfer
================

DeviceRepository subclassing BaseRepository

Python 3.13+
"""

from __future__ import annotations

from app.core.database.repository.base import BaseRepository
from app.models.device import Device


class DeviceRepository(BaseRepository[Device]):
    """
    Device entity repository for database operations.
    """
    __slots__ = ()
