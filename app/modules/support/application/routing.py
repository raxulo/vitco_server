"""
Ticket Routing (REQ-68, D-8)

A new ticket goes to its category's default team; with no default team, or when that team is
switched off, it waits in the Super Admin's unassigned pool (team None). Inside a team the
Manager or a Ticket Assigner picks the person.

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID

from app.modules.support.domain.entities import Category, SupportTeam


def route_team(category: Category, team: SupportTeam | None) -> UUID | None:
    """The team a new ticket starts in, or None for the unassigned pool."""
    if category.default_team_id is None or team is None or not team.is_active:
        return None
    return team.id
