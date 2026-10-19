"""
Settings Mapper

Converts between:

    Settings Domain Entity
            ↕
    SettingsModel SQLAlchemy Entity
"""

from __future__ import annotations

from app.modules.common.settings.domain.entities import Settings
from app.modules.common.settings.infrastructure.models import SettingsModel


class SettingsMapper:
    """
    Domain ↔ Persistence mapper for Settings.
    """

    __slots__ = ()

    # =========================================================
    # Model → Domain
    # =========================================================

    @staticmethod
    def to_entity(
        model: SettingsModel,
    ) -> Settings:

        return Settings(
            id=model.id,

            analyzer_type=model.analyzer_type,

            analyzer_collection_mode=(
                model.analyzer_collection_mode
            ),

            weight_unit=model.weight_unit,

            weight_collection_mode=(
                model.weight_collection_mode
            ),

            auto_tare_enabled=(
                model.auto_tare_enabled
            ),

            morning_collection_start=(
                model.morning_collection_start
            ),

            morning_collection_end=(
                model.morning_collection_end
            ),

            evening_collection_start=(
                model.evening_collection_start
            ),

            evening_collection_end=(
                model.evening_collection_end
            ),

            receipt_size=model.receipt_size,

            printer_type=model.printer_type,

            printer_enabled=model.printer_enabled,

            cattle_type=(
                model.cattle_type
            ),

            max_rate_chart_count=(
                model.max_rate_chart_count
            ),

            settings_edit_enabled=(
                model.settings_edit_enabled
            ),

            rate_chart_edit_enabled=(
                model.rate_chart_edit_enabled
            ),

            master_enabled=(
                model.master_enabled
            ),
        )

    # =========================================================
    # Domain → Model
    # =========================================================

    @staticmethod
    def to_model(
        entity: Settings,
    ) -> SettingsModel:

        return SettingsModel(
            id=entity.id,

            analyzer_type=entity.analyzer_type,

            analyzer_collection_mode=(
                entity.analyzer_collection_mode
            ),

            weight_unit=entity.weight_unit,

            weight_collection_mode=(
                entity.weight_collection_mode
            ),

            auto_tare_enabled=(
                entity.auto_tare_enabled
            ),

            morning_collection_start=(
                entity.morning_collection_start
            ),

            morning_collection_end=(
                entity.morning_collection_end
            ),

            evening_collection_start=(
                entity.evening_collection_start
            ),

            evening_collection_end=(
                entity.evening_collection_end
            ),

            receipt_size=entity.receipt_size,

            printer_type=entity.printer_type,

            printer_enabled=entity.printer_enabled,

            cattle_type=(
                entity.cattle_type
            ),

            max_rate_chart_count=(
                entity.max_rate_chart_count
            ),

            settings_edit_enabled=(
                entity.settings_edit_enabled
            ),

            rate_chart_edit_enabled=(
                entity.rate_chart_edit_enabled
            ),

            master_enabled=(
                entity.master_enabled
            ),
        )

    # =========================================================
    # Update existing model
    # =========================================================

    @staticmethod
    def update_model(
        model: SettingsModel,
        entity: Settings,
    ) -> SettingsModel:

        model.analyzer_type = entity.analyzer_type

        model.analyzer_collection_mode = (
            entity.analyzer_collection_mode
        )

        model.weight_unit = entity.weight_unit

        model.weight_collection_mode = (
            entity.weight_collection_mode
        )

        model.auto_tare_enabled = (
            entity.auto_tare_enabled
        )

        model.morning_collection_start = (
            entity.morning_collection_start
        )

        model.morning_collection_end = (
            entity.morning_collection_end
        )

        model.evening_collection_start = (
            entity.evening_collection_start
        )

        model.evening_collection_end = (
            entity.evening_collection_end
        )

        model.receipt_size = entity.receipt_size

        model.printer_type = entity.printer_type

        model.printer_enabled = (
            entity.printer_enabled
        )

        model.cattle_type = (
            entity.cattle_type
        )

        model.max_rate_chart_count = (
            entity.max_rate_chart_count
        )

        model.settings_edit_enabled = (
            entity.settings_edit_enabled
        )

        model.rate_chart_edit_enabled = (
            entity.rate_chart_edit_enabled
        )

        model.master_enabled = (
            entity.master_enabled
        )

        return model