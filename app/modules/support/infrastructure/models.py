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

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
    Enum,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.core.clock import now_naive_ist
from app.core.database.base import Base
from app.core.database.mixins import AuditMixin, UUIDMixin
from app.core.database.types import NaiveDateTime
from app.modules.support.domain.enums import EventType, MessageKind, TicketPriority, TicketStatus


def _enum(enum_class, length: int) -> Enum:
    """Stored as its value in a plain string column, the same on PostgreSQL and SQLite."""
    return Enum(
        enum_class,
        native_enum=False,
        length=length,
        create_constraint=False,
        values_callable=lambda members: [member.value for member in members],
    )


# Messages and events use a growing integer so clients can ask for "everything after id N"
_SEQ = BigInteger().with_variant(Integer, "sqlite")


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


# =========================================================
# PHASE 26: TICKETS (migration 0006)
# =========================================================

class SupportCategoryModel(Base, UUIDMixin, AuditMixin):

    __tablename__ = "support_categories"

    name: Mapped[str] = mapped_column(String(80), nullable=False, unique=True)
    default_team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_teams.id", ondelete="SET NULL"), nullable=True,
    )
    default_priority: Mapped[TicketPriority] = mapped_column(
        _enum(TicketPriority, 10), nullable=False, default=TicketPriority.MEDIUM,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sla_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)  # Version 2


class SupportTicketCounterModel(Base):
    """Last ticket number used in a year; gaps are fine, repeats are not."""

    __tablename__ = "support_ticket_counters"

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    last_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SupportTicketModel(Base, UUIDMixin, AuditMixin):

    __tablename__ = "support_tickets"
    __table_args__ = (
        UniqueConstraint("requester_user_id", "client_request_id", name="uq_support_tickets_client_request"),
        Index("ix_support_tickets_team_status", "team_id", "status"),
        Index("ix_support_tickets_assigned_status", "assigned_to", "status"),
    )

    ticket_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True, index=True)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True,
    )
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_categories.id"), nullable=False, index=True,
    )
    team_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_teams.id"), nullable=True,
    )
    assigned_to: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    priority: Mapped[TicketPriority] = mapped_column(
        _enum(TicketPriority, 10), nullable=False, default=TicketPriority.MEDIUM,
    )
    status: Mapped[TicketStatus] = mapped_column(
        _enum(TicketStatus, 20), nullable=False, default=TicketStatus.NEW,
    )
    subject: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    device_model: Mapped[str | None] = mapped_column(String(100), nullable=True)
    os_version: Mapped[str | None] = mapped_column(String(50), nullable=True)
    app_version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    first_response_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    last_message_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True, index=True)
    resolved_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)  # Version 2
    requester_unread: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    staff_unread: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class SupportTicketMessageModel(Base):

    __tablename__ = "support_ticket_messages"
    __table_args__ = (
        UniqueConstraint("ticket_id", "sender_user_id", "client_request_id", name="uq_support_messages_client_request"),
        Index("ix_support_ticket_messages_ticket_id_id", "ticket_id", "id"),
    )

    id: Mapped[int] = mapped_column(_SEQ, primary_key=True, autoincrement=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False,
    )
    sender_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    sender_is_staff: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    kind: Mapped[MessageKind] = mapped_column(_enum(MessageKind, 12), nullable=False, default=MessageKind.TEXT)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_internal: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    client_request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)
    # Deleted by its sender (migration 0010): the row stays as a placeholder, text and files are removed
    deleted_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    deleted_by: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)


class SupportTicketEventModel(Base):

    __tablename__ = "support_ticket_events"
    __table_args__ = (Index("ix_support_ticket_events_ticket_id_id", "ticket_id", "id"),)

    id: Mapped[int] = mapped_column(_SEQ, primary_key=True, autoincrement=True)
    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False,
    )
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    event_type: Mapped[EventType] = mapped_column(_enum(EventType, 24), nullable=False)
    from_value: Mapped[str | None] = mapped_column(String(80), nullable=True)
    to_value: Mapped[str | None] = mapped_column(String(80), nullable=True)
    meta: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)


class SupportAttachmentModel(Base, UUIDMixin):

    __tablename__ = "support_attachments"

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    message_id: Mapped[int | None] = mapped_column(
        _SEQ, ForeignKey("support_ticket_messages.id", ondelete="CASCADE"), nullable=True, index=True,
    )
    uploaded_by: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True,
    )
    file_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)


# =========================================================
# PHASE 29: CALLS (migration 0008)
# =========================================================

class SupportCallLogModel(Base, UUIDMixin):

    __tablename__ = "support_call_logs"
    __table_args__ = (Index("ix_support_call_logs_member_started", "member_user_id", "started_at"),)

    ticket_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("support_tickets.id", ondelete="CASCADE"), nullable=False, index=True,
    )
    member_user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    requester_user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False,
    )
    started_at: Mapped[datetime] = mapped_column(NaiveDateTime(), nullable=False, default=now_naive_ist)
    finished_at: Mapped[datetime | None] = mapped_column(NaiveDateTime(), nullable=True)
    outcome: Mapped[str | None] = mapped_column(String(20), nullable=True)
    duration_s: Mapped[int | None] = mapped_column(Integer, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
