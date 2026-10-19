"""
Settings Repository Port

Application-layer abstraction for Settings persistence.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.common.settings.domain.entities import Settings


class ISettingsRepository(ABC):

    # =========================================================
    # Create
    # =========================================================

    @abstractmethod
    async def create(
        self,
        settings: Settings,
    ) -> Settings:
        raise NotImplementedError

    # =========================================================
    # Get
    # =========================================================

    @abstractmethod
    async def get_by_id(
        self,
        settings_id: UUID,
    ) -> Settings | None:
        raise NotImplementedError

    # =========================================================
    # Exists
    # =========================================================

    @abstractmethod
    async def exists(
        self,
        settings_id: UUID,
    ) -> bool:
        raise NotImplementedError

    # =========================================================
    # Update
    # =========================================================

    @abstractmethod
    async def update(
        self,
        settings: Settings,
    ) -> Settings:
        raise NotImplementedError

    # =========================================================
    # Delete
    # =========================================================

    @abstractmethod
    async def delete(
        self,
        settings_id: UUID,
    ) -> bool:
        raise NotImplementedError