from __future__ import annotations

from uuid import uuid4

from app.core.database.manager import DatabaseManager

from app.modules.common.milk_quality.domain.entities import (
    MilkQualityConfig,
)

from app.modules.common.milk_quality.domain.exceptions import (
    MilkQualityConfigAlreadyExistsException,
    MilkQualityConfigNotFoundException,
    InvalidMilkQualityConfigException,
)

from app.modules.common.milk_quality.infrastructure.repository import (
    MilkQualityConfigRepository,
)

from app.modules.common.milk_quality.application.command import (
    CreateMilkQualityConfigCommand,
    UpdateMilkQualityConfigCommand,
    GetMilkQualityConfigQuery,
    GetMilkQualityConfigByUserQuery,
    DeleteMilkQualityConfigCommand,
)

from app.modules.common.milk_quality.application.dto import (
    MilkQualityConfigDto,
)


class MilkQualityConfigHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self,
        database: DatabaseManager,
        repository: MilkQualityConfigRepository,
    ) -> None:

        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateMilkQualityConfigCommand,
    ) -> MilkQualityConfigDto:

        self._validate(command)

        existing = await self._repository.get_by_user_id(
            command.user_id
        )

        if existing is not None:
            raise MilkQualityConfigAlreadyExistsException()

        config = MilkQualityConfig(
            id=uuid4(),
            user_id=command.user_id,

            cow_min_fat=command.cow_min_fat,
            cow_max_fat=command.cow_max_fat,

            cow_min_snf=command.cow_min_snf,
            cow_max_snf=command.cow_max_snf,

            buffalo_min_fat=command.buffalo_min_fat,
            buffalo_max_fat=command.buffalo_max_fat,

            buffalo_min_snf=command.buffalo_min_snf,
            buffalo_max_snf=command.buffalo_max_snf,
        )

        async with self._database.transaction():

            await self._repository.create(config)

        return self._to_dto(config)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self, command: UpdateMilkQualityConfigCommand,
    ) -> MilkQualityConfigDto:

        self._validate(command)

        async with self._database.transaction():

            config = await self._repository.get_by_id(command.id)

            if config is None:
                raise MilkQualityConfigNotFoundException()

            # Ownership protection
            if config.user_id != command.user_id:
                raise InvalidMilkQualityConfigException("Configuration does not belong to this user.")

            config.cow_min_fat = command.cow_min_fat
            config.cow_max_fat = command.cow_max_fat

            config.cow_min_snf = command.cow_min_snf
            config.cow_max_snf = command.cow_max_snf
            config.buffalo_min_fat = command.buffalo_min_fat
            config.buffalo_max_fat = command.buffalo_max_fat
            config.buffalo_min_snf = command.buffalo_min_snf
            config.buffalo_max_snf = command.buffalo_max_snf

            await self._repository.update(config)

        return self._to_dto(config)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetMilkQualityConfigQuery,
    ) -> MilkQualityConfigDto:

        config = await self._repository.get_by_id(query.id)

        if config is None:
            raise MilkQualityConfigNotFoundException()

        return self._to_dto(config)

    # =========================================================
    # GET BY USER
    # =========================================================

    async def get_by_user(
        self,
        query: GetMilkQualityConfigByUserQuery,
    ) -> MilkQualityConfigDto:

        config = await self._repository.get_by_user_id(
            query.user_id
        )

        if config is None:
            raise MilkQualityConfigNotFoundException()

        return self._to_dto(config)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteMilkQualityConfigCommand,
    ) -> None:

        async with self._database.transaction():

            config = await self._repository.get_by_id(
                command.id
            )

            if config is None:
                raise MilkQualityConfigNotFoundException()

            await self._repository.delete(
                config.id
            )

    # =========================================================
    # VALIDATION
    # =========================================================

    @staticmethod
    def _validate(
        command: CreateMilkQualityConfigCommand,
    ) -> None:

        if command.cow_min_fat > command.cow_max_fat:
            raise InvalidMilkQualityConfigException(
                "Cow minimum FAT cannot exceed maximum FAT."
            )

        if command.cow_min_snf > command.cow_max_snf:
            raise InvalidMilkQualityConfigException(
                "Cow minimum SNF cannot exceed maximum SNF."
            )

        if command.buffalo_min_fat > command.buffalo_max_fat:
            raise InvalidMilkQualityConfigException(
                "Buffalo minimum FAT cannot exceed maximum FAT."
            )

        if command.buffalo_min_snf > command.buffalo_max_snf:
            raise InvalidMilkQualityConfigException(
                "Buffalo minimum SNF cannot exceed maximum SNF."
            )

    # =========================================================
    # DTO
    # =========================================================

    @staticmethod
    def _to_dto(config: MilkQualityConfig) -> MilkQualityConfigDto:

        return MilkQualityConfigDto(
            id=config.id,
            user_id=config.user_id,

            cow_min_fat=config.cow_min_fat,
            cow_max_fat=config.cow_max_fat,

            cow_min_snf=config.cow_min_snf,
            cow_max_snf=config.cow_max_snf,

            buffalo_min_fat=config.buffalo_min_fat,
            buffalo_max_fat=config.buffalo_max_fat,

            buffalo_min_snf=config.buffalo_min_snf,
            buffalo_max_snf=config.buffalo_max_snf,
        )