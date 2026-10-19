"""
Settings Application Handlers
"""

from app.modules.administration.domain.enums import Role
from uuid import UUID, uuid4

from app.modules.common.settings.application.dto import (
    CreateSettingsCommand,
    UpdateSettingsCommand,
)

from app.modules.common.settings.domain.exceptions import (
    SettingsNotFoundError,
)

from app.modules.common.settings.domain.entities import Settings
from app.modules.common.settings.infrastructure.repository import (
    SettingsRepository,
)


class SettingsHandler:

    __slots__ = ("_repository",)

    def __init__(
        self,
        repository: SettingsRepository,
    ) -> None:

        self._repository = repository

    # =========================================================
    # Create
    # =========================================================

    async def create(
        self,
        command: CreateSettingsCommand,
    ) -> Settings:

        settings = Settings(
            id=uuid4(),

            analyzer_type=(
                command.analyzer_type
            ),

            analyzer_collection_mode=(
                command.analyzer_collection_mode
            ),

            weight_unit=(
                command.weight_unit
            ),

            weight_collection_mode=(
                command.weight_collection_mode
            ),

            auto_tare_enabled=(
                command.auto_tare_enabled
            ),

            morning_collection_start=(
                command.morning_collection_start
            ),

            morning_collection_end=(
                command.morning_collection_end
            ),

            evening_collection_start=(
                command.evening_collection_start
            ),

            evening_collection_end=(
                command.evening_collection_end
            ),

            receipt_size=(
                command.receipt_size
            ),

            printer_type=(
                command.printer_type
            ),

            printer_enabled=(
                command.printer_enabled
            ),

            cattle_type=(
                command.cattle_type
            ),

            max_rate_chart_count=(
                command.max_rate_chart_count
            ),

            settings_edit_enabled=(
                command.settings_edit_enabled
            ),

            rate_chart_edit_enabled=(
                command.rate_chart_edit_enabled
            ),

            master_enabled=(
                command.master_enabled
            ),
        )

        # Business validation
        settings.validate()

        await self._repository.create(
            settings
        )

        return settings

    # =========================================================
    # Get
    # =========================================================

    async def get_by_id(
        self,
        settings_id: UUID,
    ) -> Settings:

        settings = await self._repository.get_by_id(
            settings_id
        )

        if settings is None:
            raise SettingsNotFoundError(
                settings_id
            )

        return settings

    async def get_by_user_id(
        self,
        user_id: UUID,
        user_type: Role,
    ) -> Settings:

        settings = await self._repository.get_by_user_id(
            user_id,
            user_type,
        )

        if settings is None:
            raise SettingsNotFoundError(
                f"Settings not found for user: {user_id} and type: {user_type}"
            )

        return settings


    # =========================================================
    # Update
    # =========================================================

    async def update(
        self,
        command: UpdateSettingsCommand,
    ) -> Settings:

        settings = await self.get_by_id(
            command.settings_id
        )

        settings.analyzer_type = (
            command.analyzer_type
        )

        settings.analyzer_collection_mode = (
            command.analyzer_collection_mode
        )

        settings.weight_unit = (
            command.weight_unit
        )

        settings.weight_collection_mode = (
            command.weight_collection_mode
        )

        settings.auto_tare_enabled = (
            command.auto_tare_enabled
        )

        settings.morning_collection_start = (
            command.morning_collection_start
        )

        settings.morning_collection_end = (
            command.morning_collection_end
        )

        settings.evening_collection_start = (
            command.evening_collection_start
        )

        settings.evening_collection_end = (
            command.evening_collection_end
        )

        settings.receipt_size = (
            command.receipt_size
        )

        settings.printer_type = (
            command.printer_type
        )

        settings.printer_enabled = (
            command.printer_enabled
        )

        settings.cattle_type = (
            command.cattle_type
        )

        settings.max_rate_chart_count = (
            command.max_rate_chart_count
        )

        settings.settings_edit_enabled = (
            command.settings_edit_enabled
        )

        settings.rate_chart_edit_enabled = (
            command.rate_chart_edit_enabled
        )

        settings.master_enabled = (
            command.master_enabled
        )

        # Revalidate complete state
        settings.validate()

        await self._repository.update(
            settings
        )

        return settings

    # =========================================================
    # Delete
    # =========================================================

    async def delete(
        self,
        settings_id: UUID,
    ) -> None:

        settings = await self.get_by_id(
            settings_id
        )

        deleted = await self._repository.delete(
            settings.id
        )

        if not deleted:
            raise SettingsNotFoundError(
                settings_id
            )