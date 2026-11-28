"""
Support Repository (Phase 25)

Async SQLAlchemy implementation of `ISupportRepository`. It never commits: the handlers
own the transaction. Names, mobiles and e-mails of staff come from `users` by join.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.infrastructure.models import UserModel
from app.modules.support.domain.entities import (
    AuditEntry,
    SupportMember,
    SupportRole,
    SupportTeam,
)
from app.modules.support.domain.irepository import ISupportRepository
from app.modules.support.domain.permissions import valid_permissions
from app.modules.support.infrastructure.models import (
    SupportAuditLogModel,
    SupportMemberModel,
    SupportRoleModel,
    SupportTeamModel,
)


def _like(text: str) -> str:
    """A safe `ILIKE` pattern for a user typed search."""
    escaped = text.strip().replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
    return f"%{escaped}%"


class SupportRepository(ISupportRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # TEAMS
    # =========================================================

    async def add_team(self, team: SupportTeam, actor_id: UUID | None) -> None:
        self._session.add(
            SupportTeamModel(
                id=team.id,
                name=team.name,
                code=team.code,
                manager_user_id=team.manager_user_id,
                is_active=team.is_active,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self._session.flush()

    def _team_query(self):
        members = (
            select(SupportMemberModel.team_id, func.count(SupportMemberModel.id).label("member_count"))
            .group_by(SupportMemberModel.team_id)
            .subquery()
        )
        return (
            select(
                SupportTeamModel,
                UserModel.name.label("manager_name"),
                UserModel.mobile.label("manager_mobile"),
                UserModel.email.label("manager_email"),
                func.coalesce(members.c.member_count, 0).label("member_count"),
            )
            .join(UserModel, UserModel.id == SupportTeamModel.manager_user_id)
            .outerjoin(members, members.c.team_id == SupportTeamModel.id)
        )

    @staticmethod
    def _to_team(row) -> SupportTeam:
        team: SupportTeamModel = row[0]
        return SupportTeam(
            id=team.id,
            name=team.name,
            code=team.code,
            manager_user_id=team.manager_user_id,
            is_active=team.is_active,
            created_at=team.created_at,
            manager_name=row.manager_name,
            manager_mobile=row.manager_mobile,
            manager_email=row.manager_email,
            member_count=int(row.member_count or 0),
        )

    async def get_team(self, team_id: UUID) -> SupportTeam | None:
        row = (await self._session.execute(self._team_query().where(SupportTeamModel.id == team_id))).first()
        return self._to_team(row) if row else None

    async def team_code_exists(self, code: str, exclude_team_id: UUID | None = None) -> bool:
        stmt = select(SupportTeamModel.id).where(func.lower(SupportTeamModel.code) == code.lower())
        if exclude_team_id is not None:
            stmt = stmt.where(SupportTeamModel.id != exclude_team_id)
        return (await self._session.scalar(stmt.limit(1))) is not None

    async def list_teams(
        self, *, search: str | None, limit: int, offset: int,
    ) -> tuple[list[SupportTeam], int]:
        stmt = self._team_query()
        count_stmt = select(func.count(SupportTeamModel.id)).join(
            UserModel, UserModel.id == SupportTeamModel.manager_user_id
        )
        if search and search.strip():
            pattern = _like(search)
            condition = or_(
                SupportTeamModel.name.ilike(pattern, escape="\\"),
                SupportTeamModel.code.ilike(pattern, escape="\\"),
                UserModel.name.ilike(pattern, escape="\\"),
            )
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        total = int(await self._session.scalar(count_stmt) or 0)
        rows = (
            await self._session.execute(
                stmt.order_by(SupportTeamModel.created_at.desc(), SupportTeamModel.id).limit(limit).offset(offset)
            )
        ).all()
        return [self._to_team(row) for row in rows], total

    async def update_team(
        self, team_id: UUID, *, name: str | None, code: str | None, is_active: bool | None, actor_id: UUID | None,
    ) -> None:
        values: dict = {"updated_by": actor_id, "updated_at": now_naive_ist()}
        if name is not None:
            values["name"] = name
        if code is not None:
            values["code"] = code
        if is_active is not None:
            values["is_active"] = is_active
        await self._session.execute(update(SupportTeamModel).where(SupportTeamModel.id == team_id).values(**values))

    # =========================================================
    # ROLES
    # =========================================================

    @staticmethod
    def _to_role(model: SupportRoleModel, member_count: int = 0) -> SupportRole:
        return SupportRole(
            id=model.id,
            team_id=model.team_id,
            name=model.name,
            permissions=valid_permissions(model.permissions or []),
            is_system=model.is_system,
            member_count=member_count,
        )

    async def add_role(self, role: SupportRole, actor_id: UUID | None) -> None:
        self._session.add(
            SupportRoleModel(
                id=role.id,
                team_id=role.team_id,
                name=role.name,
                permissions=sorted(str(value) for value in role.permissions),
                is_system=role.is_system,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self._session.flush()

    async def get_role(self, role_id: UUID) -> SupportRole | None:
        model = await self._session.get(SupportRoleModel, role_id)
        return self._to_role(model) if model else None

    async def role_name_exists(self, team_id: UUID, name: str, exclude_role_id: UUID | None = None) -> bool:
        stmt = select(SupportRoleModel.id).where(
            SupportRoleModel.team_id == team_id,
            func.lower(SupportRoleModel.name) == name.lower(),
        )
        if exclude_role_id is not None:
            stmt = stmt.where(SupportRoleModel.id != exclude_role_id)
        return (await self._session.scalar(stmt.limit(1))) is not None

    async def list_roles(self, team_id: UUID) -> list[SupportRole]:
        counts = dict(
            (
                await self._session.execute(
                    select(SupportMemberModel.role_id, func.count(SupportMemberModel.id))
                    .where(SupportMemberModel.team_id == team_id, SupportMemberModel.role_id.is_not(None))
                    .group_by(SupportMemberModel.role_id)
                )
            ).all()
        )
        models = (
            await self._session.scalars(
                select(SupportRoleModel)
                .where(SupportRoleModel.team_id == team_id)
                .order_by(SupportRoleModel.is_system.desc(), SupportRoleModel.name)
            )
        ).all()
        return [self._to_role(model, int(counts.get(model.id, 0))) for model in models]

    async def update_role(
        self, role_id: UUID, *, name: str | None, permissions: list[str] | None, actor_id: UUID | None,
    ) -> None:
        values: dict = {"updated_by": actor_id, "updated_at": now_naive_ist()}
        if name is not None:
            values["name"] = name
        if permissions is not None:
            values["permissions"] = permissions
        await self._session.execute(update(SupportRoleModel).where(SupportRoleModel.id == role_id).values(**values))

    # =========================================================
    # MEMBERS
    # =========================================================

    def _member_query(self):
        return (
            select(
                SupportMemberModel,
                UserModel.name,
                UserModel.email,
                UserModel.mobile,
                UserModel.last_login,
                UserModel.is_active.label("user_active"),
                SupportRoleModel.name.label("role_name"),
                SupportRoleModel.permissions.label("role_permissions"),
                SupportTeamModel.name.label("team_name"),
                SupportTeamModel.is_active.label("team_active"),
            )
            .join(UserModel, UserModel.id == SupportMemberModel.user_id)
            .join(SupportTeamModel, SupportTeamModel.id == SupportMemberModel.team_id)
            .outerjoin(SupportRoleModel, SupportRoleModel.id == SupportMemberModel.role_id)
        )

    @staticmethod
    def _to_member(row) -> SupportMember:
        model: SupportMemberModel = row[0]
        return SupportMember(
            id=model.id,
            user_id=model.user_id,
            team_id=model.team_id,
            role_id=model.role_id,
            is_manager=model.is_manager,
            is_active=bool(model.is_active and row.user_active),
            name=row.name,
            email=row.email,
            mobile=row.mobile,
            last_login=row.last_login,
            role_name="Manager" if model.is_manager else row.role_name,
            permissions=valid_permissions(row.role_permissions or []),
            team_name=row.team_name,
            team_is_active=bool(row.team_active),
        )

    async def add_member(self, member: SupportMember, actor_id: UUID | None) -> None:
        self._session.add(
            SupportMemberModel(
                id=member.id,
                user_id=member.user_id,
                team_id=member.team_id,
                role_id=member.role_id,
                is_manager=member.is_manager,
                is_active=member.is_active,
                created_by=actor_id,
                updated_by=actor_id,
            )
        )
        await self._session.flush()

    async def get_member(self, member_id: UUID) -> SupportMember | None:
        row = (await self._session.execute(self._member_query().where(SupportMemberModel.id == member_id))).first()
        return self._to_member(row) if row else None

    async def get_member_by_user(self, user_id: UUID) -> SupportMember | None:
        row = (await self._session.execute(self._member_query().where(SupportMemberModel.user_id == user_id))).first()
        return self._to_member(row) if row else None

    async def list_members(
        self, team_id: UUID, *, search: str | None, limit: int, offset: int,
    ) -> tuple[list[SupportMember], int]:
        stmt = self._member_query().where(SupportMemberModel.team_id == team_id)
        count_stmt = (
            select(func.count(SupportMemberModel.id))
            .join(UserModel, UserModel.id == SupportMemberModel.user_id)
            .where(SupportMemberModel.team_id == team_id)
        )
        if search and search.strip():
            pattern = _like(search)
            condition = or_(
                UserModel.name.ilike(pattern, escape="\\"),
                UserModel.mobile.ilike(pattern, escape="\\"),
                UserModel.email.ilike(pattern, escape="\\"),
            )
            stmt = stmt.where(condition)
            count_stmt = count_stmt.where(condition)
        total = int(await self._session.scalar(count_stmt) or 0)
        rows = (
            await self._session.execute(
                stmt.order_by(SupportMemberModel.is_manager.desc(), UserModel.name, SupportMemberModel.id)
                .limit(limit)
                .offset(offset)
            )
        ).all()
        return [self._to_member(row) for row in rows], total

    async def update_member(
        self,
        member_id: UUID,
        *,
        role_id: UUID | None,
        set_role: bool,
        is_active: bool | None,
        actor_id: UUID | None,
    ) -> None:
        values: dict = {"updated_by": actor_id, "updated_at": now_naive_ist()}
        if set_role:
            values["role_id"] = role_id
        if is_active is not None:
            values["is_active"] = is_active
        await self._session.execute(
            update(SupportMemberModel).where(SupportMemberModel.id == member_id).values(**values)
        )

    async def update_member_user(
        self, user_id: UUID, *, name: str | None, mobile: str | None, is_active: bool | None,
    ) -> None:
        values: dict = {"updated_at": now_naive_ist()}
        if name is not None:
            values["name"] = name
        if mobile is not None:
            values["mobile"] = mobile
        if is_active is not None:
            values["is_active"] = is_active
        await self._session.execute(update(UserModel).where(UserModel.id == user_id).values(**values))

    async def mobile_taken(self, mobile: str, exclude_user_id: UUID | None = None) -> bool:
        stmt = select(UserModel.id).where(UserModel.mobile == mobile)
        if exclude_user_id is not None:
            stmt = stmt.where(UserModel.id != exclude_user_id)
        return (await self._session.scalar(stmt.limit(1))) is not None

    # =========================================================
    # AUDIT
    # =========================================================

    async def audit_exists_since(self, *, actor_id: UUID, action: str, entity_id: str, since: datetime) -> bool:
        stmt = select(SupportAuditLogModel.id).where(
            SupportAuditLogModel.actor_id == actor_id,
            SupportAuditLogModel.action == action,
            SupportAuditLogModel.entity_id == entity_id,
            SupportAuditLogModel.created_at >= since,
        )
        return (await self._session.scalar(stmt.limit(1))) is not None

    async def add_audit(self, entry: AuditEntry) -> None:
        self._session.add(
            SupportAuditLogModel(
                actor_id=entry.actor_id,
                team_id=entry.team_id,
                action=entry.action,
                entity=entry.entity,
                entity_id=entry.entity_id,
                meta=entry.meta,
            )
        )
