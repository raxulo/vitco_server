# administration/presentation/web/navigation.py

from dataclasses import dataclass
from enum import IntEnum
from typing import Final

from app.modules.administration.domain.enums import Role


class MenuPermission(IntEnum):
    ALL = -1


@dataclass(frozen=True, slots=True)
class MenuItem:
    label: str
    href: str
    icon: str
    roles: frozenset[int]
    match: str


@dataclass(frozen=True, slots=True)
class MenuGroup:
    label: str
    css_class: str
    items: tuple[MenuItem, ...]


# Role sets use the real `Role` values (the login token carries them:
# SUPER_ADMIN=1, ADMIN=2, SUB_ADMIN=3, MCC=4, VLCC=5, FARMER=6).
SUPER_ADMIN_ONLY: Final = frozenset({Role.SUPER_ADMIN})
FARMER_ONLY: Final = frozenset({Role.FARMER})
# Managed Admins page: Super Admin manages Admins / Sub Admins, an Admin its own Sub Admins
ADMIN_ROLES: Final = frozenset({Role.SUPER_ADMIN, Role.ADMIN})
# Super Admin, Admin, Sub Admin: MCC management and the System Setup masters
MANAGEMENT_ROLES: Final = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN})
# MCC Management pages an MCC user also sees (its own MCC is view-only for it)
MCC_VIEW_ROLES: Final = MANAGEMENT_ROLES | {Role.MCC}
# Route codes can only be created by the management roles
ROUTE_CREATOR_ROLES: Final = MANAGEMENT_ROLES
# Every staff role (farmers get their own FARMER_ONLY items)
ALL_ROLES: Final = frozenset({Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC})


def item(
    label: str,
    href: str,
    icon: str,
    roles: frozenset[int],
    match: str,
) -> MenuItem:
    return MenuItem(
        label=label,
        href=href,
        icon=icon,
        roles=roles,
        match=match,
    )


ADMIN_NAVIGATION: Final[tuple[MenuGroup, ...]] = (

    MenuGroup(
        label="General",
        css_class="general-group-header",
        items=(
            item(
                "Dashboard",
                "/dashboard",
                "fa-solid fa-house-chimney-window",
                ALL_ROLES | FARMER_ONLY,
                "/dashboard",
            ),
            # Farmer sees only its own collections and received payments
            item(
                "My Collections",
                "/vlcc-collections/",
                "fa-solid fa-flask",
                FARMER_ONLY,
                "/vlcc-collections",
            ),
            item(
                "My Payments",
                "/payments/history",
                "fa-solid fa-indian-rupee-sign",
                FARMER_ONLY,
                "/payments/history",
            ),
            item(
                "Managed Admins",
                "/sub-admins",
                "fa-solid fa-user-gear",
                ADMIN_ROLES,
                "/sub-admins",
            ),
        ),
    ),

    MenuGroup(
        label="MCC Management",
        css_class="mcc-group-header",
        items=(
            item(
                "MCC Master",
                "/mcc/",
                "fa-solid fa-sitemap",
                MCC_VIEW_ROLES,
                "/mcc",
            ),
            item(
                "MCC Collection",
                "/mcc-collections/",
                "fa-solid fa-truck-ramp-box",
                MCC_VIEW_ROLES,
                "/mcc-collections",
            ),
            item(
                "Map MCCs",
                "/ratecharts/assign-mcc",
                "fa-solid fa-link",
                MANAGEMENT_ROLES,
                "/ratecharts/assign-mcc",
            ),
            item(
                "MCC Reports",
                "/mcc-reports",
                "fa-solid fa-file-invoice-dollar",
                MCC_VIEW_ROLES,
                "/mcc-reports",
            ),
        ),
    ),

    MenuGroup(
        label="VLCC Management",
        css_class="dairy-group-header",
        items=(
            item(
                "My VLCC",
                "/vlcc/",
                "fa-solid fa-building",
                ALL_ROLES,
                "/vlcc",
            ),
            item(
                "Farmers",
                "/farmer/",
                "fa-solid fa-users",
                ALL_ROLES,
                "/farmer",
            ),
            item(
                "VLCC Collection",
                "/vlcc-collections/",
                "fa-solid fa-flask",
                ALL_ROLES,
                "/vlcc-collections",
            ),
            item(
                "Dispatches",
                "/vlcc-dispatches",
                "fa-solid fa-truck-ramp-box",
                ALL_ROLES,
                "/vlcc-dispatches",
            ),
            item(
                "Map VLCC",
                "/ratecharts/assign",
                "fa-solid fa-link",
                MANAGEMENT_ROLES,
                "/ratecharts/assign",
            ),
            item(
                "VLCC Reports",
                "/reports/",
                "fa-solid fa-chart-bar",
                ALL_ROLES,
                "/reports",
            ),
        ),
    ),

    MenuGroup(
        label="System Setup",
        css_class="config-group-header",
        items=(
            item(
                "Route Master",
                "/routes/",
                "fa-solid fa-route",
                ROUTE_CREATOR_ROLES,
                "/routes/",
            ),
            item(
                "Unit Master",
                "/units/",
                "fa-solid fa-scale-balanced",
                # MCC / VLCC see shared units; "create" follows their master_enabled permission
                ALL_ROLES,
                "/units/",
            ),
            item(
                "Item Master",
                "/items/",
                "fa-solid fa-boxes-stacked",
                # MCC / VLCC see shared items; "create" follows their master_enabled permission
                ALL_ROLES,
                "/items/",
            ),
            item(
                "Advance Master",
                "/advance-items/",
                "fa-solid fa-boxes-packing",
                ALL_ROLES,
                "/advance-items/",
            ),
            item(
                "Rate Charts",
                "/ratecharts/",
                "fa-solid fa-tags",
                # MCC / VLCC always view; create / modify follows their rate chart permission
                ALL_ROLES,
                "/ratecharts",
            ),
        ),
    ),

    MenuGroup(
        label="Payments",
        css_class="payment-group-header",
        items=(
            item(
                "Overview",
                "/payments/overview",
                "fa-solid fa-money-bill-transfer",
                ALL_ROLES,
                "/payments/overview",
            ),
            item(
                "History",
                "/payments/history",
                "fa-solid fa-clock-rotate-left",
                ALL_ROLES,
                "/payments/history",
            ),
            item(
                "Give / Receive",
                "/payments/user-to",
                "fa-solid fa-user-tag",
                ALL_ROLES,
                "/payments/user-to",
            ),
            item(
                "Outstanding",
                "/payments/outstanding",
                "fa-solid fa-hand-holding-hand",
                ALL_ROLES,
                "/payments/outstanding",
            ),
            item(
                "Pair Ledger",
                "/payments/pair-statement",
                "fa-solid fa-people-arrows",
                ALL_ROLES,
                "/payments/pair-statement",
            ),
        ),
    ),

    MenuGroup(
        label="Marketplace",
        css_class="market-group-header",
        items=(
            item(
                "Marketplace Setup",
                "/marketplace/setup",
                "fa-solid fa-sliders",
                SUPER_ADMIN_ONLY,
                "/marketplace/setup",
            ),
            item(
                "Marketplace",
                "/marketplace",
                "fa-solid fa-store",
                ALL_ROLES,
                "/marketplace",
            ),
        ),
    ),
)


def build_navigation(role: int) -> tuple[MenuGroup, ...]:
    return tuple(
        MenuGroup(
            label=group.label,
            css_class=group.css_class,
            items=tuple(
                menu_item
                for menu_item in group.items
                if role in menu_item.roles
            ),
        )
        for group in ADMIN_NAVIGATION
        if any(role in item.roles for item in group.items)
    )