"""
Technical Support API schemas (mobile app, Phase 26).

Each response model lists exactly what a requester may see, so a field added to a domain
object never reaches the app by accident: no internal notes, no member ids, no assignee phone.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.modules.support.domain import ticket_rules
from app.modules.support.domain.entities import (
    Category,
    Ticket,
    TicketAttachment,
    TicketEvent,
    TicketMessage,
)
from app.modules.support.domain.enums import EventType, MessageKind, TicketPriority, TicketStatus

Limit = Annotated[int, Field(ge=1, le=100)]
Offset = Annotated[int, Field(ge=0)]


# =========================================================
# REQUESTS
# =========================================================


class CreateTicketRequest(BaseModel):
    """`client_request_id` is any unique text the app makes once per ticket, so a retry never doubles it."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "subject": "Sync is not working",
                "description": "The app shows 'sync failed' since morning.",
                "category_id": "8f4e2c1a-7b3d-4f6e-9a10-2b5c6d7e8f90",
                "device_model": "Redmi 9",
                "os_version": "Android 13",
                "app_version": "2.4.1",
                "client_request_id": "a3f1c9e2-1b7d-4c55-8a9e-0d2f6b7c1e44",
            }
        }
    )

    subject: str = Field(min_length=3, max_length=200)
    description: str = Field(min_length=5, max_length=4000)
    category_id: UUID
    device_model: str | None = Field(default=None, max_length=300)
    os_version: str | None = Field(default=None, max_length=300)
    app_version: str | None = Field(default=None, max_length=300)
    client_request_id: str | None = Field(default=None, max_length=64)


class PostMessageRequest(BaseModel):
    model_config = ConfigDict(
        json_schema_extra={"example": {"body": "It still fails after logging in again.", "client_request_id": "m-17"}}
    )

    body: str = Field(min_length=1, max_length=4000)
    client_request_id: str | None = Field(default=None, max_length=64)


# =========================================================
# RESPONSES
# =========================================================


class _Out(BaseModel):
    model_config = ConfigDict(from_attributes=True)


class CategoryOut(_Out):
    id: UUID
    name: str

    @classmethod
    def of(cls, category: Category) -> "CategoryOut":
        return cls(id=category.id, name=category.name)


class AttachmentOut(_Out):
    id: UUID
    file_name: str
    mime_type: str
    size_bytes: int
    url: str

    @classmethod
    def of(cls, attachment: TicketAttachment) -> "AttachmentOut":
        return cls(
            id=attachment.id,
            file_name=attachment.file_name,
            mime_type=attachment.mime_type,
            size_bytes=attachment.size_bytes,
            url=f"/api/v1/support/attachments/{attachment.id}",
        )


class MessageOut(_Out):
    id: int
    kind: MessageKind
    body: str
    from_you: bool
    sender_label: str
    created_at: datetime | None
    # A deleted message keeps its place: `body` is empty and `attachments` is empty
    is_deleted: bool = False
    deleted_at: datetime | None = None
    attachments: list[AttachmentOut] = []

    @classmethod
    def of(cls, message: TicketMessage, requester_id: UUID) -> "MessageOut":
        from_you = message.sender_user_id == requester_id
        return cls(
            id=message.id,
            kind=message.kind,
            body="" if message.is_deleted else message.body,
            from_you=from_you,
            sender_label="You" if from_you else "Support team",
            created_at=message.created_at,
            is_deleted=message.is_deleted,
            deleted_at=message.deleted_at,
            attachments=[] if message.is_deleted else [AttachmentOut.of(item) for item in message.attachments],
        )


class TimelineOut(_Out):
    id: int
    type: EventType
    from_status: str | None = None
    to_status: str | None = None
    created_at: datetime | None

    @classmethod
    def of(cls, event: TicketEvent) -> "TimelineOut":
        from_status = to_status = None
        if event.event_type is EventType.STATUS_CHANGED:
            from_status = _label(event.from_value)
            to_status = _label(event.to_value)
        elif event.event_type is EventType.CREATED:
            to_status = _label(event.to_value)
        return cls(
            id=event.id, type=event.event_type, from_status=from_status, to_status=to_status,
            created_at=event.created_at,
        )


def _label(value: str | None) -> str | None:
    if not value:
        return None
    try:
        return ticket_rules.REQUESTER_LABELS[TicketStatus(value)]
    except (ValueError, KeyError):
        return value


class TicketCardOut(_Out):
    id: UUID
    ticket_no: str
    subject: str
    status: TicketStatus
    status_label: str
    is_open: bool
    priority: TicketPriority
    category_id: UUID
    category_name: str | None
    unread: int
    created_at: datetime | None
    updated_at: datetime | None
    last_message_at: datetime | None

    @classmethod
    def of(cls, ticket: Ticket) -> "TicketCardOut":
        return cls(
            id=ticket.id,
            ticket_no=ticket.ticket_no,
            subject=ticket.subject,
            status=ticket.status,
            status_label=ticket_rules.REQUESTER_LABELS[ticket.status],
            is_open=ticket_rules.is_open(ticket.status),
            priority=ticket.priority,
            category_id=ticket.category_id,
            category_name=ticket.category_name,
            unread=ticket.requester_unread,
            created_at=ticket.created_at,
            updated_at=ticket.updated_at,
            last_message_at=ticket.last_message_at,
        )


class TicketDetailOut(TicketCardOut):
    description: str
    device_model: str | None
    os_version: str | None
    app_version: str | None
    resolved_at: datetime | None
    closed_at: datetime | None
    messages: list[MessageOut]
    timeline: list[TimelineOut]
    can_reply: bool
    can_reopen: bool
    can_close: bool

    @classmethod
    def build(
        cls, ticket: Ticket, messages: list[TicketMessage], events: list[TicketEvent],
    ) -> "TicketDetailOut":
        card = TicketCardOut.of(ticket).model_dump()
        status = ticket.status
        return cls(
            **card,
            description=ticket.description,
            device_model=ticket.device_model,
            os_version=ticket.os_version,
            app_version=ticket.app_version,
            resolved_at=ticket.resolved_at,
            closed_at=ticket.closed_at,
            messages=[MessageOut.of(message, ticket.requester_user_id) for message in messages],
            timeline=[TimelineOut.of(event) for event in events],
            can_reply=status is not TicketStatus.CLOSED,
            can_reopen=TicketStatus.REOPENED in ticket_rules.REQUESTER_TRANSITIONS.get(status, frozenset()),
            can_close=TicketStatus.CLOSED in ticket_rules.REQUESTER_TRANSITIONS.get(status, frozenset()),
        )


def dump(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
