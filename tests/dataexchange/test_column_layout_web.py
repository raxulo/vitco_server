"""
"Excel Column Order" web page (Plan 24.3, REQ-55, REQ-57).

The page uses ColumnLayoutHandler, so the API's permission rules hold here too;
these tests cover the page, its form, the reset and the links to it.
"""

from __future__ import annotations

import json

import pytest

from app.config.settings import settings
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.jwt import JWTService
from app.modules.dashboard.presentation.navigation import build_navigation
from app.modules.dataexchange.domain.sheets import COLLECTION_COLUMN_KEYS
from tests.dataexchange.factories import create_user

PAGE = "/sub-admins/column-layout"
API = "/api/v1/excel/column-layouts/collections"
HTMX = {"HX-Request": "true"}


def _cookies(user_id, role: Role) -> dict[str, str]:
    token = JWTService(secret_key=settings.SECRET_KEY).create_access_token(
        str(user_id), {"role": str(int(role)), "name": "Test"},
    )
    return {"access_token": token}


def _notification(response) -> dict:
    return json.loads(response.headers["HX-Trigger"])["notification"]


@pytest.fixture
async def people(database):
    admin = await create_user(database, role=Role.ADMIN, name="Admin A")
    sub = await create_user(database, role=Role.SUB_ADMIN, created_by=admin, name="Sub Admin S")
    other_admin = await create_user(database, role=Role.ADMIN, name="Admin O")
    other_sub = await create_user(database, role=Role.SUB_ADMIN, created_by=other_admin, name="Sub Admin T")
    return {"admin": admin, "sub": sub, "other_admin": other_admin, "other_sub": other_sub}


async def test_own_page_lists_every_column_in_default_order(api, people):
    response = await api.get(PAGE, cookies=_cookies(people["sub"], Role.SUB_ADMIN))
    assert response.status_code == 200
    html = response.text
    assert "Excel Column Order" in html and "Default order" in html
    positions = [html.index(f'data-key="{key}"') for key in COLLECTION_COLUMN_KEYS]
    assert positions == sorted(positions)
    assert "js/column_layout.js" in html


async def test_saving_the_form_stores_order_and_visibility(api, people):
    cookies = _cookies(people["sub"], Role.SUB_ADMIN)
    keys = list(reversed(COLLECTION_COLUMN_KEYS))
    visible = [key for key in keys if key not in ("time", "clr_value")]

    response = await api.post(PAGE, data={"key": keys, "visible": visible}, cookies=cookies, headers=HTMX)
    assert response.status_code == 200
    assert _notification(response)["type"] == "success"

    stored = (await api.get(API, cookies=cookies)).json()["data"]
    assert [column["key"] for column in stored["columns"]] == keys
    assert {column["key"] for column in stored["columns"] if not column["visible"]} == {"time", "clr_value"}
    assert "Custom order" in (await api.get(PAGE, cookies=cookies)).text


async def test_a_save_that_hides_everything_is_refused(api, people):
    cookies = _cookies(people["sub"], Role.SUB_ADMIN)
    response = await api.post(PAGE, data={"key": list(COLLECTION_COLUMN_KEYS)}, cookies=cookies, headers=HTMX)
    assert response.status_code == 422
    assert _notification(response)["type"] == "error"
    assert (await api.get(API, cookies=cookies)).json()["data"]["is_default"] is True


async def test_reset_goes_back_to_the_default(api, people):
    cookies = _cookies(people["admin"], Role.ADMIN)
    target = {"user_id": str(people["sub"])}
    await api.post(PAGE, params=target, data={"key": list(reversed(COLLECTION_COLUMN_KEYS)),
                                              "visible": list(COLLECTION_COLUMN_KEYS)}, cookies=cookies, headers=HTMX)

    response = await api.post(f"{PAGE}/reset", params=target, cookies=cookies, headers=HTMX)
    assert response.status_code < 400
    assert f"user_id={people['sub']}" in response.headers.get("HX-Redirect", "")
    stored = (await api.get(API, params=target, cookies=cookies)).json()["data"]
    assert stored["is_default"] is True


@pytest.mark.parametrize(("actor", "role", "target", "status"), [
    ("admin", Role.ADMIN, "sub", 200),
    ("admin", Role.ADMIN, "other_sub", 404),
    ("sub", Role.SUB_ADMIN, "admin", 404),
    ("other_admin", Role.ADMIN, "sub", 404),
])
async def test_another_users_page_follows_the_edit_rules(api, people, actor, role, target, status):
    cookies = _cookies(people[actor], role)
    params = {"user_id": str(people[target])}
    page = await api.get(PAGE, params=params, cookies=cookies)
    assert page.status_code == status
    if status == 200:
        assert "Sub Admin S" in page.text
    saved = await api.post(PAGE, params=params, data={"key": list(COLLECTION_COLUMN_KEYS),
                                                      "visible": list(COLLECTION_COLUMN_KEYS)},
                           cookies=cookies, headers=HTMX)
    assert saved.status_code == status


@pytest.mark.parametrize("role", [Role.MCC, Role.VLCC, Role.FARMER])
async def test_centres_and_farmers_cannot_open_the_page(api, database, role):
    user = await create_user(database, role=role)
    assert (await api.get(PAGE, cookies=_cookies(user, role))).status_code == 403


async def test_links_on_the_profile_list_and_view_pages(api, people):
    admin = _cookies(people["admin"], Role.ADMIN)

    profile = await api.get("/profile", cookies=admin)
    assert profile.status_code == 200 and f'href="{PAGE}"' in profile.text

    listing = await api.get("/sub-admins", cookies=admin)
    assert f"{PAGE}?user_id={people['sub']}" in listing.text

    view = await api.get(f"/sub-admins/view/{people['sub']}", cookies=admin)
    assert view.status_code == 200 and f"{PAGE}?user_id={people['sub']}" in view.text


def _setup_items(role: Role) -> dict[str, str]:
    return {item.label: item.href for group in build_navigation(int(role))
            if group.label == "System Setup" for item in group.items}


@pytest.mark.parametrize("role", [Role.SUPER_ADMIN, Role.ADMIN, Role.SUB_ADMIN])
def test_excel_maps_is_in_system_setup_for_managers(role):
    assert _setup_items(role).get("Excel Maps") == PAGE


@pytest.mark.parametrize("role", [Role.MCC, Role.VLCC, Role.FARMER, Role.VLCC_FARMER])
def test_excel_maps_is_not_shown_to_centres_or_farmers(role):
    assert "Excel Maps" not in _setup_items(role)


async def test_sidebar_links_to_the_page(api, people):
    page = await api.get(PAGE, cookies=_cookies(people["sub"], Role.SUB_ADMIN))
    assert f'href="{PAGE}" class="menu-item active" data-match="{PAGE}"' in page.text
    assert "Back</a>" not in page.text  # own order: a sidebar page, no Back button


async def test_sidebar_renders_the_current_section_open(api, people):
    """The current page's section is open in the HTML itself, so it does not animate open on load."""
    html = (await api.get(PAGE, cookies=_cookies(people["sub"], Role.SUB_ADMIN))).text
    assert 'class="menu-group config-group expanded"' in html
    assert 'class="menu-group mcc-group"' in html  # other sections stay closed
    assert html.count("menu-item active") == 1
