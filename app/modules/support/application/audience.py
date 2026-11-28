"""
Support event audience (Phase 27, REQ-73, REQ-63)

Who may receive an event, decided on the server from permission and team scope; the browser or app
never chooses what it hears. Pure functions over a `Subscriber`, so every rule is unit tested.

- the ticket's requester gets public events of their own tickets, never staff-only ones;
- Super Admin gets everything, including the unassigned pool (tickets with no team);
- team staff only hear about their own team, and then: the Manager and members with `view_all` hear
  everything of the team, `view_assigned` members hear about tickets assigned to them (and the one they
  just lost), Ticket Assigners also hear about tickets nobody holds yet.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass
from uuid import UUID

from app.modules.support.application.events import SupportEvent
from app.modules.support.application.guard import SupportContext
from app.modules.support.domain.permissions import SupportPermission as P


@dataclass(slots=True, frozen=True, kw_only=True)
class Subscriber:
    user_id: UUID
    is_requester: bool = False
    is_super_admin: bool = False
    team_id: UUID | None = None
    permissions: frozenset[P] = frozenset()

    @classmethod
    def requester(cls, user_id: UUID) -> "Subscriber":
        return cls(user_id=user_id, is_requester=True)

    @classmethod
    def staff(cls, ctx: SupportContext) -> "Subscriber":
        return cls(
            user_id=ctx.user_id, is_super_admin=ctx.is_super_admin, team_id=ctx.team_id, permissions=ctx.permissions,
        )


def can_receive(subscriber: Subscriber, event: SupportEvent) -> bool:
    user = str(subscriber.user_id)
    if subscriber.is_requester:
        return event.public and event.requester_id == user
    if subscriber.is_super_admin:
        return True
    if event.team_id is None or subscriber.team_id is None or str(subscriber.team_id) != event.team_id:
        return False
    if P.TICKET_VIEW_ALL in subscriber.permissions:
        return True
    if P.TICKET_VIEW_ASSIGNED in subscriber.permissions and user in (event.assigned_to, event.previous_assignee):
        return True
    return P.TICKET_ASSIGN in subscriber.permissions and event.assigned_to is None
