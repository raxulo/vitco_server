from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException
from app.middleware.authentication import CurrentUser

from app.core.database.manager import DatabaseManager
from app.modules.masters.units.domain.entities import UnitMaster
from app.modules.masters.units.domain.exceptions import (
    UnitNotFoundException,
    UnitAlreadyExistsException,
)
from app.modules.masters.units.infrastructure.repository import UnitMasterRepository
from app.modules.masters.units.domain.dto import UnitMasterDto, UnitMasterListDto
from app.modules.masters.units.application.command import (
    CreateUnitMasterCommand,
    UpdateUnitMasterCommand,
    DeleteUnitMasterCommand,
    GetUnitMasterQuery,
    ListUnitMasterQuery,
)


class UnitMasterHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: UnitMasterRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateUnitMasterCommand,
        owner: CurrentUser | None = None,
    ) -> UnitMasterDto:
        self._validate(command)

        await self._ensure_name_available(command.name, owner)

        unit = UnitMaster(
            id=uuid4(),
            name=command.name.strip(),
            is_active=True,
            created_by=command.created_by,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
            can_modify=True,
        )

        async with self._database.transaction():
            await self._repository.create(unit)

        return self._to_dto(unit)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateUnitMasterCommand,
    ) -> UnitMasterDto:
        self._validate(command)

        async with self._database.transaction():
            unit = await self._repository.get_by_id(command.id, command.owner)
            if unit is None:
                raise UnitNotFoundException()

            if unit.name.lower() != command.name.strip().lower():
                await self._ensure_name_available(command.name, command.owner)

            unit.name = command.name.strip()
            unit.is_active = command.is_active
            unit.updated_at = datetime.now(UTC)

            await self._repository.update(unit, command.owner)

        return self._to_dto(unit)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteUnitMasterCommand,
    ) -> None:
        async with self._database.transaction():
            unit = await self._repository.get_by_id(command.id, command.owner)
            if unit is None:
                raise UnitNotFoundException()

            await self._repository.delete(unit.id, command.owner)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetUnitMasterQuery,
    ) -> UnitMasterDto:
        unit = await self._repository.get_by_id(query.id, query.owner)
        if unit is None:
            raise UnitNotFoundException()

        return self._to_dto(unit)

    async def count(self, owner: CurrentUser | None = None) -> int:
        return await self._repository.count(owner)

    async def count_search(self, keyword: str, owner: CurrentUser | None = None) -> int:
        return await self._repository.count_search(keyword, owner)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListUnitMasterQuery,
    ) -> list[UnitMasterListDto]:
        if query.keyword:
            entities = await self._repository.search(
                keyword=query.keyword,
                offset=query.offset,
                limit=query.size,
                owner=query.owner,
            )
        else:
            entities = await self._repository.list(
                offset=query.offset,
                limit=query.size,
                owner=query.owner,
            )

        return [
            self._to_list_dto(entity)
            for entity in entities
        ]

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        unit: UnitMaster,
    ) -> UnitMasterListDto:
        return UnitMasterListDto(
            id=unit.id,
            name=unit.name,
            is_active=unit.is_active,
            owner_name=unit.owner_name,
            can_modify=unit.can_modify,
        )

    def _validate(
        self,
        command: CreateUnitMasterCommand | UpdateUnitMasterCommand,
    ) -> None:
        if not command.name.strip():
            raise ValidationException("Invalid Unit Name")

    async def _ensure_name_available(self, name: str, owner: CurrentUser | None = None) -> None:
        if await self._repository.exists_name(name, owner):
            raise UnitAlreadyExistsException()

    def _to_dto(self, unit: UnitMaster) -> UnitMasterDto:
        return UnitMasterDto(
            id=unit.id,
            name=unit.name,
            is_active=unit.is_active,
            owner_name=unit.owner_name,
            can_modify=unit.can_modify,
        )