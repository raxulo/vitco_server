"""
Support Guard (REQ-58, REQ-63)

Resolves the signed-in user into a `SupportContext` and answers every permission and
team-scope question on the server. Every support handler starts with `resolve` and then
`require(...)`; the screens only hide what the context says is not allowed.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.support.domain.entities import SupportMember
from app.modules.support.domain.exceptions import (
    SupportAccessDeniedException,
    SupportPermissionDeniedException,
    TeamNotFoundException,
)
from app.modules.support.domain.irepository import ISupportRepository
from app.modules.support.domain.permissions import (
    ALL_PERMISSIONS,
    SUPER_ADMIN_ONLY,
    SupportPermission,
    has_permission,
)


@dataclass(slots=True, frozen=True, kw_only=True)
class SupportContext:
    """Who is acting and what they may do. Super Admin has no team of its own."""

    user_id: UUID
    is_super_admin: bool = False
    member: SupportMember | None = None

    @property
    def is_manager(self) -> bool:
        return bool(self.member and self.member.is_manager)

    @property
    def team_id(self) -> UUID | None:
        return self.member.team_id if self.member else None

    @property
    def permissions(self) -> frozenset[SupportPermission]:
        """The effective permission set (used by sidebars and templates)."""
        if self.is_super_admin:
            return ALL_PERMISSIONS
        if self.member is None:
            return frozenset()
        if self.member.is_manager:
            return ALL_PERMISSIONS - SUPER_ADMIN_ONLY
        return self.member.permissions

    def has(self, permission: SupportPermission) -> bool:
        if self.member is None and not self.is_super_admin:
            return False
        return has_permission(
            self.member.permissions if self.member else frozenset(),
            permission,
            is_manager=self.is_manager,
            is_super_admin=self.is_super_admin,
        )

    def require(self, permission: SupportPermission) -> None:
        if not self.has(permission):
            raise SupportPermissionDeniedException()

    def team_scope(self, requested_team_id: UUID | None) -> UUID:
        """The team an action applies to: always the member's own; Super Admin names one."""
        if self.is_super_admin:
            if requested_team_id is None:
                raise TeamNotFoundException()
            return requested_team_id
        if self.team_id is None:
            raise SupportAccessDeniedException()
        # A request for another team looks like a team that does not exist
        if requested_team_id is not None and requested_team_id != self.team_id:
            raise TeamNotFoundException()
        return self.team_id

    def can_access_team(self, team_id: UUID) -> bool:
        return self.is_super_admin or self.team_id == team_id


class SupportGuard:

    __slots__ = ("_repository",)

    def __init__(self, repository: ISupportRepository) -> None:
        self._repository = repository

    async def resolve(self, user: CurrentUser | None) -> SupportContext:
        """Super Admin, or an active member of an active team; everyone else is refused."""
        if user is None:
            raise SupportAccessDeniedException()
        role = user.role_type
        if role == Role.SUPER_ADMIN:
            return SupportContext(user_id=user.id, is_super_admin=True)
        if role != Role.SUPPORT:
            raise SupportAccessDeniedException()
        member = await self._repository.get_member_by_user(user.id)
        if member is None or not member.is_active or not member.team_is_active:
            raise SupportAccessDeniedException()
        return SupportContext(user_id=user.id, member=member)
