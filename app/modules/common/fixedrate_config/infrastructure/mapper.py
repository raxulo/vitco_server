from __future__ import annotations

from app.modules.common.fixedrate_config.domain.entities import (
    FixedRateConfig,
)

from app.modules.common.fixedrate_config.infrastructure.models import (
    FixedRateConfigModel,
)


class FixedRateConfigMapper:

    __slots__ = ()

    @staticmethod
    def to_model(
        entity: FixedRateConfig,
    ) -> FixedRateConfigModel:

        return FixedRateConfigModel(
            id=entity.id,
            user_id=entity.user_id,

            fixed_rate=entity.fixed_rate,

            less_detection=entity.less_detection,
            high_detection=entity.high_detection,

            min_fat=entity.min_fat,
            max_fat=entity.max_fat,

            min_snf=entity.min_snf,
            max_snf=entity.max_snf,
        )

    @staticmethod
    def to_entity(
        model: FixedRateConfigModel,
    ) -> FixedRateConfig:

        return FixedRateConfig(
            id=model.id,
            user_id=model.user_id,

            fixed_rate=model.fixed_rate,

            less_detection=model.less_detection,
            high_detection=model.high_detection,

            min_fat=model.min_fat,
            max_fat=model.max_fat,

            min_snf=model.min_snf,
            max_snf=model.max_snf,
        )