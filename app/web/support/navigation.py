"""
Support portal sidebar (REQ-58, REQ-65)

One list of entries, each with the permission it needs. A member only gets the entries their
context allows, so a menu they cannot use never shows. Later phases add their entries here.

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from app.modules.support.application.guard import SupportContext
from app.modules.support.domain.permissions import SupportPermission as P


@dataclass(slots=True, frozen=True, kw_only=True)
class NavItem:
    key: str
    label: str
    href: str
    icon: str
    permission: P | None = None                   # None: every member
    any_of: tuple[P, ...] = ()                    # alternative to `permission`: one of these is enough
    super_admin_only: bool = False
    team_scoped: bool = False                     # works inside one team, so Super Admin reaches it from the team page
    hide_for_super_admin: bool = False
    manager_or_super_admin: bool = False
    count_key: str | None = None                  # key in the queue counts shown as the badge
    count: int = 0


@dataclass(slots=True, frozen=True, kw_only=True)
class NavGroup:
    label: str
    items: tuple[NavItem, ...]


_GROUPS: tuple[tuple[str, tuple[NavItem, ...]], ...] = (
    ("", (
        NavItem(key="dashboard", label="Dashboard", href="/support", icon="fa-solid fa-gauge-high"),
    )),
    ("Tickets", (
        NavItem(
            key="unassigned", label="Unassigned queue", href="/support/tickets?scope=unassigned",
            icon="fa-solid fa-inbox", any_of=(P.TICKET_VIEW_ALL, P.TICKET_ASSIGN), count_key="unassigned",
        ),
        NavItem(
            key="all", label="All tickets", href="/support/tickets?scope=all", icon="fa-solid fa-layer-group",
            permission=P.TICKET_VIEW_ALL, count_key="all",
        ),
        NavItem(
            key="mine", label="My tickets", href="/support/tickets?scope=mine", icon="fa-solid fa-user-check",
            any_of=(P.TICKET_VIEW_ASSIGNED, P.TICKET_VIEW_ALL), hide_for_super_admin=True, count_key="mine",
        ),
    )),
    ("Insights", (
        NavItem(
            key="activity", label="My activity", href="/support/activity", icon="fa-solid fa-chart-simple",
            hide_for_super_admin=True,
        ),
        NavItem(
            key="team_activity", label="Team activity", href="/support/activity/team", icon="fa-solid fa-ranking-star",
            permission=P.REPORT_VIEW,
        ),
        NavItem(
            key="audit", label="Audit log", href="/support/audit", icon="fa-solid fa-clipboard-list",
            manager_or_super_admin=True,
        ),
    )),
    ("Administration", (
        NavItem(
            key="teams", label="Support teams", href="/support/teams", icon="fa-solid fa-people-group",
            super_admin_only=True,
        ),
        NavItem(
            key="categories", label="Categories", href="/support/categories", icon="fa-solid fa-tags",
            super_admin_only=True,
        ),
        NavItem(
            key="members", label="Members", href="/support/members", icon="fa-solid fa-user-group",
            permission=P.MEMBER_MANAGE, team_scoped=True,
        ),
        NavItem(
            key="roles", label="Roles and permissions", href="/support/roles", icon="fa-solid fa-user-shield",
            permission=P.ROLE_MANAGE, team_scoped=True,
        ),
    )),
)


def _allowed(item: NavItem, ctx: SupportContext) -> bool:
    if item.super_admin_only and not ctx.is_super_admin:
        return False
    if item.team_scoped and ctx.is_super_admin:
        return False
    if item.hide_for_super_admin and ctx.is_super_admin:
        return False
    if item.manager_or_super_admin and not (ctx.is_super_admin or ctx.is_manager):
        return False
    if item.permission is not None and not ctx.has(item.permission):
        return False
    if item.any_of and not any(ctx.has(permission) for permission in item.any_of):
        return False
    return True


def default_scope(ctx: SupportContext) -> str | None:
    """The queue a member lands on when they open Tickets without choosing one."""
    for key in ("unassigned", "all", "mine"):
        item = next(i for _, items in _GROUPS for i in items if i.key == key)
        if _allowed(item, ctx):
            return key
    return None


def build_navigation(ctx: SupportContext, counts: dict[str, int] | None = None) -> tuple[NavGroup, ...]:
    counts = counts or {}
    groups: list[NavGroup] = []
    for label, items in _GROUPS:
        allowed = tuple(
            replace(item, count=counts.get(item.count_key or "", 0)) for item in items if _allowed(item, ctx)
        )
        if allowed:
            groups.append(NavGroup(label=label, items=allowed))
    return tuple(groups)
