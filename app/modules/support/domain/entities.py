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

from app.modules.support.domain.enums import EventType, MessageKind, TicketPriority, TicketStatus
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


@dataclass(slots=True, kw_only=True)
class Category:
    id: UUID
    name: str
    default_team_id: UUID | None = None
    default_priority: TicketPriority = TicketPriority.MEDIUM
    is_active: bool = True
    # Filled by list queries
    default_team_name: str | None = None


@dataclass(slots=True, kw_only=True)
class Ticket:
    id: UUID
    ticket_no: str
    requester_user_id: UUID
    category_id: UUID
    subject: str
    description: str
    status: TicketStatus = TicketStatus.NEW
    priority: TicketPriority = TicketPriority.MEDIUM
    team_id: UUID | None = None
    assigned_to: UUID | None = None
    device_model: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    client_request_id: str | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    first_response_at: datetime | None = None
    last_message_at: datetime | None = None
    resolved_at: datetime | None = None
    closed_at: datetime | None = None
    sla_due_at: datetime | None = None  # Version 2
    requester_unread: int = 0
    staff_unread: int = 0
    # Joined for screens (REQ-62): basic profile, phone, device, never dairy data
    category_name: str | None = None
    team_name: str | None = None
    requester_name: str | None = None
    requester_role: int | None = None
    requester_mobile: str | None = None
    requester_email: str | None = None
    requester_parent: str | None = None
    assignee_name: str | None = None


@dataclass(slots=True, kw_only=True)
class TicketMessage:
    id: int | None = None
    ticket_id: UUID
    sender_user_id: UUID | None
    sender_is_staff: bool
    body: str
    kind: MessageKind = MessageKind.TEXT
    is_internal: bool = False
    client_request_id: str | None = None
    created_at: datetime | None = None
    # A deleted message stays in the conversation as "deleted", without its text or files
    deleted_at: datetime | None = None
    sender_name: str | None = None
    attachments: list["TicketAttachment"] = field(default_factory=list)

    @property
    def is_deleted(self) -> bool:
        return self.deleted_at is not None


@dataclass(slots=True, kw_only=True)
class TicketEvent:
    id: int | None = None
    ticket_id: UUID
    actor_user_id: UUID | None
    event_type: EventType
    from_value: str | None = None
    to_value: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)
    is_public: bool = True
    created_at: datetime | None = None
    actor_name: str | None = None


@dataclass(slots=True, kw_only=True)
class TicketAttachment:
    id: UUID
    ticket_id: UUID
    message_id: int | None
    uploaded_by: UUID | None
    file_name: str
    mime_type: str
    size_bytes: int
    storage_key: str
    created_at: datetime | None = None


@dataclass(slots=True, kw_only=True)
class CallLog:
    """One click-to-call (REQ-78): started when the member presses Call, finished with the outcome."""

    id: UUID
    ticket_id: UUID
    member_user_id: UUID
    requester_user_id: UUID
    started_at: datetime | None = None
    finished_at: datetime | None = None
    outcome: str | None = None
    duration_s: int | None = None
    note: str | None = None
    member_name: str | None = None
    ticket_no: str | None = None

    @property
    def is_open(self) -> bool:
        return self.finished_at is None
