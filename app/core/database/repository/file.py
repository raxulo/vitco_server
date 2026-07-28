"""
RealTimeTransfer
================

FileRepository subclassing BaseRepository

Python 3.13+
"""

from __future__ import annotations

from app.core.database.repository.base import BaseRepository
from app.models.file import File


class FileRepository(BaseRepository[File]):
    """
    File entity repository for database operations.
    """
    __slots__ = ()
