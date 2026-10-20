from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException
from app.middleware.authentication import CurrentUser

from app.core.database.manager import DatabaseManager
from app.modules.masters.route.domain.entities import RouteMaster
from app.modules.masters.route.domain.exceptions import (
    RouteNotFoundException,
    RouteCodeAlreadyExistsException,
)
from app.core.exceptions.base import ForbiddenException
from app.modules.masters.route.infrastructure.repository import (
    RouteMasterAccessScope,
    RouteMasterRepository,
)
from app.modules.masters.route.domain.dto import RouteMasterDto, RouteMasterListDto
from app.core.clock import now_naive_ist
from app.modules.masters.route.application.command import (
    CreateRouteMasterCommand,
    UpdateRouteMasterCommand,
    DeleteRouteMasterCommand,
    GetRouteMasterQuery,
    ListRouteMasterQuery,
)


class RouteMasterHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: RouteMasterRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateRouteMasterCommand,
    ) -> RouteMasterDto:
        # Route codes are created only by Super Admin / Admin / Sub Admin
        if command.owner is None or command.owner.role_type not in RouteMasterAccessScope.CREATOR_ROLES:
            raise ForbiddenException("Only Super Admin, Admin or Sub Admin can create route codes")

        self._validate(command)

        await self._ensure_code_available(command.route_code)

        route = RouteMaster(
            id=uuid4(),
            route_code=command.route_code,
            route_name=command.route_name.strip(),
            is_active=True,
            created_by=command.created_by,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
        )

        async with self._database.transaction():
            await self._repository.create(route)

        return self._to_dto(route)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateRouteMasterCommand,
    ) -> RouteMasterDto:
        self._validate(command)

        async with self._database.transaction():
            route = await self._repository.get_by_id(command.id, command.owner)
            if route is None:
                raise RouteNotFoundException()

            if route.route_code != command.route_code:
                await self._ensure_code_available(command.route_code, command.owner)

            route.route_code = command.route_code
            route.route_name = command.route_name.strip()
            route.is_active = command.is_active
            route.updated_at = now_naive_ist()

            await self._repository.update(route, command.owner)

        return self._to_dto(route)

    # =========================================================
    # DELETE
    # =========================================================

    async def delete(
        self,
        command: DeleteRouteMasterCommand,
    ) -> None:
        async with self._database.transaction():
            route = await self._repository.get_by_id(command.id, command.owner)
            if route is None:
                raise RouteNotFoundException()

            await self._repository.delete(route.id, command.owner)

    # =========================================================
    # GET
    # =========================================================

    async def get(
        self,
        query: GetRouteMasterQuery,
    ) -> RouteMasterDto:
        route = await self._repository.get_by_id(query.id, query.owner)
        if route is None:
            raise RouteNotFoundException()

        return self._to_dto(route)

    async def count(self, owner: CurrentUser | None = None) -> int:
        return await self._repository.count(owner)

    async def count_search(self, keyword: str, owner: CurrentUser | None = None) -> int:
        return await self._repository.count_search(keyword, owner)

    # =========================================================
    # LIST
    # =========================================================

    async def list(
        self,
        query: ListRouteMasterQuery,
    ) -> list[RouteMasterListDto]:
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

    async def selectable(self, owner: CurrentUser) -> list[RouteMasterDto]:
        """Routes the logged-in user can assign to an MCC / VLCC (route master hierarchy)."""
        return await self._repository.get_selectable_routes(owner)

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        route: RouteMaster,
    ) -> RouteMasterListDto:
        return RouteMasterListDto(
            id=route.id,
            route_code=route.route_code,
            route_name=route.route_name,
            is_active=route.is_active,
            owner_name=route.owner_name,
            can_modify=route.can_modify,
        )

    def _validate(
        self,
        command: CreateRouteMasterCommand | UpdateRouteMasterCommand,
    ) -> None:
        if not command.route_name.strip():
            raise ValidationException("Invalid Route Name")
        if command.route_code <= 0:
            raise ValidationException("Route code must be a positive integer.")

    async def _ensure_code_available(self, code: int, owner: CurrentUser | None = None) -> None:
        if await self._repository.exists_code(code, owner):
            raise RouteCodeAlreadyExistsException()

    def _to_dto(self, route: RouteMaster) -> RouteMasterDto:
        return RouteMasterDto(
            id=route.id,
            route_code=route.route_code,
            route_name=route.route_name,
            is_active=route.is_active,
            owner_name=route.owner_name,
            can_modify=route.can_modify,
        )