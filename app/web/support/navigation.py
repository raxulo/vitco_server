"""
Support portal sidebar (REQ-58, REQ-65)

One list of entries, each with the permission it needs. A member only gets the entries their
context allows, so a menu they cannot use never shows. Later phases add their entries here.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass

from app.modules.support.application.guard import SupportContext
from app.modules.support.domain.permissions import SupportPermission


@dataclass(slots=True, frozen=True, kw_only=True)
class NavItem:
    key: str
    label: str
    href: str
    icon: str
    permission: SupportPermission | None = None   # None: every member
    super_admin_only: bool = False
    team_scoped: bool = False                     # works inside one team, so Super Admin reaches it from the team page
    count: int = 0


@dataclass(slots=True, frozen=True, kw_only=True)
class NavGroup:
    label: str
    items: tuple[NavItem, ...]


_GROUPS: tuple[tuple[str, tuple[NavItem, ...]], ...] = (
    ("", (
        NavItem(key="dashboard", label="Dashboard", href="/support", icon="fa-solid fa-gauge-high"),
    )),
    ("Administration", (
        NavItem(
            key="teams", label="Support teams", href="/support/teams", icon="fa-solid fa-people-group",
            super_admin_only=True,
        ),
        NavItem(
            key="members", label="Members", href="/support/members", icon="fa-solid fa-user-group",
            permission=SupportPermission.MEMBER_MANAGE, team_scoped=True,
        ),
        NavItem(
            key="roles", label="Roles and permissions", href="/support/roles", icon="fa-solid fa-user-shield",
            permission=SupportPermission.ROLE_MANAGE, team_scoped=True,
        ),
    )),
)


def build_navigation(ctx: SupportContext) -> tuple[NavGroup, ...]:
    groups: list[NavGroup] = []
    for label, items in _GROUPS:
        allowed = tuple(
            item for item in items
            if (not item.super_admin_only or ctx.is_super_admin)
            and not (item.team_scoped and ctx.is_super_admin)
            and (item.permission is None or ctx.has(item.permission))
        )
        if allowed:
            groups.append(NavGroup(label=label, items=allowed))
    return tuple(groups)
