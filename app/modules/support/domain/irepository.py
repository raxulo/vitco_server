"""
Support Repository Interface

Python 3.13+
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.modules.support.domain.enums import Scope, TicketPriority, TicketStatus
from app.modules.support.domain.entities import (
    AuditEntry,
    Category,
    Ticket,
    TicketAttachment,
    TicketEvent,
    TicketMessage,
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

    @abstractmethod
    async def audit_exists_since(self, *, actor_id: UUID, action: str, entity_id: str, since: datetime) -> bool: ...


class ITicketRepository(ABC):
    """Tickets, messages, events and categories (Phase 26). Never commits."""

    # ---------------------------------------------------- categories

    @abstractmethod
    async def add_category(self, category: Category, actor_id: UUID | None) -> None: ...

    @abstractmethod
    async def get_category(self, category_id: UUID) -> Category | None: ...

    @abstractmethod
    async def category_name_exists(self, name: str, exclude_category_id: UUID | None = None) -> bool: ...

    @abstractmethod
    async def list_categories(self, *, active_only: bool) -> list[Category]: ...

    @abstractmethod
    async def update_category(
        self,
        category_id: UUID,
        *,
        name: str | None,
        default_team_id: UUID | None,
        set_team: bool,
        default_priority: TicketPriority | None,
        is_active: bool | None,
        actor_id: UUID | None,
    ) -> None: ...

    # ---------------------------------------------------- tickets

    @abstractmethod
    async def next_ticket_number(self, year: int) -> str: ...

    @abstractmethod
    async def add_ticket(self, ticket: Ticket) -> None: ...

    @abstractmethod
    async def get_ticket(self, ticket_id: UUID) -> Ticket | None: ...

    @abstractmethod
    async def find_by_client_request(self, requester_user_id: UUID, client_request_id: str) -> Ticket | None: ...

    @abstractmethod
    async def list_for_requester(
        self, requester_user_id: UUID, *, status: TicketStatus | None, limit: int, offset: int,
    ) -> tuple[list[Ticket], int]: ...

    @abstractmethod
    async def list_for_staff(
        self,
        *,
        scope: Scope,
        team_id: UUID | None,
        user_id: UUID,
        limit_to_assigned: bool,
        status: list[TicketStatus] | None,
        priority: TicketPriority | None,
        category_id: UUID | None,
        assignee_id: UUID | None,
        search: str | None,
        date_from: datetime | None,
        date_to: datetime | None,
        limit: int,
        offset: int,
    ) -> tuple[list[Ticket], int]: ...

    @abstractmethod
    async def update_ticket(self, ticket_id: UUID, values: dict) -> None: ...

    @abstractmethod
    async def bump_unread(self, ticket_id: UUID, *, for_staff: bool) -> None: ...

    @abstractmethod
    async def clear_unread(self, ticket_id: UUID, *, for_staff: bool) -> None: ...

    @abstractmethod
    async def queue_counts(self, *, team_id: UUID | None, user_id: UUID) -> dict[str, int]:
        """Open tickets for the sidebar badges: `unassigned`, `all` and `mine`, in one query."""

    @abstractmethod
    async def member_is_assignable(self, user_id: UUID, team_id: UUID) -> bool: ...

    # ---------------------------------------------------- messages, events, attachments

    @abstractmethod
    async def add_message(self, message: TicketMessage) -> TicketMessage: ...

    @abstractmethod
    async def get_message(self, message_id: int) -> TicketMessage | None: ...

    @abstractmethod
    async def delete_message(self, message_id: int, *, deleted_by: UUID, deleted_at: datetime) -> list[str]:
        """Blank a message and drop its attachments; returns the storage keys of the dropped files."""

    @abstractmethod
    async def find_message_by_client_request(
        self, ticket_id: UUID, sender_user_id: UUID, client_request_id: str,
    ) -> TicketMessage | None: ...

    @abstractmethod
    async def list_messages(
        self, ticket_id: UUID, *, include_internal: bool, after_id: int | None, limit: int,
    ) -> list[TicketMessage]: ...

    @abstractmethod
    async def add_event(self, event: TicketEvent) -> TicketEvent: ...

    @abstractmethod
    async def list_events(self, ticket_id: UUID, *, public_only: bool) -> list[TicketEvent]: ...

    @abstractmethod
    async def add_attachment(self, attachment: TicketAttachment) -> None: ...

    @abstractmethod
    async def get_attachment(self, attachment_id: UUID) -> TicketAttachment | None: ...
