"""
Ticket Rules (REQ-69, DECISION-031)

The legal status moves, who may make each one and which permission it needs. Pure
Python: the handlers call these before writing anything, so an illegal move can never
reach the database. Requesters use the mobile API only (REQ-67).

Python 3.13+
"""

from __future__ import annotations

from app.modules.support.domain.enums import TicketStatus as S
from app.modules.support.domain.exceptions import InvalidTicketTransitionException
from app.modules.support.domain.permissions import SupportPermission as P

# Staff moves. "Any open state to ESCALATED" is spelled out so the table is the whole truth.
STAFF_TRANSITIONS: dict[S, frozenset[S]] = {
    S.NEW: frozenset({S.ASSIGNED, S.ESCALATED}),
    S.ASSIGNED: frozenset({S.IN_PROGRESS, S.ESCALATED}),
    S.IN_PROGRESS: frozenset({S.WAITING_ON_USER, S.RESOLVED, S.ESCALATED}),
    S.WAITING_ON_USER: frozenset({S.IN_PROGRESS, S.RESOLVED, S.ESCALATED}),
    S.ESCALATED: frozenset({S.IN_PROGRESS, S.RESOLVED}),
    S.RESOLVED: frozenset({S.CLOSED, S.REOPENED}),
    S.CLOSED: frozenset({S.REOPENED}),
    S.REOPENED: frozenset({S.ASSIGNED, S.IN_PROGRESS, S.ESCALATED}),
}

OPEN_STATES = frozenset({S.NEW, S.ASSIGNED, S.IN_PROGRESS, S.WAITING_ON_USER, S.ESCALATED, S.REOPENED})

# The requester may close a ticket they no longer need, or reopen a finished one
REQUESTER_TRANSITIONS: dict[S, frozenset[S]] = {
    **{state: frozenset({S.CLOSED}) for state in OPEN_STATES},
    S.RESOLVED: frozenset({S.CLOSED, S.REOPENED}),
    S.CLOSED: frozenset({S.REOPENED}),
}

# Any one of these permissions lets staff move a ticket INTO the status
REQUIRED_PERMISSIONS: dict[S, tuple[P, ...]] = {
    S.ASSIGNED: (P.TICKET_ASSIGN,),
    S.IN_PROGRESS: (P.TICKET_REPLY, P.TICKET_RESOLVE, P.TICKET_ASSIGN),
    S.WAITING_ON_USER: (P.TICKET_REPLY,),
    S.ESCALATED: (P.TICKET_REPLY, P.TICKET_ASSIGN),
    S.RESOLVED: (P.TICKET_RESOLVE,),
    S.CLOSED: (P.TICKET_CLOSE,),
    S.REOPENED: (P.TICKET_REOPEN,),
}

# What each status means to the requester, shown in the app (the staff labels stay internal)
REQUESTER_LABELS: dict[S, str] = {
    S.NEW: "Received",
    S.ASSIGNED: "In review",
    S.IN_PROGRESS: "In progress",
    S.WAITING_ON_USER: "Waiting for your reply",
    S.ESCALATED: "In progress",
    S.RESOLVED: "Resolved",
    S.CLOSED: "Closed",
    S.REOPENED: "Reopened",
}


def is_open(status: S) -> bool:
    return status in OPEN_STATES


def ensure_staff_transition(current: S, target: S) -> None:
    if target not in STAFF_TRANSITIONS.get(current, frozenset()):
        raise InvalidTicketTransitionException(
            f"A {current.label.lower()} ticket cannot be moved to {target.label.lower()}."
        )


def ensure_requester_transition(current: S, target: S) -> None:
    if target not in REQUESTER_TRANSITIONS.get(current, frozenset()):
        raise InvalidTicketTransitionException(
            f"A {current.label.lower()} ticket cannot be moved to {target.label.lower()}."
        )


def permissions_for(target: S) -> tuple[P, ...]:
    return REQUIRED_PERMISSIONS.get(target, ())


def requester_reply_target(current: S) -> S | None:
    """Where a requester message moves the ticket (None = stays)."""
    if current is S.WAITING_ON_USER:
        return S.IN_PROGRESS
    if current is S.RESOLVED:
        return S.REOPENED
    return None
