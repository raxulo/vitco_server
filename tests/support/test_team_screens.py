"""
Teams, members and roles screens (Plan 25.3, REQ-59 to REQ-61, REQ-65) through the real app.
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.support.infrastructure.models import SupportMemberModel, SupportTeamModel
from tests.support.test_foundation import (  # noqa: F401  (fixtures and helpers)
    _digits,
    _make_member,
    _make_team,
    _role_id,
    support,
)


def _redirect(response) -> str | None:
    return response.headers.get("location") if response.status_code in (302, 303, 307) else None


@pytest.fixture
async def super_admin(user_factory, token_for):
    return token_for(await user_factory(Role.SUPER_ADMIN), Role.SUPER_ADMIN)


def _team_form(**overrides) -> dict[str, str]:
    token = uuid4().hex[:6]
    values = {
        "name": f"North Desk {token}", "code": f"N-{token}".upper(), "manager_name": "Nisha Rao",
        "manager_email": f"nisha{token}@quickyee-tests.com", "manager_mobile": _digits(), "manager_password": "Passw0rd!x",
    }
    values.update(overrides)
    return values


# =========================================================
# TEAMS
# =========================================================

async def test_super_admin_creates_a_team_from_the_form(api, super_admin, database, token_for):
    form = _team_form()
    response = await api.post("/support/teams/new", data=form, headers=super_admin, follow_redirects=False)
    location = _redirect(response)
    assert location and location.startswith("/support/teams/") and location.endswith("?notice=created")

    detail = await api.get(location, headers=super_admin)
    assert detail.status_code == 200
    assert form["name"] in detail.text and "Nisha Rao" in detail.text and "Team created." in detail.text
    for template in ("Technical Support", "Ticket Assigner", "Chat Agent", "Caller", "Viewer"):
        assert template in detail.text

    async with database.transaction() as session:
        team = await session.scalar(select(SupportTeamModel).where(SupportTeamModel.code == form["code"]))
    manager = token_for(team.manager_user_id, Role.SUPPORT)
    assert (await api.get("/support", headers=manager)).status_code == 200


async def test_team_form_errors_are_shown_in_place(api, super_admin):
    first = _team_form()
    await api.post("/support/teams/new", data=first, headers=super_admin)

    duplicate = await api.post("/support/teams/new", data=_team_form(code=first["code"]), headers=super_admin)
    assert duplicate.status_code == 422 and "already exists" in duplicate.text
    assert first["code"] in duplicate.text                     # what was typed is kept

    bad_email = await api.post("/support/teams/new", data=_team_form(manager_email="not-an-email"), headers=super_admin)
    assert bad_email.status_code == 422 and "valid email" in bad_email.text

    short = await api.post("/support/teams/new", data=_team_form(manager_password="short"), headers=super_admin)
    assert short.status_code == 422 and "8 characters" in short.text

    mobile = await api.post("/support/teams/new", data=_team_form(manager_mobile="123"), headers=super_admin)
    assert mobile.status_code == 422 and "10 digits" in mobile.text


async def test_team_list_search_edit_and_disable(api, super_admin):
    form = _team_form(name=f"Searchable Desk {uuid4().hex[:4]}")
    location = _redirect(await api.post("/support/teams/new", data=form, headers=super_admin, follow_redirects=False))
    team_url = location.split("?")[0]

    listing = await api.get("/support/teams", params={"q": form["name"]}, headers=super_admin)
    assert form["name"] in listing.text and "Nisha Rao" in listing.text
    nothing = await api.get("/support/teams", params={"q": "no-such-team-xyz"}, headers=super_admin)
    assert "No team matches" in nothing.text

    edited = await api.post(f"{team_url}/edit", data={"name": "Renamed Desk", "code": form["code"]},
                            headers=super_admin, follow_redirects=False)
    assert _redirect(edited) == f"{team_url}?notice=updated"

    disabled = await api.post(f"{team_url}/status", data={"active": "0"}, headers=super_admin, follow_redirects=False)
    assert _redirect(disabled) == f"{team_url}?notice=disabled"
    page = await api.get(team_url, headers=super_admin)
    assert "Renamed Desk" in page.text and "Disabled" in page.text and ">Enable<" in page.text


@pytest.mark.parametrize("path", ["/support/teams", "/support/teams/new"])
async def test_only_super_admin_reaches_team_screens(api, support, token_for, path):
    _, manager = await _make_team(support)
    response = await api.get(path, headers=token_for(manager.id, Role.SUPPORT), follow_redirects=False)
    assert _redirect(response) == "/"
    posted = await api.post("/support/teams/new", data=_team_form(), headers=token_for(manager.id, Role.SUPPORT),
                            follow_redirects=False)
    assert _redirect(posted) == "/"


async def test_dairy_sidebar_links_super_admin_to_technical_support(api, super_admin, user_factory, token_for):
    assert "/support/teams" in (await api.get("/dashboard", headers=super_admin)).text
    admin = token_for(await user_factory(Role.ADMIN), Role.ADMIN)
    assert "/support/teams" not in (await api.get("/dashboard", headers=admin)).text


# =========================================================
# MEMBERS
# =========================================================

async def test_manager_adds_edits_and_disables_a_member(api, support, token_for, database):
    team, manager = await _make_team(support)
    headers = token_for(manager.id, Role.SUPPORT)
    role_id = await _role_id(support, manager, "Ticket Assigner")
    email = f"ravi{uuid4().hex[:6]}@quickyee-tests.com"

    created = await api.post("/support/members/new", headers=headers, follow_redirects=False, data={
        "name": "Ravi Kumar", "email": email, "mobile": _digits(), "password": "Passw0rd!x", "role_id": str(role_id),
    })
    assert _redirect(created) == "/support/members?notice=created"
    listing = await api.get(_redirect(created), headers=headers)
    assert "Ravi Kumar" in listing.text and "Ticket Assigner" in listing.text and "Member created." in listing.text

    async with database.transaction() as session:
        member = await session.scalar(
            select(SupportMemberModel).join(UserModel, UserModel.id == SupportMemberModel.user_id).where(UserModel.email == email)
        )
    edit_page = await api.get(f"/support/members/{member.id}/edit", headers=headers)
    assert edit_page.status_code == 200 and email in edit_page.text

    viewer_role = await _role_id(support, manager, "Viewer")
    saved = await api.post(f"/support/members/{member.id}/edit", headers=headers, follow_redirects=False,
                           data={"name": "Ravi K", "mobile": _digits(), "role_id": str(viewer_role)})
    assert _redirect(saved) == "/support/members?notice=updated"

    off = await api.post(f"/support/members/{member.id}/status", headers=headers, data={"active": "0"},
                         follow_redirects=False)
    assert _redirect(off) == "/support/members?notice=disabled"
    async with database.transaction() as session:
        assert (await session.get(UserModel, member.user_id)).is_active is False


async def test_member_form_keeps_input_and_shows_the_error(api, support, token_for):
    _, manager = await _make_team(support)
    headers = token_for(manager.id, Role.SUPPORT)
    response = await api.post("/support/members/new", headers=headers, data={
        "name": "Asha Verma", "email": f"asha{uuid4().hex[:6]}@quickyee-tests.com", "mobile": _digits(),
        "password": "Passw0rd!x", "role_id": "",
    })
    assert response.status_code == 422 and "Choose a role" in response.text and "Asha Verma" in response.text


async def test_members_screens_respect_permissions_and_team(api, support, token_for):
    _, manager = await _make_team(support)
    _, other_manager = await _make_team(support)
    viewer, viewer_actor = await _make_member(support, manager, "Viewer")
    other_member, _ = await _make_member(support, other_manager)

    viewer_headers = token_for(viewer_actor.id, Role.SUPPORT)
    assert _redirect(await api.get("/support/members", headers=viewer_headers, follow_redirects=False)) == "/"
    assert _redirect(await api.get("/support/roles", headers=viewer_headers, follow_redirects=False)) == "/"

    headers = token_for(manager.id, Role.SUPPORT)
    foreign = await api.get(f"/support/members/{other_member.id}/edit", headers=headers, follow_redirects=False)
    assert _redirect(foreign) == "/support/members"
    refused = await api.post(f"/support/members/{other_member.id}/status", headers=headers, data={"active": "0"},
                             follow_redirects=False)
    assert _redirect(refused) == "/support/members?notice=missing"


async def test_manager_row_cannot_be_disabled_from_the_screen(api, support, token_for):
    _, manager = await _make_team(support)
    headers = token_for(manager.id, Role.SUPPORT)
    listing = await api.get("/support/members", headers=headers)
    assert "(you)" in listing.text and "Disable" not in listing.text


async def test_super_admin_manages_members_inside_a_named_team(api, support, super_admin):
    team, manager = await _make_team(support)
    listing = await api.get("/support/members", params={"team": str(team.id)}, headers=super_admin)
    assert listing.status_code == 200 and team.name in listing.text
    # Without a team there is nothing to show
    assert _redirect(await api.get("/support/members", headers=super_admin, follow_redirects=False)) == "/"


# =========================================================
# ROLES
# =========================================================

async def test_manager_creates_and_edits_a_role(api, support, token_for):
    _, manager = await _make_team(support)
    headers = token_for(manager.id, Role.SUPPORT)

    page = await api.get("/support/roles/new", headers=headers)
    assert page.status_code == 200 and "support.ticket.reply" in page.text
    assert "support.team.manage" not in page.text               # never offered to a team role

    created = await api.post("/support/roles/new", headers=headers, follow_redirects=False,
                             data={"name": "Senior Resolver", "permissions": ["support.ticket.reply", "support.ticket.resolve"]})
    assert _redirect(created) == "/support/roles?notice=created"
    listing = await api.get("/support/roles", headers=headers)
    assert "Senior Resolver" in listing.text and "Custom" in listing.text

    role_id = await _role_id(support, manager, "Senior Resolver")
    edit = await api.get(f"/support/roles/{role_id}/edit", headers=headers)
    assert 'value="support.ticket.resolve" checked' in edit.text

    sneaky = await api.post(f"/support/roles/{role_id}/edit", headers=headers,
                            data={"name": "Senior Resolver", "permissions": ["support.team.manage"]})
    assert sneaky.status_code == 422 and "cannot be given" in sneaky.text

    duplicate = await api.post("/support/roles/new", headers=headers, data={"name": "viewer", "permissions": []})
    assert duplicate.status_code == 422 and "already has a role" in duplicate.text
