from sqlalchemy import func
from sqlalchemy import update

from uuid import UUID

from sqlalchemy import select

from app.core.database.manager import DatabaseManager

from app.modules.common.milk_quality.domain.entities import (
    MilkQualityConfig,
)

from app.modules.common.milk_quality.domain.repository import (
    IMilkQualityConfigRepository,
)

from app.modules.common.milk_quality.infrastructure.mapper import (
    MilkQualityConfigMapper,
)

from app.modules.common.milk_quality.infrastructure.models import (
    MilkQualityConfigModel,
)


class MilkQualityConfigRepository(
    IMilkQualityConfigRepository
):

    __slots__ = ("_database",)

    def __init__(
        self,
        database: DatabaseManager,
    ) -> None:

        self._database = database

    # =========================================================
    # CREATE
    # =========================================================

    async def create(self, config: MilkQualityConfig) -> None:

        model = MilkQualityConfigMapper.to_model(config)

        self._database.session.add(model)

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        config_id: UUID,
    ) -> MilkQualityConfig | None:

        stmt = (
            select(MilkQualityConfigModel)
            .where(
                MilkQualityConfigModel.id == config_id
            )
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return MilkQualityConfigMapper.to_entity(
            model
        )

    # =========================================================
    # GET BY USER
    # =========================================================

    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> MilkQualityConfig | None:

        stmt = (
            select(MilkQualityConfigModel)
            .where(
                MilkQualityConfigModel.user_id == user_id
            )
            .limit(1)
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return MilkQualityConfigMapper.to_entity(
            model
        )

    # =========================================================
    # EXISTS
    # =========================================================

    async def exists(
        self,
        config_id: UUID,
    ) -> bool:

        stmt = (
            select(MilkQualityConfigModel.id)
            .where(
                MilkQualityConfigModel.id == config_id
            )
            .limit(1)
        )

        return (
            await self._database.session.scalar(stmt)
        ) is not None

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        config: MilkQualityConfig,
    ) -> None:
        stmt = (
            update(MilkQualityConfigModel)
            .where(
                MilkQualityConfigModel.id == config.id
            )
            .values(
                cow_min_fat=config.cow_min_fat,
                cow_max_fat=config.cow_max_fat,
                cow_min_snf=config.cow_min_snf,
                cow_max_snf=config.cow_max_snf,
                buffalo_min_fat=config.buffalo_min_fat,
                buffalo_max_fat=config.buffalo_max_fat,
                buffalo_min_snf=config.buffalo_min_snf,
                buffalo_max_snf=config.buffalo_max_snf,
            )
        )

        await self._database.session.execute(stmt)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        config_id: UUID,
    ) -> None:

        model = await self._database.session.get(
            MilkQualityConfigModel,
            config_id,
        )

        if model is None:
            return

        await self._database.session.delete(
            model
        )