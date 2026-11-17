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
