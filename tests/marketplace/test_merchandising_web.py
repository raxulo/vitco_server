"""Banners, home page and settings pages through the real app."""

from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.infrastructure.models import MarketplaceCategoryModel
from tests.dataexchange.factories import create_user

BASE = "/admin/marketplace"
HTML = {"accept": "text/html"}


def _image(field: str = "image"):
    buffer = BytesIO()
    Image.new("RGB", (64, 48), (200, 120, 40)).save(buffer, format="JPEG")
    return (field, ("banner.jpg", buffer.getvalue(), "image/jpeg"))


@pytest.fixture
async def headers(database, token_for) -> dict[str, str]:
    return token_for(await create_user(database, role=Role.SUPER_ADMIN), Role.SUPER_ADMIN) | HTML


@pytest.mark.parametrize("path", ["/banners", "/home", "/settings"])
async def test_guest_goes_to_login(api, path):
    response = await api.get(f"{BASE}{path}", headers=HTML, follow_redirects=False)
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.VLCC, Role.FARMER])
@pytest.mark.parametrize(
    ("method", "path"),
    [("get", "/banners"), ("get", "/home"), ("get", "/settings"), ("post", "/settings"), ("post", "/banners"), ("post", "/trending")],
)
async def test_other_roles_are_refused(api, database, token_for, role, method, path):
    other = token_for(await create_user(database, role=role), role) | HTML
    response = await getattr(api, method)(f"{BASE}{path}", headers=other)
    assert response.status_code == 403


async def test_banner_add_shows_state_edit_and_delete(api, headers):
    title = f"Festive {uuid4().hex[:8]}"
    created = await api.post(
        f"{BASE}/banners", data={"title": title, "placement": "HOME_HERO", "is_active": "on", "starts_at": "2099-01-01T10:30"},
        files=[_image()], headers=headers, follow_redirects=False,
    )
    assert created.status_code == 303

    page = (await api.get(f"{BASE}/banners", headers=headers)).text
    assert title in page and "Scheduled" in page and "01 Jan 2099, 10:30 AM" in page

    banner_id = page[page.index(title):].split("?edit=")[1].split('"')[0]  # the row's actions come after the title

    edit = (await api.get(f"{BASE}/banners", params={"edit": banner_id}, headers=headers)).text
    assert 'value="2099-01-01T10:30"' in edit and "Save changes" in edit

    deleted = await api.post(f"{BASE}/banners/{banner_id}/delete", headers=headers, follow_redirects=False)
    assert deleted.status_code == 303
    assert title not in (await api.get(f"{BASE}/banners", headers=headers)).text


async def test_invalid_banner_keeps_values_and_refuses_javascript_link(api, headers):
    response = await api.post(
        f"{BASE}/banners",
        data={"title": "Kept title", "cta_label": "Go", "cta_url": "javascript:alert(1)", "is_active": "on"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "Kept title" in response.text
    assert "Use a site path" in response.text
    assert "Choose a banner image." in response.text


async def test_home_sections_move_edit_and_built_in_delete_refused(api, headers):
    page = (await api.get(f"{BASE}/home", headers=headers)).text
    first_id = page.split("/home-sections/")[1].split("/")[0]

    assert (await api.post(f"{BASE}/home-sections/{first_id}/move", data={"direction": "down"}, headers=headers, follow_redirects=False)).status_code == 303

    after = (await api.get(f"{BASE}/home", headers=headers)).text
    assert after.split("/home-sections/")[1].split("/")[0] != first_id

    refused = await api.post(f"{BASE}/home-sections/{first_id}/delete", headers=headers)
    assert refused.status_code == 409
    assert "can be hidden but not deleted" in refused.text

    hidden = await api.post(f"{BASE}/home-sections", data={"id": first_id, "title": "Renamed section", "item_limit": "6"}, headers=headers, follow_redirects=False)
    assert hidden.status_code == 303
    page = (await api.get(f"{BASE}/home", headers=headers)).text
    assert "Renamed section" in page and "Hidden" in page


async def test_category_section_can_be_added_and_deleted(api, database, headers):
    category_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=category_id, name=f"Paneer {category_id.hex[:6]}", slug=f"p-{category_id.hex}"))

    missing = await api.post(f"{BASE}/home-sections", data={"title": "No category", "item_limit": "8"}, headers=headers)
    assert missing.status_code == 422
    assert "Choose a category." in missing.text and "No category" in missing.text

    title = f"Paneer picks {uuid4().hex[:6]}"
    added = await api.post(f"{BASE}/home-sections", data={"title": title, "category_id": str(category_id), "item_limit": "4", "is_visible": "on"}, headers=headers, follow_redirects=False)
    assert added.status_code == 303

    page = (await api.get(f"{BASE}/home", headers=headers)).text
    section_id = page[page.index(title):].split("/home-sections/")[1].split("/")[0]
    assert (await api.post(f"{BASE}/home-sections/{section_id}/delete", headers=headers, follow_redirects=False)).status_code == 303
    assert title not in (await api.get(f"{BASE}/home", headers=headers)).text


async def test_trending_link_round_trip_and_unsafe_link(api, headers):
    bad = await api.post(f"{BASE}/trending", data={"label": "Bad", "url": "javascript:alert(1)"}, headers=headers)
    assert bad.status_code == 422
    assert "Use a site path" in bad.text

    label = f"Gir {uuid4().hex[:8]}"
    assert (await api.post(f"{BASE}/trending", data={"label": label, "url": "/marketplace/animals", "is_active": "on"}, headers=headers, follow_redirects=False)).status_code == 303
    assert label in (await api.get(f"{BASE}/home", headers=headers)).text


async def test_settings_save_and_reload(api, headers):
    name = f"Store {uuid4().hex[:6]}"
    response = await api.post(
        f"{BASE}/settings",
        data={
            "store_name": name, "support_phone": "9876543210", "whatsapp_number": "919876543210", "delivery_charge": "40",
            "free_delivery_above": "500", "min_order_amount": "100", "pincodes_text": "302001, 302002\n302003",
            "cod_enabled": "on", "is_store_open": "on", "policy_returns": "Seven days",
        },
        files=[_image("logo")], headers=headers, follow_redirects=False,
    )
    assert response.status_code == 303

    page = (await api.get(f"{BASE}/settings", headers=headers)).text
    assert name in page
    assert "302001, 302002, 302003" in page
    assert "Seven days" in page
    assert "/api/v1/media/banner/" in page


async def test_invalid_settings_keep_what_was_typed(api, headers):
    response = await api.post(
        f"{BASE}/settings",
        data={"store_name": "Typed name", "support_phone": "123", "pincodes_text": "302001 99", "delivery_charge": "abc", "policy_terms": "Typed terms"},
        headers=headers,
    )
    assert response.status_code == 422
    assert "Enter a valid number." in response.text

    domain = await api.post(
        f"{BASE}/settings",
        data={"store_name": "Typed name", "support_phone": "123", "pincodes_text": "302001 99", "policy_terms": "Typed terms"},
        headers=headers,
    )
    assert domain.status_code == 422
    for text in ("Typed name", "must have 10 to 15 digits", "Check: 99", "Typed terms", "302001 99"):
        assert text in domain.text
