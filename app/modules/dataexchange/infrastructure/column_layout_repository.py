"""
Column Layout Repository (REQ-55, REQ-56, REQ-57, DECISION-030)

Stores each user's export column layout and answers the two access questions:

- `layout_owner`: whose layout an export follows.

      Super Admin / Admin / Sub Admin -> its own
      MCC                             -> whoever created its MCC
      VLCC                            -> whoever created its VLCC; when that is an MCC user,
                                         whoever created that MCC
      anyone else, or a deleted owner -> None (the default layout)

- `manageable_user`: whose layout an actor may read and change.

      everyone (manager roles)  -> itself
      Super Admin               -> any Admin / Sub Admin
      Admin                     -> the Sub Admins it created

Python 3.13+
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.dataexchange.domain.column_layout import LayoutUser
from app.modules.dataexchange.domain.irepository import IColumnLayoutRepository
from app.modules.dataexchange.infrastructure.models import ExcelColumnLayoutModel
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.vlcc.infrastructure.models import VlccModel

MANAGER_ROLES = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN})


class ColumnLayoutRepository(IColumnLayoutRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # LAYOUT ROWS
    # =========================================================

    async def get(self, user_id: UUID, sheet: str) -> list[dict[str, Any]] | None:
        return await self._session.scalar(
            select(ExcelColumnLayoutModel.columns).where(
                ExcelColumnLayoutModel.user_id == user_id,
                ExcelColumnLayoutModel.sheet == sheet,
            )
        )

    async def save(self, user_id: UUID, sheet: str, columns: list[dict[str, Any]], actor_id: UUID) -> None:
        model = await self._session.scalar(
            select(ExcelColumnLayoutModel).where(
                ExcelColumnLayoutModel.user_id == user_id,
                ExcelColumnLayoutModel.sheet == sheet,
            )
        )
        if model is None:
            self._session.add(ExcelColumnLayoutModel(
                user_id=user_id, sheet=sheet, columns=columns, created_by=actor_id, updated_by=actor_id,
            ))
        else:
            model.columns = columns                    # a new list, so the JSON column is marked changed
            model.updated_by = actor_id
            model.updated_at = now_naive_ist()
        await self._session.flush()

    async def delete(self, user_id: UUID, sheet: str) -> None:
        await self._session.execute(
            delete(ExcelColumnLayoutModel).where(
                ExcelColumnLayoutModel.user_id == user_id,
                ExcelColumnLayoutModel.sheet == sheet,
            )
        )

    # =========================================================
    # ACCESS
    # =========================================================

    async def layout_owner(self, user: CurrentUser) -> UUID | None:
        role = user.role_type
        if role in MANAGER_ROLES:
            owner_id: UUID | None = user.id
        elif role == Role.MCC:
            owner_id = await self._first(select(MccModel.created_by).where(MccModel.user_id == user.id))
        elif role in (Role.VLCC, Role.VLCC_FARMER):
            owner_id = await self._first(select(VlccModel.created_by).where(VlccModel.user_id == user.id))
            if owner_id is not None:
                # A VLCC made by an MCC user follows that MCC's creator
                made_by_mcc = await self._first(select(MccModel.created_by).where(MccModel.user_id == owner_id))
                if made_by_mcc is not None:
                    owner_id = made_by_mcc
        else:
            return None
        if owner_id is None:
            return None
        alive = await self._session.scalar(
            select(UserModel.id).where(UserModel.id == owner_id, UserModel.is_deleted.is_(False))
        )
        return alive

    async def manageable_user(self, actor: CurrentUser, user_id: UUID) -> LayoutUser | None:
        role = actor.role_type
        conditions = [UserModel.id == user_id, UserModel.is_deleted.is_(False)]
        if user_id == actor.id:
            pass
        elif role == Role.SUPER_ADMIN:
            conditions.append(UserModel.role.in_([Role.ADMIN, Role.SUB_ADMIN]))
        elif role == Role.ADMIN:
            conditions.extend([UserModel.created_by == actor.id, UserModel.role == Role.SUB_ADMIN])
        else:
            return None
        row = (await self._session.execute(
            select(UserModel.id, UserModel.name, UserModel.role).where(*conditions).limit(1)
        )).first()
        if row is None:
            return None
        return LayoutUser(id=row.id, name=row.name or "", role=int(row.role))

    async def _first(self, stmt) -> UUID | None:
        return (await self._session.execute(stmt.limit(1))).scalar()


__all__ = ["ColumnLayoutRepository", "MANAGER_ROLES"]
