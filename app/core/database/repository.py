"""
RealTimeTransfer
================

Repository Registry

Python 3.13+
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.file import File
from app.models.device import Device
from app.models.otp import OTP

from app.core.database.repository.user import UserRepository
from app.core.database.repository.file import FileRepository
from app.core.database.repository.device import DeviceRepository
from app.core.database.repository.otp import OTPRepository


class RepositoryRegistry:
    """
    Creates one repository instance per session.
    """

    __slots__ = (
        "_session",
        "_users",
        "_files",
        "_devices",
        "_otps",
    )

    def __init__(
        self,
        session: AsyncSession,
    ) -> None:
        self._session = session
        self._users = None
        self._files = None
        self._devices = None
        self._otps = None

    @property
    def users(self) -> UserRepository:
        if self._users is None:
            self._users = UserRepository(
                self._session,
                User,
            )
        return self._users

    @property
    def files(self) -> FileRepository:
        if self._files is None:
            self._files = FileRepository(
                self._session,
                File,
            )
        return self._files

    @property
    def devices(self) -> DeviceRepository:
        if self._devices is None:
            self._devices = DeviceRepository(
                self._session,
                Device,
            )
        return self._devices

    @property
    def otps(self) -> OTPRepository:
        if self._otps is None:
            self._otps = OTPRepository(
                self._session,
                OTP,
            )
        return self._otps