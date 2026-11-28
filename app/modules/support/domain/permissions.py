"""
Support Permissions (REQ-61, REQ-63, DECISION-031)

`support.*` permission strings, the five role templates seeded for every team and the pure
rule that decides whether a context holds a permission. No framework imports.

Python 3.13+
"""

from __future__ import annotations

from enum import StrEnum


class SupportPermission(StrEnum):

    TICKET_VIEW_ALL = "support.ticket.view_all"
    TICKET_VIEW_ASSIGNED = "support.ticket.view_assigned"
    TICKET_REPLY = "support.ticket.reply"
    TICKET_ASSIGN = "support.ticket.assign"
    TICKET_RESOLVE = "support.ticket.resolve"
    TICKET_CLOSE = "support.ticket.close"
    TICKET_REOPEN = "support.ticket.reopen"
    TICKET_CHANGE_PRIORITY = "support.ticket.change_priority"
    TICKET_INTERNAL_NOTE = "support.ticket.internal_note"
    TICKET_DELETE = "support.ticket.delete"
    CHAT_USE = "support.chat.use"
    CALL_MAKE = "support.call.make"
    MEMBER_MANAGE = "support.member.manage"
    ROLE_MANAGE = "support.role.manage"
    REPORT_VIEW = "support.report.view"
    TEAM_MANAGE = "support.team.manage"


# Only Super Admin holds this; a team role can never carry it
SUPER_ADMIN_ONLY = frozenset({SupportPermission.TEAM_MANAGE})

# Permissions a Manager can give to team roles (everything except the Super Admin ones)
ASSIGNABLE_PERMISSIONS = frozenset(SupportPermission) - SUPER_ADMIN_ONLY

ALL_PERMISSIONS = frozenset(SupportPermission)

# Heading and one-line help per permission, used by the role editor
PERMISSION_GROUPS: tuple[tuple[str, tuple[tuple[SupportPermission, str], ...]], ...] = (
    ("Tickets", (
        (SupportPermission.TICKET_VIEW_ALL, "See every ticket of the team"),
        (SupportPermission.TICKET_VIEW_ASSIGNED, "See only tickets assigned to them"),
        (SupportPermission.TICKET_REPLY, "Reply to the requester"),
        (SupportPermission.TICKET_INTERNAL_NOTE, "Write internal notes (never shown to the requester)"),
        (SupportPermission.TICKET_ASSIGN, "Assign and reassign tickets to team members"),
        (SupportPermission.TICKET_CHANGE_PRIORITY, "Change priority and category"),
        (SupportPermission.TICKET_RESOLVE, "Mark tickets as resolved"),
        (SupportPermission.TICKET_CLOSE, "Close tickets"),
        (SupportPermission.TICKET_REOPEN, "Reopen resolved or closed tickets"),
        (SupportPermission.TICKET_DELETE, "Delete tickets"),
    )),
    ("Chat and calls", (
        (SupportPermission.CHAT_USE, "Chat live with the requester"),
        (SupportPermission.CALL_MAKE, "Call the requester and log the call"),
    )),
    ("Team", (
        (SupportPermission.MEMBER_MANAGE, "Create, edit and disable members"),
        (SupportPermission.ROLE_MANAGE, "Create and edit roles and permissions"),
        (SupportPermission.REPORT_VIEW, "See team dashboards and activity of members"),
    )),
)


# Role templates seeded for each new team (REQ-61); the Manager may edit them or add roles
ROLE_TEMPLATES: dict[str, frozenset[SupportPermission]] = {
    "Technical Support": frozenset({
        SupportPermission.TICKET_VIEW_ASSIGNED,
        SupportPermission.TICKET_REPLY,
        SupportPermission.TICKET_INTERNAL_NOTE,
        SupportPermission.TICKET_CHANGE_PRIORITY,
        SupportPermission.TICKET_RESOLVE,
        SupportPermission.TICKET_REOPEN,
        SupportPermission.CHAT_USE,
        SupportPermission.CALL_MAKE,
    }),
    "Ticket Assigner": frozenset({
        SupportPermission.TICKET_VIEW_ALL,
        SupportPermission.TICKET_ASSIGN,
        SupportPermission.TICKET_CHANGE_PRIORITY,
        SupportPermission.TICKET_INTERNAL_NOTE,
    }),
    "Chat Agent": frozenset({
        SupportPermission.TICKET_VIEW_ASSIGNED,
        SupportPermission.TICKET_REPLY,
        SupportPermission.TICKET_INTERNAL_NOTE,
        SupportPermission.CHAT_USE,
    }),
    "Caller": frozenset({
        SupportPermission.TICKET_VIEW_ASSIGNED,
        SupportPermission.TICKET_INTERNAL_NOTE,
        SupportPermission.CALL_MAKE,
    }),
    "Viewer": frozenset({
        SupportPermission.TICKET_VIEW_ALL,
    }),
}


def valid_permissions(values: list[str] | tuple[str, ...] | set[str] | frozenset[str]) -> frozenset[SupportPermission]:
    """Turn stored strings into permissions, dropping anything unknown."""
    known: set[SupportPermission] = set()
    for value in values:
        try:
            known.add(SupportPermission(value))
        except ValueError:
            continue
    return frozenset(known)


def has_permission(
    permissions: frozenset[SupportPermission] | frozenset[str],
    permission: SupportPermission,
    *,
    is_manager: bool = False,
    is_super_admin: bool = False,
) -> bool:
    """Super Admin holds everything, a Manager everything except the Super Admin ones."""
    if is_super_admin:
        return True
    if is_manager:
        return permission not in SUPER_ADMIN_ONLY
    return permission in permissions
