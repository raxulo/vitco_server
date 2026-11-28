"""
Ticket Commands and Queries (CQRS, Phase 26)

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.modules.support.domain.enums import Scope, TicketPriority, TicketStatus


# ---------------------------------------------------------- categories

@dataclass(slots=True, kw_only=True)
class CreateCategoryCommand:
    name: str
    default_team_id: UUID | None = None
    default_priority: TicketPriority = TicketPriority.MEDIUM


@dataclass(slots=True, kw_only=True)
class UpdateCategoryCommand:
    category_id: UUID
    name: str | None = None
    default_team_id: UUID | None = None
    set_team: bool = False
    default_priority: TicketPriority | None = None
    is_active: bool | None = None


# ---------------------------------------------------------- requester

@dataclass(slots=True, kw_only=True)
class CreateTicketCommand:
    subject: str
    description: str
    category_id: UUID
    device_model: str | None = None
    os_version: str | None = None
    app_version: str | None = None
    client_request_id: str | None = None


@dataclass(slots=True, kw_only=True)
class ListRequesterTicketsQuery:
    status: TicketStatus | None = None
    limit: int = 20
    offset: int = 0


@dataclass(slots=True, kw_only=True)
class ListMessagesQuery:
    ticket_id: UUID
    after_id: int | None = None
    limit: int = 50


# ---------------------------------------------------------- messages

@dataclass(slots=True, kw_only=True)
class PostMessageCommand:
    ticket_id: UUID
    body: str
    internal: bool = False
    client_request_id: str | None = None


@dataclass(slots=True, kw_only=True)
class AddAttachmentCommand:
    ticket_id: UUID
    file_name: str
    content_type: str
    data: bytes
    internal: bool = False


# ---------------------------------------------------------- staff actions

@dataclass(slots=True, kw_only=True)
class AssignTicketCommand:
    ticket_id: UUID
    assignee_user_id: UUID


@dataclass(slots=True, kw_only=True)
class RouteTicketCommand:
    ticket_id: UUID
    team_id: UUID


@dataclass(slots=True, kw_only=True)
class ChangeStatusCommand:
    ticket_id: UUID
    status: TicketStatus


@dataclass(slots=True, kw_only=True)
class ChangePriorityCommand:
    ticket_id: UUID
    priority: TicketPriority


@dataclass(slots=True, kw_only=True)
class ChangeCategoryCommand:
    ticket_id: UUID
    category_id: UUID


@dataclass(slots=True, kw_only=True)
class ListStaffTicketsQuery:
    scope: Scope = Scope.ALL
    status: list[TicketStatus] | None = None
    priority: TicketPriority | None = None
    category_id: UUID | None = None
    assignee_id: UUID | None = None
    search: str | None = None
    date_from: datetime | None = None
    date_to: datetime | None = None
    limit: int = 20
    offset: int = 0
