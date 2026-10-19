from __future__ import annotations

from dataclasses import asdict

from app.modules.common.milk_quality.domain.entities import MilkQualityConfig
from app.modules.common.milk_quality.infrastructure.models import MilkQualityConfigModel


class MilkQualityConfigMapper:

    __slots__ = ()

    @staticmethod
    def to_model(
        entity: MilkQualityConfig,
    ) -> MilkQualityConfigModel:

        return MilkQualityConfigModel(**asdict(entity))

    @staticmethod
    def to_entity(
        model: MilkQualityConfigModel,
    ) -> MilkQualityConfig:

        return MilkQualityConfig(
            id=model.id,
            user_id=model.user_id,

            cow_min_fat=model.cow_min_fat,
            cow_max_fat=model.cow_max_fat,

            cow_min_snf=model.cow_min_snf,
            cow_max_snf=model.cow_max_snf,

            buffalo_min_fat=model.buffalo_min_fat,
            buffalo_max_fat=model.buffalo_max_fat,

            buffalo_min_snf=model.buffalo_min_snf,
            buffalo_max_snf=model.buffalo_max_snf,
        )