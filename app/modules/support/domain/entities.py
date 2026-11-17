"""
Support Entities

Pure dataclasses, no framework imports.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any
from uuid import UUID

from app.modules.support.domain.permissions import SupportPermission


@dataclass(slots=True, kw_only=True)
class SupportTeam:
    id: UUID
    name: str
    code: str
    manager_user_id: UUID
    is_active: bool = True
    created_at: datetime | None = None
    # Filled by list / get queries
    manager_name: str | None = None
    manager_mobile: str | None = None
    manager_email: str | None = None
    member_count: int = 0


@dataclass(slots=True, kw_only=True)
class SupportRole:
    id: UUID
    team_id: UUID
    name: str
    permissions: frozenset[SupportPermission] = frozenset()
    is_system: bool = False
    member_count: int = 0


@dataclass(slots=True, kw_only=True)
class SupportMember:
    id: UUID
    user_id: UUID
    team_id: UUID
    role_id: UUID | None
    is_manager: bool = False
    is_active: bool = True
    # Joined from the user and the role
    name: str = ""
    email: str = ""
    mobile: str | None = None
    last_login: datetime | None = None
    role_name: str | None = None
    permissions: frozenset[SupportPermission] = frozenset()
    team_name: str | None = None
    team_is_active: bool = True


@dataclass(slots=True, kw_only=True)
class AuditEntry:
    actor_id: UUID | None
    action: str
    entity: str
    entity_id: str | None = None
    team_id: UUID | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    id: UUID | None = None
    created_at: datetime | None = None
