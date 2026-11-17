"""
Support Repository Interface

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.support.domain.entities import (
    AuditEntry,
    SupportMember,
    SupportRole,
    SupportTeam,
)


class ISupportRepository(ABC):

    # ---------------------------------------------------- teams

    @abstractmethod
    async def add_team(self, team: SupportTeam, actor_id: UUID | None) -> None: ...

    @abstractmethod
    async def get_team(self, team_id: UUID) -> SupportTeam | None: ...

    @abstractmethod
    async def team_code_exists(self, code: str, exclude_team_id: UUID | None = None) -> bool: ...

    @abstractmethod
    async def list_teams(
        self, *, search: str | None, limit: int, offset: int,
    ) -> tuple[list[SupportTeam], int]: ...

    @abstractmethod
    async def update_team(
        self, team_id: UUID, *, name: str | None, code: str | None, is_active: bool | None, actor_id: UUID | None,
    ) -> None: ...

    # ---------------------------------------------------- roles

    @abstractmethod
    async def add_role(self, role: SupportRole, actor_id: UUID | None) -> None: ...

    @abstractmethod
    async def get_role(self, role_id: UUID) -> SupportRole | None: ...

    @abstractmethod
    async def role_name_exists(self, team_id: UUID, name: str, exclude_role_id: UUID | None = None) -> bool: ...

    @abstractmethod
    async def list_roles(self, team_id: UUID) -> list[SupportRole]: ...

    @abstractmethod
    async def update_role(
        self, role_id: UUID, *, name: str | None, permissions: list[str] | None, actor_id: UUID | None,
    ) -> None: ...

    # ---------------------------------------------------- members

    @abstractmethod
    async def add_member(self, member: SupportMember, actor_id: UUID | None) -> None: ...

    @abstractmethod
    async def get_member(self, member_id: UUID) -> SupportMember | None: ...

    @abstractmethod
    async def get_member_by_user(self, user_id: UUID) -> SupportMember | None: ...

    @abstractmethod
    async def list_members(
        self, team_id: UUID, *, search: str | None, limit: int, offset: int,
    ) -> tuple[list[SupportMember], int]: ...

    @abstractmethod
    async def update_member(
        self,
        member_id: UUID,
        *,
        role_id: UUID | None,
        set_role: bool,
        is_active: bool | None,
        actor_id: UUID | None,
    ) -> None: ...

    @abstractmethod
    async def update_member_user(
        self, user_id: UUID, *, name: str | None, mobile: str | None, is_active: bool | None,
    ) -> None: ...

    @abstractmethod
    async def mobile_taken(self, mobile: str, exclude_user_id: UUID | None = None) -> bool: ...

    # ---------------------------------------------------- audit

    @abstractmethod
    async def add_audit(self, entry: AuditEntry) -> None: ...
