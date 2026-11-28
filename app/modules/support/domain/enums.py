"""
Support Enums

Python 3.13+
"""

from __future__ import annotations

from enum import StrEnum


class AuditAction(StrEnum):
    """What an audit row records (REQ-64)."""

    TEAM_CREATED = "team.created"
    TEAM_UPDATED = "team.updated"
    TEAM_ACTIVATED = "team.activated"
    TEAM_DEACTIVATED = "team.deactivated"
    MEMBER_CREATED = "member.created"
    MEMBER_UPDATED = "member.updated"
    MEMBER_ACTIVATED = "member.activated"
    MEMBER_DEACTIVATED = "member.deactivated"
    MEMBER_ROLE_CHANGED = "member.role_changed"
    ROLE_CREATED = "role.created"
    ROLE_UPDATED = "role.updated"
    CATEGORY_CREATED = "category.created"
    CATEGORY_UPDATED = "category.updated"
    TICKET_CREATED = "ticket.created"
    TICKET_ROUTED = "ticket.routed"
    TICKET_ASSIGNED = "ticket.assigned"
    TICKET_STATUS_CHANGED = "ticket.status_changed"
    TICKET_PRIORITY_CHANGED = "ticket.priority_changed"
    TICKET_CATEGORY_CHANGED = "ticket.category_changed"
    TICKET_NOTE_ADDED = "ticket.note_added"
    MESSAGE_DELETED = "ticket.message_deleted"
    PHONE_VIEWED = "ticket.phone_viewed"
    CALL_STARTED = "call.started"
    CALL_LOGGED = "call.logged"


class TicketStatus(StrEnum):
    """REQ-69. Stored as its value; the legal moves live in `ticket_rules`."""

    NEW = "NEW"
    ASSIGNED = "ASSIGNED"
    IN_PROGRESS = "IN_PROGRESS"
    WAITING_ON_USER = "WAITING_ON_USER"
    ESCALATED = "ESCALATED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    REOPENED = "REOPENED"

    @property
    def label(self) -> str:
        return self.value.replace("_", " ").title()


class TicketPriority(StrEnum):

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"

    @property
    def label(self) -> str:
        return self.value.title()


class MessageKind(StrEnum):

    TEXT = "TEXT"
    ATTACHMENT = "ATTACHMENT"
    AUDIO = "AUDIO"            # a voice message: one audio file, played in the conversation
    SYSTEM = "SYSTEM"


class EventType(StrEnum):
    """One timeline row per change (REQ-69)."""

    CREATED = "CREATED"
    ROUTED = "ROUTED"
    ASSIGNED = "ASSIGNED"
    STATUS_CHANGED = "STATUS_CHANGED"
    PRIORITY_CHANGED = "PRIORITY_CHANGED"
    CATEGORY_CHANGED = "CATEGORY_CHANGED"
    NOTE_ADDED = "NOTE_ADDED"
    REPLIED = "REPLIED"
    REQUESTER_REPLIED = "REQUESTER_REPLIED"
    ATTACHMENT_ADDED = "ATTACHMENT_ADDED"
    MESSAGE_DELETED = "MESSAGE_DELETED"
    CALL_STARTED = "CALL_STARTED"
    CALL_LOGGED = "CALL_LOGGED"


class Scope(StrEnum):
    """Which ticket queue a staff member is looking at."""

    UNASSIGNED = "unassigned"
    ALL = "all"
    MINE = "mine"


class CallOutcome(StrEnum):
    """What happened on a call (REQ-78)."""

    CONNECTED = "CONNECTED"
    NOT_REACHABLE = "NOT_REACHABLE"
    BUSY = "BUSY"
    CALLBACK_REQUESTED = "CALLBACK_REQUESTED"

    @property
    def label(self) -> str:
        return {
            "CONNECTED": "Connected",
            "NOT_REACHABLE": "Not reachable",
            "BUSY": "Busy",
            "CALLBACK_REQUESTED": "Callback requested",
        }[self.value]
