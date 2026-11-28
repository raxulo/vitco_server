"""
Support Commands and Queries (CQRS)

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID


# ---------------------------------------------------------- teams

@dataclass(slots=True, kw_only=True)
class CreateTeamCommand:
    name: str
    code: str
    manager_name: str
    manager_email: str
    manager_mobile: str
    manager_password: str


@dataclass(slots=True, kw_only=True)
class UpdateTeamCommand:
    team_id: UUID
    name: str | None = None
    code: str | None = None


@dataclass(slots=True, kw_only=True)
class SetTeamActiveCommand:
    team_id: UUID
    is_active: bool


@dataclass(slots=True, kw_only=True)
class ListTeamsQuery:
    search: str | None = None
    limit: int = 20
    offset: int = 0


# ---------------------------------------------------------- members

@dataclass(slots=True, kw_only=True)
class CreateMemberCommand:
    role_id: UUID
    name: str
    email: str
    mobile: str
    password: str
    team_id: UUID | None = None          # only Super Admin names a team; a Manager always uses its own


@dataclass(slots=True, kw_only=True)
class UpdateMemberCommand:
    member_id: UUID
    name: str | None = None
    mobile: str | None = None
    role_id: UUID | None = None


@dataclass(slots=True, kw_only=True)
class SetMemberActiveCommand:
    member_id: UUID
    is_active: bool


@dataclass(slots=True, kw_only=True)
class ListMembersQuery:
    team_id: UUID | None = None
    search: str | None = None
    limit: int = 20
    offset: int = 0


# ---------------------------------------------------------- roles

@dataclass(slots=True, kw_only=True)
class CreateRoleCommand:
    name: str
    permissions: list[str]
    team_id: UUID | None = None


@dataclass(slots=True, kw_only=True)
class UpdateRoleCommand:
    role_id: UUID
    name: str | None = None
    permissions: list[str] | None = None
