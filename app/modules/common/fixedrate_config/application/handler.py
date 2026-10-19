from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from app.core.database.manager import DatabaseManager

from app.modules.common.fixedrate_config.domain.entities import (
    FixedRateConfig,
)

from app.modules.common.fixedrate_config.domain.exceptions import (
    FixedRateConfigNotFoundException,
    FixedRateConfigAlreadyExistsException,
    InvalidFixedRateConfigException,
)

from app.modules.common.fixedrate_config.domain.repository import (
    IFixedRateConfigRepository,
)

from app.modules.common.fixedrate_config.application.command import (
    CreateFixedRateConfigCommand,
    UpdateFixedRateConfigCommand,
    GetFixedRateConfigQuery,
    GetFixedRateConfigByUserQuery,
    DeleteFixedRateConfigCommand,
)

from app.modules.common.fixedrate_config.application.dto import (
    FixedRateConfigDto,
)


class FixedRateConfigHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self,
        database: DatabaseManager,
        repository: IFixedRateConfigRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateFixedRateConfigCommand,
    ) -> FixedRateConfigDto:

        self._validate(command)

        existing = await self._repository.get_by_user_id(
            command.user_id
        )

        if existing is not None:
            raise FixedRateConfigAlreadyExistsException()

        config = FixedRateConfig(
            id=uuid4(),
            user_id=command.user_id,
            fixed_rate=command.fixed_rate,
            less_detection=command.less_detection,
            high_detection=command.high_detection,
            min_fat=command.min_fat,
            max_fat=command.max_fat,
            min_snf=command.min_snf,
            max_snf=command.max_snf,
        )

        async with self._database.transaction():
            await self._repository.create(config)

        return self._to_dto(config)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateFixedRateConfigCommand,
    ) -> FixedRateConfigDto:

        self._validate(command)

        async with self._database.transaction():
            config = await self._repository.get_by_id(
                command.id
            )

            if config is None:
                raise FixedRateConfigNotFoundException()

            if config.user_id != command.user_id:
                raise InvalidFixedRateConfigException(
                    "Configuration does not belong to this user."
                )

            config.fixed_rate = command.fixed_rate
            config.less_detection = command.less_detection
            config.high_detection = command.high_detection
            config.min_fat = command.min_fat
            config.max_fat = command.max_fat
            config.min_snf = command.min_snf
            config.max_snf = command.max_snf

            await self._repository.update(config)

        return self._to_dto(config)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetFixedRateConfigQuery,
    ) -> FixedRateConfigDto:

        config = await self._repository.get_by_id(
            query.id
        )

        if config is None:
            raise FixedRateConfigNotFoundException()

        return self._to_dto(config)

    # =========================================================
    # GET BY USER
    # =========================================================

    async def get_by_user(
        self,
        query: GetFixedRateConfigByUserQuery,
    ) -> FixedRateConfigDto:

        config = await self._repository.get_by_user_id(
            query.user_id
        )

        if config is None:
            raise FixedRateConfigNotFoundException()

        return self._to_dto(config)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteFixedRateConfigCommand,
    ) -> None:

        async with self._database.transaction():
            config = await self._repository.get_by_id(
                command.id
            )

            if config is None:
                raise FixedRateConfigNotFoundException()

            await self._repository.delete(
                config.id
            )

    # =========================================================
    # VALIDATION
    # =========================================================

    @staticmethod
    def _validate(
        command: CreateFixedRateConfigCommand | UpdateFixedRateConfigCommand,
    ) -> None:

        if command.fixed_rate < 0:
            raise InvalidFixedRateConfigException(
                "Fixed rate cannot be negative."
            )

        if command.less_detection < 0 or command.high_detection < 0:
            raise InvalidFixedRateConfigException(
                "Detection deductions cannot be negative."
            )

        if command.min_fat > command.max_fat:
            raise InvalidFixedRateConfigException(
                "Minimum FAT cannot exceed maximum FAT."
            )

        if command.min_snf > command.max_snf:
            raise InvalidFixedRateConfigException(
                "Minimum SNF cannot exceed maximum SNF."
            )

    # =========================================================
    # DTO
    # =========================================================

    @staticmethod
    def _to_dto(config: FixedRateConfig) -> FixedRateConfigDto:

        return FixedRateConfigDto(
            id=config.id,
            user_id=config.user_id,
            fixed_rate=config.fixed_rate,
            less_detection=config.less_detection,
            high_detection=config.high_detection,
            min_fat=config.min_fat,
            max_fat=config.max_fat,
            min_snf=config.min_snf,
            max_snf=config.max_snf,
        )