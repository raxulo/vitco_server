"""
Column Layout Handler (REQ-55, REQ-56, REQ-57, DECISION-030)

Read, change and reset a user's collection export column layout, used by the REST
API and the website. Every use case first checks that the caller may manage that
user's layout; the export worker reads layouts through `for_export`.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.command import (
    GetColumnLayoutQuery,
    ResetColumnLayoutCommand,
    UpdateColumnLayoutCommand,
)
from app.modules.dataexchange.domain.column_layout import COLLECTION_LAYOUT, ColumnLayout, LayoutUser
from app.modules.dataexchange.domain.exceptions import (
    ColumnLayoutForbiddenException,
    ColumnLayoutUserNotFoundException,
)
from app.modules.dataexchange.domain.irepository import IColumnLayoutRepository
from app.modules.dataexchange.domain.sheets import COLLECTION_COLUMNS, CollectionSheet, collection_column_sheets

_MANAGER_ROLES = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN})
_HEADERS = {column.key: column.header for column in COLLECTION_COLUMNS}


@dataclass(slots=True, kw_only=True)
class ColumnLayoutEntryDto:
    key: str
    header: str
    visible: bool
    sheets: list[str]                  # "mcc" / "vlcc": the exports that have this column


@dataclass(slots=True, kw_only=True)
class ColumnLayoutDto:
    user_id: UUID
    user_name: str
    user_role: int
    is_default: bool
    items: list[ColumnLayoutEntryDto]


class ColumnLayoutHandler:

    __slots__ = ("_database", "_repository")

    def __init__(self, *, database: DatabaseManager, repository: IColumnLayoutRepository) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # USE CASES
    # =========================================================

    async def get(self, query: GetColumnLayoutQuery) -> ColumnLayoutDto:
        async with self._database.transaction():
            target = await self._target(query.owner, query.user_id)
            stored = await self._repository.get(target.id, COLLECTION_LAYOUT)
        return _dto(target, ColumnLayout.normalise(stored))

    async def update(self, command: UpdateColumnLayoutCommand) -> ColumnLayoutDto:
        layout = ColumnLayout.from_request(command.columns)       # 422 before touching the database
        async with self._database.transaction():
            target = await self._target(command.owner, command.user_id)
            await self._repository.save(target.id, COLLECTION_LAYOUT, layout.to_json(), command.owner.id)
        return _dto(target, layout)

    async def reset(self, command: ResetColumnLayoutCommand) -> ColumnLayoutDto:
        async with self._database.transaction():
            target = await self._target(command.owner, command.user_id)
            await self._repository.delete(target.id, COLLECTION_LAYOUT)
        return _dto(target, ColumnLayout.default())

    async def can_manage(self, owner: CurrentUser, user_id: UUID) -> bool:
        """For pages that show an "Excel Column Order" link next to a user."""
        if owner.role_type not in _MANAGER_ROLES:
            return False
        async with self._database.transaction():
            return await self._repository.manageable_user(owner, user_id) is not None

    # ---------------------------------------------------------

    async def _target(self, owner: CurrentUser, user_id: UUID | None) -> LayoutUser:
        if owner.role_type not in _MANAGER_ROLES or owner.is_farmer_vlcc:
            raise ColumnLayoutForbiddenException()
        target = await self._repository.manageable_user(owner, user_id or owner.id)
        if target is None:
            raise ColumnLayoutUserNotFoundException()
        return target


async def layout_for_export(repository: IColumnLayoutRepository, owner: CurrentUser) -> ColumnLayout:
    """The layout an export by `owner` follows (call inside a transaction)."""
    layout_owner = await repository.layout_owner(owner)
    if layout_owner is None:
        return ColumnLayout.default()
    return ColumnLayout.normalise(await repository.get(layout_owner, COLLECTION_LAYOUT))


def _dto(target: LayoutUser, layout: ColumnLayout) -> ColumnLayoutDto:
    return ColumnLayoutDto(
        user_id=target.id,
        user_name=target.name,
        user_role=target.role,
        is_default=layout.is_default,
        items=[
            ColumnLayoutEntryDto(
                key=item.key,
                header=_HEADERS[item.key],
                visible=item.visible,
                sheets=[sheet.value for sheet in CollectionSheet if sheet in collection_column_sheets(item.key)],
            )
            for item in layout.items
        ],
    )


__all__ = [
    "ColumnLayoutDto",
    "ColumnLayoutEntryDto",
    "ColumnLayoutHandler",
    "layout_for_export",
]
