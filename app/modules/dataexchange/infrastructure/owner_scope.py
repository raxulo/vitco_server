"""
Owner Scope for VLCC Exchange

Which owner a user may export / import VLCCs for (REQ-12, DECISION-004):

    Super Admin -> any Admin, Sub Admin, or Self (Super Admin)
    Admin       -> its Sub Admins; blank / default = itself
    Sub Admin   -> itself, locked
    MCC         -> itself, locked
    VLCC / Farmer -> not allowed (403)

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.dataexchange.domain.exceptions import (
    ExcelExchangeForbiddenException,
    ExcelTargetNotFoundException,
    ExcelTargetRequiredException,
)

_ELIGIBLE_ROLES = (Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.MCC)


@dataclass(slots=True, frozen=True)
class OwnerOption:
    id: UUID
    name: str
    role: str


@dataclass(slots=True, frozen=True)
class OwnerOptions:
    items: list[OwnerOption]
    total: int
    locked: bool
    default_id: UUID | None


class OwnerScope:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    def _ensure_role(self, owner: CurrentUser) -> None:
        if owner.role_type not in _ELIGIBLE_ROLES:
            raise ExcelExchangeForbiddenException("Only administrators and MCCs can exchange VLCCs")

    async def options(self, owner: CurrentUser, *, search: str | None, limit: int, offset: int) -> OwnerOptions:
        self._ensure_role(owner)
        role = owner.role_type

        if role in (Role.SUB_ADMIN, Role.MCC):
            # Locked to self
            self_user = await self._session.scalar(select(UserModel).where(UserModel.id == owner.id))
            name = self_user.name if self_user else str(owner.id)
            item = OwnerOption(id=owner.id, name=name, role=role.name)
            return OwnerOptions(items=[item], total=1, locked=True, default_id=owner.id)

        conditions = [UserModel.is_deleted.is_(False)]
        if role == Role.SUPER_ADMIN:
            conditions.append(UserModel.role.in_([Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN]))
        elif role == Role.ADMIN:
            conditions.append(
                or_(
                    UserModel.id == owner.id,
                    (UserModel.created_by == owner.id) & (UserModel.role == Role.SUB_ADMIN),
                )
            )

        keyword = (search or "").strip()
        if keyword:
            pattern = f"%{keyword}%"
            conditions.append(UserModel.name.ilike(pattern))

        total = int(await self._session.scalar(select(func.count(UserModel.id)).where(*conditions)) or 0)
        rows = (await self._session.execute(
            select(UserModel.id, UserModel.name, UserModel.role)
            .where(*conditions)
            .order_by(UserModel.name, UserModel.id)
            .offset(offset)
            .limit(limit)
        )).all()
        items = [OwnerOption(id=row.id, name=row.name, role=Role(row.role).name) for row in rows]

        locked = False
        default_id = owner.id if role == Role.ADMIN else (items[0].id if total == 1 and items else None)
        return OwnerOptions(items=items, total=total, locked=locked, default_id=default_id)

    async def resolve(self, owner: CurrentUser, requested: UUID | None) -> OwnerOption:
        self._ensure_role(owner)
        role = owner.role_type

        # Sub Admin and MCC are strictly locked to self
        if role in (Role.SUB_ADMIN, Role.MCC):
            self_user = await self._session.scalar(select(UserModel).where(UserModel.id == owner.id))
            name = self_user.name if self_user else str(owner.id)
            return OwnerOption(id=owner.id, name=name, role=role.name)

        # Admin defaults to self if requested is None
        if role == Role.ADMIN and requested is None:
            self_user = await self._session.scalar(select(UserModel).where(UserModel.id == owner.id))
            name = self_user.name if self_user else str(owner.id)
            return OwnerOption(id=owner.id, name=name, role=role.name)

        if requested is None:
            raise ExcelTargetRequiredException("Owner ID is required for VLCC exchange")

        conditions = [UserModel.id == requested, UserModel.is_deleted.is_(False)]
        if role == Role.SUPER_ADMIN:
            conditions.append(UserModel.role.in_([Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN]))
        elif role == Role.ADMIN:
            conditions.append(
                or_(
                    UserModel.id == owner.id,
                    (UserModel.created_by == owner.id) & (UserModel.role == Role.SUB_ADMIN),
                )
            )

        row = (await self._session.execute(
            select(UserModel.id, UserModel.name, UserModel.role).where(*conditions).limit(1)
        )).first()
        if row is None:
            raise ExcelTargetNotFoundException("Selected owner was not found or is outside your hierarchy")
        return OwnerOption(id=row.id, name=row.name, role=Role(row.role).name)
