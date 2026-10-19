from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException
from app.middleware.authentication import CurrentUser

from app.core.database.manager import DatabaseManager
from app.modules.masters.items.domain.entities import ItemMaster
from app.modules.masters.items.domain.exceptions import (
    ItemNotFoundException,
    ItemCodeAlreadyExistsException,
)
from app.modules.masters.items.infrastructure.repository import ItemMasterRepository
from app.modules.masters.items.domain.dto import ItemMasterDto, ItemMasterListDto
from app.modules.masters.items.application.command import (
    CreateItemMasterCommand,
    UpdateItemMasterCommand,
    DeleteItemMasterCommand,
    GetItemMasterQuery,
    ListItemMasterQuery,
)


class ItemMasterHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: ItemMasterRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateItemMasterCommand,
        owner: CurrentUser | None = None
    ) -> ItemMasterDto:
        self._validate(command)

        if await self._repository.exists_item(command.item_name,command.item_code,owner):
            raise ItemCodeAlreadyExistsException()

        item = ItemMaster(
            id=uuid4(),
            item_code=command.item_code,
            item_name=command.item_name.strip(),
            unit_id=command.unit_id,
            rate=command.rate,
            is_active=True,
            created_by=command.created_by,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )

        async with self._database.transaction():
            await self._repository.create(item)

        return self._to_dto(item)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateItemMasterCommand,
    ) -> ItemMasterDto:
        self._validate(command)

        async with self._database.transaction():
            item = await self._repository.get_by_id(command.id, command.owner)
            if item is None:
                raise ItemNotFoundException()

            if item.item_code != command.item_code:
                await self._ensure_code_available(command.item_code)

            item.item_code = command.item_code
            item.item_name = command.item_name.strip()
            item.unit_id = command.unit_id
            item.rate = command.rate
            item.is_active = command.is_active
            item.updated_at = datetime.now(UTC)

            await self._repository.update(item, command.owner)

        return self._to_dto(item)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteItemMasterCommand,
    ) -> None:
        async with self._database.transaction():
            item = await self._repository.get_by_id(command.id, command.owner)
            if item is None:
                raise ItemNotFoundException()

            await self._repository.delete(item.id, command.owner)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetItemMasterQuery,
    ) -> ItemMasterDto:
        item = await self._repository.get_by_id(query.id, query.owner)
        if item is None:
            raise ItemNotFoundException()

        return self._to_dto(item)

    async def count(self, owner: CurrentUser | None = None) -> int:
        return await self._repository.count(owner)

    async def count_search(self, keyword: str, owner: CurrentUser | None = None) -> int:
        return await self._repository.count_search(keyword, owner)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListItemMasterQuery,
    ) -> list[ItemMasterListDto]:
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
        item: ItemMaster,
    ) -> ItemMasterListDto:
        return ItemMasterListDto(
            id=item.id,
            item_code=item.item_code,
            item_name=item.item_name,
            unit_id=item.unit_id,
            rate=item.rate,
            is_active=item.is_active,
            owner_name=item.owner_name,
            can_modify=item.can_modify,
        )

    def _validate(
        self,
        command: CreateItemMasterCommand | UpdateItemMasterCommand,
    ) -> None:
        if not command.item_name.strip():
            raise ValidationException("Invalid Item Name")
        if command.item_code <= 0:
            raise ValidationException("Item code must be a positive integer.")
        if command.rate < 0:
            raise ValidationException("Rate cannot be negative.")

    async def _ensure_code_available(self, code: int) -> None:
        if await self._repository.exists_code(code):
            raise ItemCodeAlreadyExistsException()

    def _to_dto(self, item: ItemMaster) -> ItemMasterDto:
        return ItemMasterDto(
            id=item.id,
            item_code=item.item_code,
            item_name=item.item_name,
            unit_id=item.unit_id,
            rate=item.rate,
            is_active=item.is_active,
            owner_name=item.owner_name,
            can_modify=item.can_modify,
        )