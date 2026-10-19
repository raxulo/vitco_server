from operator import or_
from uuid import UUID

from sqlalchemy import select

from app.core.database.manager import DatabaseManager

from app.modules.common.fixedrate_config.domain.entities import (
    FixedRateConfig,
)

from app.modules.common.fixedrate_config.domain.repository import (
    IFixedRateConfigRepository,
)

from app.modules.common.fixedrate_config.infrastructure.mapper import (
    FixedRateConfigMapper,
)

from app.modules.common.fixedrate_config.infrastructure.models import (
    FixedRateConfigModel,
)


class FixedRateConfigRepository(
    IFixedRateConfigRepository
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

    async def create(
        self,
        config: FixedRateConfig,
    ) -> None:

        model = FixedRateConfigMapper.to_model(
            config
        )

        self._database.session.add(model)

    # =========================================================
    # GET BY ID
    # =========================================================

    async def get_by_id(
        self,
        config_id: UUID,
    ) -> FixedRateConfig | None:

        stmt = (
            select(FixedRateConfigModel)
            .where(
                FixedRateConfigModel.id == config_id,
            )
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return FixedRateConfigMapper.to_entity(
            model
        )

    # =========================================================
    # GET BY USER
    # =========================================================

    async def get_by_user_id(
        self,
        user_id: UUID,
    ) -> FixedRateConfig | None:

        stmt = (
            select(FixedRateConfigModel)
            .where(
                FixedRateConfigModel.user_id == user_id,
            )
            .limit(1)
        )

        model = await self._database.session.scalar(
            stmt
        )

        if model is None:
            return None

        return FixedRateConfigMapper.to_entity(
            model
        )

    # =========================================================
    # EXISTS
    # =========================================================

    async def exists(
        self,
        config_id: UUID,
        user_id: UUID | None = None,
    ) -> bool:

        stmt = (
            select(FixedRateConfigModel.id)
            .where(
                or_(
                    FixedRateConfigModel.id == config_id,
                    user_id is not None and FixedRateConfigModel.user_id == user_id,
                )
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
        config: FixedRateConfig,
    ) -> None:

        model = await self._database.session.get(
            FixedRateConfigModel,
            config.id,
        )

        if model is None:
            return

        model.fixed_rate = config.fixed_rate

        model.less_detection = (
            config.less_detection
        )

        model.high_detection = (
            config.high_detection
        )

        model.min_fat = config.min_fat
        model.max_fat = config.max_fat

        model.min_snf = config.min_snf
        model.max_snf = config.max_snf

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        config_id: UUID,
    ) -> None:

        model = await self._database.session.get(
            FixedRateConfigModel,
            config_id,
        )

        if model is None:
            return

        await self._database.session.delete(
            model
        )