"""
Settings Repository

Persistence operations for Settings.
"""

from app.modules.vlcc.infrastructure.models import VlccModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.administration.domain.enums import Role
from app.modules.common.settings.domain.enums import *
from sqlalchemy import update
from app.modules.common.settings.application.dto import UpdateSettingsCommand

from app.core.database.manager import DatabaseManager

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.common.settings.domain.entities import Settings
from app.modules.common.settings.infrastructure.mapper import SettingsMapper
from app.modules.common.settings.infrastructure.models import SettingsModel


class SettingsRepository:

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self._database = database

    # =========================================================
    # Create
    # =========================================================
    
    @property
    def _session(self) -> AsyncSession:
        return self._database.session
    
    async def create(
        self,
        settings: Settings,
    ) -> Settings:

        model = SettingsMapper.to_model(settings)

        self._session.add(model)

        return settings

    # =========================================================
    # Get By ID
    # =========================================================

    async def get_by_id(
        self,
        settings_id: UUID,
    ) -> Settings | None:

        stmt = (
            select(SettingsModel)
            .where(
                SettingsModel.id == settings_id
            )
        )

        result = await self._session.execute(stmt)

        model = result.scalar_one_or_none()

        if model is None:
            return None

        return SettingsMapper.to_entity(model)

    # =========================================================
    # Get By User ID
    # =========================================================

    async def get_by_user_id(
        self,
        user_id: UUID,
        user_type: Role,
    ) -> Settings | None:

        if user_type == Role.MCC:
            stmt = (
                select(SettingsModel)
                .join(MccModel, MccModel.settings_id == SettingsModel.id)
                .where(MccModel.user_id == user_id)
            )

        elif user_type == Role.VLCC:
            stmt = (
                select(SettingsModel)
                .join(VlccModel, VlccModel.settings_id == SettingsModel.id)
                .where(VlccModel.user_id == user_id)
            )

        else:
            return None

        result = await self._session.execute(stmt)

        model = result.scalar_one_or_none()

        if model is None:
            return None

        return SettingsMapper.to_entity(model)
        

    # =========================================================
    # Exists
    # =========================================================

    async def exists(
        self,
        settings_id: UUID,
    ) -> bool:

        stmt = (
            select(SettingsModel.id)
            .where(
                SettingsModel.id == settings_id
            )
            .limit(1)
        )

        result = await self._session.execute(stmt)

        return result.scalar_one_or_none() is not None

    # =========================================================
    # Update
    # =========================================================

    async def update(
        self,
        settings: Settings,
    ) -> Settings:

        stmt = (
            select(SettingsModel)
            .where(
                SettingsModel.id == settings.id
            )
        )

        result = await self._session.execute(stmt)

        model = result.scalar_one_or_none()

        if model is None:
            raise ValueError(
                f"Settings not found: {settings.id}"
            )

        SettingsMapper.update_model(
            model,
            settings,
        )

        return settings

    async def update_by_command(self, command: UpdateSettingsCommand) -> Settings:
        stmt = (
            update(SettingsModel).
            where(SettingsModel.id == command.settings_id).
            values(
            analyzer_type = command.analyzer_type,
            analyzer_collection_mode = command.analyzer_collection_mode,
            weight_unit = command.weight_unit,
            weight_collection_mode = command.weight_collection_mode,
            auto_tare_enabled = command.auto_tare_enabled,
            morning_collection_start = command.morning_collection_start,
            morning_collection_end = command.morning_collection_end,

            evening_collection_start = command.evening_collection_start,

            evening_collection_end = command.evening_collection_end,

            receipt_size = command.receipt_size,

            printer_type = command.printer_type,

            printer_enabled = command.printer_enabled,

            cattle_type = command.cattle_type,

            max_rate_chart_count = command.max_rate_chart_count,

            settings_edit_enabled = command.settings_edit_enabled,

            rate_chart_edit_enabled = command.rate_chart_edit_enabled,

            master_enabled = command.master_enabled
            )
        )
        result = await self._session.execute(stmt)
        if result.rowcount == 0:
            raise ValueError(f"Settings not found: {command.id}")
        return await self.get_by_id(command.settings_id)

    # =========================================================
    # Delete
    # =========================================================

    async def delete(
        self,
        settings_id: UUID,
    ) -> bool:

        stmt = (
            select(SettingsModel)
            .where(
                SettingsModel.id == settings_id
            )
        )

        result = await self._session.execute(stmt)

        model = result.scalar_one_or_none()

        if model is None:
            return False

        await self._session.delete(model)

        return True