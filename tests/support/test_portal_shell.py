"""
Support portal shell (Plan 25.2, REQ-58, REQ-65, D-13): login redirect, isolation both ways,
the permission-filtered sidebar and the design kit page, through the real app.
"""

from __future__ import annotations

import re

import pytest

from app.modules.administration.domain.enums import Role
from tests.support.test_foundation import (  # noqa: F401  (fixtures and helpers)
    _make_member,
    _make_team,
    support,
)

PASSWORD = "Passw0rd!x"


@pytest.fixture
async def portal(api, support, user_factory, token_for):
    """A team with its manager, a Technical Support member, a Viewer and a Super Admin user."""
    team, manager = await _make_team(support)
    tech, tech_actor = await _make_member(support, manager, "Technical Support")
    viewer, viewer_actor = await _make_member(support, manager, "Viewer")
    super_admin = await user_factory(Role.SUPER_ADMIN)

    def headers(user_id, role=Role.SUPPORT):
        return token_for(user_id, role)

    return type("Portal", (), {
        "team": team,
        "manager": headers(manager.id),
        "tech": headers(tech_actor.id),
        "viewer": headers(viewer_actor.id),
        "super_admin": headers(super_admin, Role.SUPER_ADMIN),
        "headers": staticmethod(headers),
        "user_factory": staticmethod(user_factory),
    })


def _redirects_to(response, location: str) -> bool:
    return response.status_code in (302, 303, 307) and response.headers.get("location") == location


async def _get(api, path, headers=None):
    return await api.get(path, headers=headers or {}, follow_redirects=False)


# =========================================================
# ACCESS AND ISOLATION
# =========================================================

async def test_anonymous_visitors_are_sent_to_the_login_page(api):
    response = await _get(api, "/support")
    assert _redirects_to(response, "/login")


async def test_support_manager_sees_the_portal_with_its_team_and_menus(api, portal):
    response = await _get(api, "/support", portal.manager)
    assert response.status_code == 200
    html = response.text
    assert "sp-sidebar" in html and portal.team.name in html
    assert "Members" in html and "Roles and permissions" in html
    assert "Support teams" not in html                      # Super Admin only
    assert "app.min.css" not in html                        # none of the dairy styling
    assert "Back to dairy panel" not in html


async def test_a_member_only_gets_the_menus_the_role_allows(api, portal):
    html = (await _get(api, "/support", portal.tech)).text
    assert "Dashboard" in html
    assert "Members" not in html and "Roles and permissions" not in html
    assert "Support teams" not in html


async def test_super_admin_gets_the_portal_with_teams_and_a_way_back(api, portal):
    response = await _get(api, "/support", portal.super_admin)
    assert response.status_code == 200
    assert "Support teams" in response.text and "Back to dairy panel" in response.text
    # Members and roles are reached from a team, not from the sidebar
    assert "Roles and permissions" not in response.text


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER, Role.VLCC_FARMER])
async def test_other_roles_cannot_open_the_support_portal(api, portal, role):
    user_id = await portal.user_factory(role)
    response = await _get(api, "/support", portal.headers(user_id, role))
    assert _redirects_to(response, "/")


@pytest.mark.parametrize("path", ["/dashboard", "/mcc", "/sub-admins", "/admin/marketplace", "/reports"])
async def test_support_users_are_kept_out_of_the_dairy_panel(api, portal, path):
    response = await _get(api, path, portal.manager)
    assert _redirects_to(response, "/support")


async def test_support_users_get_403_on_the_dairy_api(api, portal):
    response = await api.get("/api/v1/mcc", headers=portal.manager)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "SUPPORT_ACCESS_ONLY"


async def test_the_home_page_sends_support_staff_to_the_portal(api, portal):
    response = await _get(api, "/", portal.tech)
    assert _redirects_to(response, "/support")


async def test_a_support_user_without_a_team_row_or_a_disabled_one_is_sent_away(api, portal, user_factory, token_for):
    stray = await user_factory(Role.SUPPORT)
    response = await _get(api, "/support", token_for(stray, Role.SUPPORT))
    assert _redirects_to(response, "/")


# =========================================================
# LOGIN
# =========================================================

async def test_web_login_of_a_support_user_lands_on_the_portal(api, support):
    team, _ = await _make_team(support)
    try:
        response = await api.post("/auth/login", data={"email": team.manager_email, "password": "Passw0rd!x"})
    finally:
        api.cookies.clear()             # the session client is shared: do not stay signed in as this manager
    assert response.status_code == 200
    assert response.headers.get("hx-redirect") == "/support"


async def test_support_accounts_cannot_use_the_mobile_login(api, support):
    team, _ = await _make_team(support)
    response = await api.post(
        "/api/v1/auth/login", json={"email": team.manager_email, "password": "Passw0rd!x"},
    )
    assert response.status_code == 401
    # Refused for the role, not because of wrong credentials
    assert "INVALID_CREDENTIALS" not in response.text


# =========================================================
# DESIGN KIT
# =========================================================

async def test_design_kit_is_for_super_admin_only(api, portal):
    ok = await _get(api, "/support/_kit", portal.super_admin)
    assert ok.status_code == 200, ok.headers.get("location")
    for marker in ("sp-btn", "sp-chip", "sp-table", "sp-empty", "sp-skel", "sp-bubble", "sp-timeline", "sp-live"):
        assert marker in ok.text
    denied = await _get(api, "/support/_kit", portal.manager)
    assert _redirects_to(denied, "/")


async def test_the_support_stylesheet_only_uses_its_own_prefix(api):
    css = (await api.get("/static/css/support.css")).text
    assert ".sp-card" in css
    css = re.sub(r"/\*.*?\*/", "", css, flags=re.S)
    selectors = [
        part.strip() for block in css.split("}") for part in block.split("{")[0].split(",") if part.strip()
    ]
    stray = [
        selector for selector in selectors
        if selector
        and not selector.startswith(("/*", "@", "from", "to", ":root", "*", "html", "body", "dialog.sp-dialog"))
        and ".sp-" not in selector and "%" not in selector
    ]
    assert stray == []
