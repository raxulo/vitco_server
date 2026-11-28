"""
Support Handlers (Phase 25): teams, members and roles

Use cases for REQ-59, REQ-60, REQ-61, REQ-63 and REQ-64. Every use case opens one
transaction, resolves the acting user into a `SupportContext`, checks permission and
team scope, writes, and records an audit row in the same transaction.

Python 3.13+
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from app.core.database.manager import DatabaseManager
from app.middleware.authentication import CurrentUser
from app.modules.administration.application.command import CreateUserCommand
from app.modules.administration.application.handler import UserHandler
from app.modules.administration.domain.enums import Role
from app.modules.support.application.command import (
    CreateMemberCommand,
    CreateRoleCommand,
    CreateTeamCommand,
    ListMembersQuery,
    ListTeamsQuery,
    SetMemberActiveCommand,
    SetTeamActiveCommand,
    UpdateMemberCommand,
    UpdateRoleCommand,
    UpdateTeamCommand,
)
from app.modules.support.application.guard import SupportContext, SupportGuard
from app.modules.support.application.validation import (
    clean_code,
    clean_mobile,
    clean_name,
    clean_permissions,
)
from app.modules.support.domain.entities import (
    AuditEntry,
    SupportMember,
    SupportRole,
    SupportTeam,
)
from app.modules.support.domain.enums import AuditAction
from app.modules.support.domain.exceptions import (
    ManagerNotEditableException,
    MemberNotFoundException,
    RoleNameAlreadyExistsException,
    RoleNotFoundException,
    SupportPermissionDeniedException,
    SupportValidationException,
    TeamCodeAlreadyExistsException,
    TeamNotFoundException,
)
from app.modules.support.domain.irepository import ISupportRepository
from app.modules.support.domain.permissions import ROLE_TEMPLATES, SupportPermission

MAX_PAGE = 100


def _page(limit: int, offset: int) -> tuple[int, int]:
    return max(1, min(int(limit), MAX_PAGE)), max(0, int(offset))


class _SupportHandlerBase:

    __slots__ = ("_database", "_repository", "_guard")

    def __init__(self, *, database: DatabaseManager, repository: ISupportRepository) -> None:
        self._database = database
        self._repository = repository
        self._guard = SupportGuard(repository)

    async def context(self, actor: CurrentUser | None) -> SupportContext:
        """The acting user's context; callers run it inside a transaction."""
        async with self._database.transaction():
            return await self._guard.resolve(actor)

    async def _audit(
        self,
        ctx: SupportContext,
        action: AuditAction,
        entity: str,
        entity_id: UUID | str | None,
        team_id: UUID | None,
        **meta: Any,
    ) -> None:
        await self._repository.add_audit(
            AuditEntry(
                actor_id=ctx.user_id,
                action=str(action),
                entity=entity,
                entity_id=str(entity_id) if entity_id else None,
                team_id=team_id,
                meta=meta,
            )
        )


# =============================================================
# TEAMS
# =============================================================

class SupportTeamHandler(_SupportHandlerBase):

    __slots__ = ("_users",)

    def __init__(self, *, database: DatabaseManager, repository: ISupportRepository, users: UserHandler) -> None:
        super().__init__(database=database, repository=repository)
        self._users = users

    @staticmethod
    def _require_super_admin(ctx: SupportContext) -> None:
        if not ctx.is_super_admin:
            raise SupportPermissionDeniedException()

    async def create_team(self, command: CreateTeamCommand, actor: CurrentUser | None) -> SupportTeam:
        """Super Admin only: the team, its single Manager login and the five role templates."""
        name = clean_name(command.name, label="Team name", minimum=2)
        code = clean_code(command.code)
        manager_name = clean_name(command.manager_name, label="Manager name")
        manager_mobile = clean_mobile(command.manager_mobile)

        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            self._require_super_admin(ctx)
            if await self._repository.team_code_exists(code):
                raise TeamCodeAlreadyExistsException()

            manager = await self._users.create(
                CreateUserCommand(
                    name=manager_name,
                    email=command.manager_email,
                    mobile=manager_mobile,
                    role=Role.SUPPORT,
                    password_hash=command.manager_password,
                    created_by=ctx.user_id,
                )
            )

            team = SupportTeam(id=uuid4(), name=name, code=code, manager_user_id=manager.id)
            await self._repository.add_team(team, ctx.user_id)
            for role_name, permissions in ROLE_TEMPLATES.items():
                await self._repository.add_role(
                    SupportRole(
                        id=uuid4(), team_id=team.id, name=role_name,
                        permissions=permissions, is_system=True,
                    ),
                    ctx.user_id,
                )
            await self._repository.add_member(
                SupportMember(
                    id=uuid4(), user_id=manager.id, team_id=team.id, role_id=None, is_manager=True,
                ),
                ctx.user_id,
            )
            await self._audit(ctx, AuditAction.TEAM_CREATED, "team", team.id, team.id, name=name, code=code)
            created = await self._repository.get_team(team.id)
        return created or team

    async def update_team(self, command: UpdateTeamCommand, actor: CurrentUser | None) -> SupportTeam:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            self._require_super_admin(ctx)
            team = await self._repository.get_team(command.team_id)
            if team is None:
                raise TeamNotFoundException()
            name = clean_name(command.name, label="Team name", minimum=2) if command.name is not None else None
            code = clean_code(command.code) if command.code is not None else None
            if code and await self._repository.team_code_exists(code, exclude_team_id=team.id):
                raise TeamCodeAlreadyExistsException()
            await self._repository.update_team(
                team.id, name=name, code=code, is_active=None, actor_id=ctx.user_id,
            )
            await self._audit(ctx, AuditAction.TEAM_UPDATED, "team", team.id, team.id, name=name, code=code)
            updated = await self._repository.get_team(team.id)
        return updated or team

    async def set_active(self, command: SetTeamActiveCommand, actor: CurrentUser | None) -> SupportTeam:
        """Disable or enable a team; a disabled team and all its members lose portal access."""
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            self._require_super_admin(ctx)
            team = await self._repository.get_team(command.team_id)
            if team is None:
                raise TeamNotFoundException()
            await self._repository.update_team(
                team.id, name=None, code=None, is_active=command.is_active, actor_id=ctx.user_id,
            )
            action = AuditAction.TEAM_ACTIVATED if command.is_active else AuditAction.TEAM_DEACTIVATED
            await self._audit(ctx, action, "team", team.id, team.id)
            updated = await self._repository.get_team(team.id)
        return updated or team

    async def list_teams(self, query: ListTeamsQuery, actor: CurrentUser | None) -> tuple[list[SupportTeam], int]:
        limit, offset = _page(query.limit, query.offset)
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            self._require_super_admin(ctx)
            return await self._repository.list_teams(search=query.search, limit=limit, offset=offset)

    async def get_team(self, team_id: UUID, actor: CurrentUser | None) -> SupportTeam:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not ctx.can_access_team(team_id):
                raise TeamNotFoundException()
            team = await self._repository.get_team(team_id)
        if team is None:
            raise TeamNotFoundException()
        return team


# =============================================================
# MEMBERS
# =============================================================

class SupportMemberHandler(_SupportHandlerBase):

    __slots__ = ("_users",)

    def __init__(self, *, database: DatabaseManager, repository: ISupportRepository, users: UserHandler) -> None:
        super().__init__(database=database, repository=repository)
        self._users = users

    async def _member_in_scope(self, ctx: SupportContext, member_id: UUID) -> SupportMember:
        member = await self._repository.get_member(member_id)
        # Another team's member looks like one that does not exist
        if member is None or not ctx.can_access_team(member.team_id):
            raise MemberNotFoundException()
        return member

    async def _role_in_team(self, team_id: UUID, role_id: UUID) -> SupportRole:
        role = await self._repository.get_role(role_id)
        if role is None or role.team_id != team_id:
            raise RoleNotFoundException()
        return role

    async def create_member(self, command: CreateMemberCommand, actor: CurrentUser | None) -> SupportMember:
        name = clean_name(command.name)
        mobile = clean_mobile(command.mobile)

        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.MEMBER_MANAGE)
            team_id = ctx.team_scope(command.team_id)
            team = await self._repository.get_team(team_id)
            if team is None:
                raise TeamNotFoundException()
            role = await self._role_in_team(team_id, command.role_id)

            user = await self._users.create(
                CreateUserCommand(
                    name=name,
                    email=command.email,
                    mobile=mobile,
                    role=Role.SUPPORT,
                    password_hash=command.password,
                    created_by=ctx.user_id,
                )
            )
            member = SupportMember(id=uuid4(), user_id=user.id, team_id=team_id, role_id=role.id)
            await self._repository.add_member(member, ctx.user_id)
            await self._audit(
                ctx, AuditAction.MEMBER_CREATED, "member", member.id, team_id, name=name, role=role.name,
            )
            created = await self._repository.get_member(member.id)
        return created or member

    async def update_member(self, command: UpdateMemberCommand, actor: CurrentUser | None) -> SupportMember:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.MEMBER_MANAGE)
            member = await self._member_in_scope(ctx, command.member_id)

            name = clean_name(command.name) if command.name is not None else None
            mobile = None
            if command.mobile is not None:
                mobile = clean_mobile(command.mobile)
                if await self._repository.mobile_taken(mobile, exclude_user_id=member.user_id):
                    raise SupportValidationException(f"Mobile number {mobile} is already registered.")
            if name is not None or mobile is not None:
                await self._repository.update_member_user(
                    member.user_id, name=name, mobile=mobile, is_active=None,
                )
                await self._audit(
                    ctx, AuditAction.MEMBER_UPDATED, "member", member.id, member.team_id, name=name, mobile=bool(mobile),
                )

            if command.role_id is not None and command.role_id != member.role_id:
                if member.is_manager:
                    raise ManagerNotEditableException()
                if member.user_id == ctx.user_id:
                    raise SupportPermissionDeniedException("You cannot change your own role.")
                role = await self._role_in_team(member.team_id, command.role_id)
                await self._repository.update_member(
                    member.id, role_id=role.id, set_role=True, is_active=None, actor_id=ctx.user_id,
                )
                await self._audit(
                    ctx, AuditAction.MEMBER_ROLE_CHANGED, "member", member.id, member.team_id,
                    role=role.name, previous=member.role_name,
                )
            updated = await self._repository.get_member(member.id)
        return updated or member

    async def set_active(self, command: SetMemberActiveCommand, actor: CurrentUser | None) -> SupportMember:
        """Disable or enable a member; the login is switched off with it."""
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.MEMBER_MANAGE)
            member = await self._member_in_scope(ctx, command.member_id)
            if member.is_manager:
                raise ManagerNotEditableException("The manager is switched off by disabling the team.")
            if member.user_id == ctx.user_id:
                raise SupportValidationException("You cannot disable yourself.")
            await self._repository.update_member(
                member.id, role_id=None, set_role=False, is_active=command.is_active, actor_id=ctx.user_id,
            )
            await self._repository.update_member_user(
                member.user_id, name=None, mobile=None, is_active=command.is_active,
            )
            action = AuditAction.MEMBER_ACTIVATED if command.is_active else AuditAction.MEMBER_DEACTIVATED
            await self._audit(ctx, action, "member", member.id, member.team_id)
            updated = await self._repository.get_member(member.id)
        return updated or member

    async def list_members(
        self, query: ListMembersQuery, actor: CurrentUser | None,
    ) -> tuple[list[SupportMember], int]:
        limit, offset = _page(query.limit, query.offset)
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.MEMBER_MANAGE)
            team_id = ctx.team_scope(query.team_id)
            return await self._repository.list_members(team_id, search=query.search, limit=limit, offset=offset)

    async def get_member(self, member_id: UUID, actor: CurrentUser | None) -> SupportMember:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.MEMBER_MANAGE)
            return await self._member_in_scope(ctx, member_id)


# =============================================================
# ROLES
# =============================================================

class SupportRoleHandler(_SupportHandlerBase):

    __slots__ = ()

    async def list_roles(self, team_id: UUID | None, actor: CurrentUser | None) -> list[SupportRole]:
        """Roles of a team. Members managers can pick from; also needed by the member form."""
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            if not (ctx.has(SupportPermission.ROLE_MANAGE) or ctx.has(SupportPermission.MEMBER_MANAGE)):
                raise SupportPermissionDeniedException()
            return await self._repository.list_roles(ctx.team_scope(team_id))

    async def get_role(self, role_id: UUID, actor: CurrentUser | None) -> SupportRole:
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.ROLE_MANAGE)
            role = await self._repository.get_role(role_id)
            if role is None or not ctx.can_access_team(role.team_id):
                raise RoleNotFoundException()
            return role

    async def create_role(self, command: CreateRoleCommand, actor: CurrentUser | None) -> SupportRole:
        name = clean_name(command.name, label="Role name", minimum=2, maximum=80)
        permissions = clean_permissions(command.permissions)
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.ROLE_MANAGE)
            team_id = ctx.team_scope(command.team_id)
            if await self._repository.role_name_exists(team_id, name):
                raise RoleNameAlreadyExistsException()
            role = SupportRole(
                id=uuid4(), team_id=team_id, name=name,
                permissions=frozenset(SupportPermission(value) for value in permissions),
            )
            await self._repository.add_role(role, ctx.user_id)
            await self._audit(ctx, AuditAction.ROLE_CREATED, "role", role.id, team_id, name=name)
        return role

    async def update_role(self, command: UpdateRoleCommand, actor: CurrentUser | None) -> SupportRole:
        name = clean_name(command.name, label="Role name", minimum=2, maximum=80) if command.name is not None else None
        permissions = clean_permissions(command.permissions) if command.permissions is not None else None
        async with self._database.transaction():
            ctx = await self._guard.resolve(actor)
            ctx.require(SupportPermission.ROLE_MANAGE)
            role = await self._repository.get_role(command.role_id)
            if role is None or not ctx.can_access_team(role.team_id):
                raise RoleNotFoundException()
            if name is not None and await self._repository.role_name_exists(
                role.team_id, name, exclude_role_id=role.id,
            ):
                raise RoleNameAlreadyExistsException()
            await self._repository.update_role(
                role.id, name=name, permissions=permissions, actor_id=ctx.user_id,
            )
            await self._audit(
                ctx, AuditAction.ROLE_UPDATED, "role", role.id, role.team_id,
                name=name, permissions=permissions,
            )
            updated = await self._repository.get_role(role.id)
        return updated or role
