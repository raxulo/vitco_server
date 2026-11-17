"""
Support Models (SQLAlchemy 2.0)

`support_teams`, `support_roles`, `support_members` and `support_audit_log`
(Phase 25, migration 0005). Staff themselves are rows in `users` with `Role.SUPPORT`.

Python 3.13+
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import JSON, Boolean, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_naive_ist
from app.core.database.base import Base
from app.core.database.mixins import AuditMixin, UUIDMixin
from app.core.database.types import NaiveDateTime


class SupportTeamModel(Base, UUIDMixin, AuditMixin):

    __tablename__ = "support_teams"

    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code: Mapped[str] = mapped_column(String(30), nullable=False, unique=True, index=True)
    manager_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SupportRoleModel(Base, UUIDMixin, AuditMixin):

    __tablename__ = "support_roles"
    __table_args__ = (UniqueConstraint("team_id", "name", name="uq_support_roles_team_name"),)

    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_teams.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    permissions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)


class SupportMemberModel(Base, UUIDMixin, AuditMixin):

    __tablename__ = "support_members"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True,
    )
    team_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_teams.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    # The Manager has no role: it holds every team permission
    role_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_roles.id"), nullable=True, index=True,
    )
    is_manager: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)


class SupportAuditLogModel(Base, UUIDMixin):

    __tablename__ = "support_audit_log"
    __table_args__ = (Index("ix_support_audit_log_team_created", "team_id", "created_at"),)

    actor_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True, index=True)
    team_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    action: Mapped[str] = mapped_column(String(60), nullable=False)
    entity: Mapped[str] = mapped_column(String(40), nullable=False)
    entity_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)
