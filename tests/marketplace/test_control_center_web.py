"""Control Center through the real app: middleware, routes, templates, real files."""

from decimal import Decimal
from io import BytesIO
from uuid import uuid4

import pytest
from PIL import Image
from sqlalchemy import select, update

from app.modules.administration.domain.enums import Role
from app.modules.dashboard.presentation.navigation import build_navigation
from app.modules.marketplace.domain.enums import AnimalStatus, ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)
from app.web.framework.formatting import inr
from tests.dataexchange.factories import create_user

BASE = "/admin/marketplace"
HTML = {"accept": "text/html"}


def _jpeg() -> bytes:
    buffer = BytesIO()
    Image.new("RGB", (64, 48), (200, 120, 40)).save(buffer, format="JPEG")
    return buffer.getvalue()


def _image(name: str = "a.jpg", data: bytes | None = None):
    return ("new_images", (name, _jpeg() if data is None else data, "image/jpeg"))


@pytest.fixture
async def admin_headers(database, token_for) -> dict[str, str]:
    user_id = await create_user(database, role=Role.SUPER_ADMIN)
    return token_for(user_id, Role.SUPER_ADMIN) | HTML


@pytest.fixture
async def category_id(database) -> str:
    row_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=row_id, name=f"Ghee {row_id.hex[:6]}", slug=f"ghee-{row_id.hex}"))
    return str(row_id)


@pytest.fixture
async def type_id(database) -> str:
    row_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceAnimalTypeModel(id=row_id, name=f"Cow {row_id.hex}", slug=f"cow-{row_id.hex}"))
    return str(row_id)


def _product_form(category_id: str, title: str, **overrides) -> dict:
    return {
        "title": title, "category_id": category_id, "status": "DRAFT",
        "variant_id": [""], "variant_row": ["0"], "variant_default": "0", "variant_name": ["1 L"], "variant_sku": [""],
        "variant_mrp": ["600"], "variant_price": ["550"], "variant_stock": ["7"], "variant_low_stock": ["5"],
        "variant_active": ["1"],
    } | overrides


async def _product_by_title(database, title: str) -> MarketplaceProductModel | None:
    async with database.transaction() as session:
        return await session.scalar(select(MarketplaceProductModel).where(MarketplaceProductModel.title == title))


# =========================================================
# ACCESS
# =========================================================


@pytest.mark.parametrize(
    "path", ["", "/products", "/products/new", "/animals", "/animals/new", "/categories", "/animal-types"]
)
async def test_access_guest_goes_to_login(api, path):
    response = await api.get(f"{BASE}{path}", headers=HTML, follow_redirects=False)
    assert response.status_code in (302, 303)
    assert response.headers["location"] == "/login"


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER])
@pytest.mark.parametrize("path", ["", "/products", "/categories"])
async def test_access_other_roles_are_refused(api, database, token_for, role, path):
    headers = token_for(await create_user(database, role=role), role) | HTML
    assert (await api.get(f"{BASE}{path}", headers=headers)).status_code == 403


@pytest.mark.parametrize("role", [Role.ADMIN, Role.VLCC])
async def test_access_other_roles_cannot_write(api, database, token_for, category_id, role):
    headers = token_for(await create_user(database, role=role), role) | HTML
    title = f"Hack {uuid4().hex}"

    response = await api.post(f"{BASE}/products/new", data=_product_form(category_id, title), headers=headers)
    delete = await api.post(f"{BASE}/categories/{category_id}/delete", headers=headers)

    assert response.status_code == 403
    assert delete.status_code == 403
    assert await _product_by_title(database, title) is None


@pytest.mark.parametrize(
    ("role", "visible"),
    [(Role.SUPER_ADMIN, True), (Role.ADMIN, False), (Role.SUB_ADMIN, False), (Role.VLCC, False), (Role.FARMER, False)],
)
def test_access_menu_only_for_sellers(role, visible):
    hrefs = [item.href for group in build_navigation(role.value) for item in group.items]
    assert (f"{BASE}" in hrefs) is visible


# =========================================================
# OVERVIEW
# =========================================================


async def test_overview_shows_real_counts_and_is_safe_when_empty(api, database, admin_headers, category_id):
    # The low stock list is short and the test database is shared: restock what other tests left
    async with database.transaction() as session:
        await session.execute(update(MarketplaceProductVariantModel).values(stock=100))
    title = f"Counted {uuid4().hex}"
    before = (await api.get(BASE, headers=admin_headers)).text
    assert "Products live" in before and "Low stock" in before

    response = await api.post(
        f"{BASE}/products/new",
        data=_product_form(category_id, title, status="PUBLISHED", variant_stock=["2"]),
        files=[_image()],
        headers=admin_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303

    page = (await api.get(BASE, headers=admin_headers)).text
    assert title in page  # low stock list
    assert "Needs restocking" in page


# =========================================================
# PRODUCTS
# =========================================================


async def test_product_create_edit_list_and_delete(api, database, admin_headers, category_id):
    title = f"Desi Ghee {uuid4().hex[:8]}"

    created = await api.post(
        f"{BASE}/products/new",
        data=_product_form(category_id, title, spec_label=["Shelf life"], spec_value=["6 months"], is_featured="on"),
        files=[_image()],
        headers=admin_headers,
        follow_redirects=False,
    )
    assert created.status_code == 303
    assert created.headers["location"] == f"{BASE}/products?done=created"

    product = await _product_by_title(database, title)
    assert product.status == ProductStatus.DRAFT
    assert product.is_featured is True
    assert product.specifications == [{"label": "Shelf life", "value": "6 months"}]

    listing = await api.get(f"{BASE}/products", params={"search": title}, headers=admin_headers)
    assert title in listing.text and "₹550" in listing.text

    edit_page = await api.get(f"{BASE}/products/{product.id}", headers=admin_headers)
    assert edit_page.status_code == 200
    assert "Shelf life" in edit_page.text

    deleted = await api.post(f"{BASE}/products/{product.id}/delete", headers=admin_headers, follow_redirects=False)
    assert deleted.status_code == 303
    assert (await api.get(f"{BASE}/products/{product.id}", headers=admin_headers)).status_code == 404


async def test_uploaded_image_is_served_publicly(api, database, admin_headers, category_id):
    title = f"Pic {uuid4().hex}"
    await api.post(
        f"{BASE}/products/new", data=_product_form(category_id, title), files=[_image()], headers=admin_headers
    )
    product = await _product_by_title(database, title)
    edit_page = (await api.get(f"{BASE}/products/{product.id}", headers=admin_headers)).text

    url = edit_page.split('src="/api/v1/media/product/')[1].split('"')[0]
    image = await api.get(f"/api/v1/media/product/{url}")  # no login

    assert image.status_code == 200
    assert image.headers["content-type"] == "image/webp"


async def test_invalid_product_keeps_typed_values_and_names_the_field(api, database, admin_headers, category_id):
    title = f"Bad price {uuid4().hex}"
    response = await api.post(
        f"{BASE}/products/new",
        data=_product_form(category_id, title, brand="My Brand", variant_mrp=["100"], variant_price=["200"]),
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "price cannot be above MRP" in response.text
    assert title in response.text
    assert "My Brand" in response.text
    assert await _product_by_title(database, title) is None


async def test_missing_title_and_not_a_number_get_clear_messages(api, admin_headers, category_id):
    response = await api.post(
        f"{BASE}/products/new",
        data=_product_form(category_id, "", variant_price=["abc"]),
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "This field is required." in response.text
    assert "Size row 1: Enter a valid number." in response.text


async def test_publish_without_image_is_refused_and_chosen_files_are_mentioned(api, admin_headers, category_id):
    response = await api.post(
        f"{BASE}/products/new", data=_product_form(category_id, "No image", status="PUBLISHED"), headers=admin_headers
    )
    assert response.status_code == 422
    assert "Add at least one image before publishing." in response.text

    with_bad_size = await api.post(
        f"{BASE}/products/new",
        data=_product_form(category_id, "Lost file", variant_mrp=["1"], variant_price=["2"]),
        files=[_image()],
        headers=admin_headers,
    )
    assert "Please choose your new images again." in with_bad_size.text


async def test_broken_image_shows_a_message_not_an_error_page(api, admin_headers, category_id):
    response = await api.post(
        f"{BASE}/products/new",
        data=_product_form(category_id, "Broken image"),
        files=[_image("broken.jpg", b"not really an image")],
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "broken.jpg: Invalid image file" in response.text


async def test_blank_size_rows_are_ignored(api, database, admin_headers, category_id):
    title = f"Rows {uuid4().hex}"
    form = _product_form(category_id, title) | {
        "variant_id": ["", ""], "variant_row": ["0", "1"], "variant_name": ["1 L", ""], "variant_sku": ["", ""],
        "variant_mrp": ["600", ""], "variant_price": ["550", ""], "variant_stock": ["7", ""],
        "variant_low_stock": ["5", "5"], "variant_active": ["1", "1"],
    }
    response = await api.post(f"{BASE}/products/new", data=form, headers=admin_headers, follow_redirects=False)
    assert response.status_code == 303

    edit_page = (await api.get(f"{BASE}/products/{(await _product_by_title(database, title)).id}", headers=admin_headers)).text
    assert edit_page.count('name="variant_name"') == 2  # the one saved row plus the add-row template


async def test_edit_page_of_unknown_product_is_404(api, admin_headers):
    assert (await api.get(f"{BASE}/products/{uuid4()}", headers=admin_headers)).status_code == 404
    assert (await api.post(f"{BASE}/products/{uuid4()}/delete", headers=admin_headers)).status_code == 404


async def test_list_filters_by_status_and_escapes_html(api, admin_headers, category_id):
    mark = f"<script>x{uuid4().hex}"
    await api.post(f"{BASE}/products/new", data=_product_form(category_id, mark), headers=admin_headers)

    drafts = await api.get(f"{BASE}/products", params={"status": "DRAFT", "search": mark}, headers=admin_headers)
    published = await api.get(f"{BASE}/products", params={"status": "PUBLISHED", "search": mark}, headers=admin_headers)

    assert "&lt;script&gt;" in drafts.text and mark not in drafts.text.replace('value="', "")
    assert "No products match" in published.text


# =========================================================
# ANIMALS
# =========================================================


async def test_animal_create_with_all_details(api, database, admin_headers, type_id):
    title = f"Gir cow {uuid4().hex[:8]}"
    form = {
        "title": title, "animal_type_id": type_id, "gender": "FEMALE", "status": "PUBLISHED", "price": "85000",
        "is_negotiable": "on", "lactation_number": "2", "milk_litres_per_day": "14.5", "fat_percent": "4.2",
        "pregnancy_status": "PREGNANT", "pregnancy_months": "3", "age_months": "48", "district": "Jaipur",
        "description": "Calm and healthy",
    }
    response = await api.post(
        f"{BASE}/animals/new", data=form, files=[_image()], headers=admin_headers, follow_redirects=False
    )
    assert response.status_code == 303

    async with database.transaction() as session:
        animal = await session.scalar(select(MarketplaceAnimalModel).where(MarketplaceAnimalModel.title == title))
    assert animal.status == AnimalStatus.PUBLISHED
    assert animal.milk_litres_per_day == Decimal("14.50")
    assert animal.lactation_number == 2
    assert animal.is_negotiable is True

    listing = await api.get(f"{BASE}/animals", params={"search": title}, headers=admin_headers)
    assert "₹85,000" in listing.text and "14.5 L" in listing.text

    edit_page = await api.get(f"{BASE}/animals/{animal.id}", headers=admin_headers)
    assert "Calm and healthy" in edit_page.text


async def test_publishing_animal_without_milk_names_those_fields(api, admin_headers, type_id):
    response = await api.post(
        f"{BASE}/animals/new",
        data={"title": "Cow", "animal_type_id": type_id, "gender": "FEMALE", "status": "PUBLISHED", "price": "85000"},
        headers=admin_headers,
    )
    assert response.status_code == 422
    assert "Enter the lactation number" in response.text
    assert "Enter milk litres per day" in response.text


# =========================================================
# MASTERS
# =========================================================


async def test_master_category_add_edit_and_refused_delete(api, database, admin_headers, category_id):
    name = f"Cheese {uuid4().hex[:8]}"
    created = await api.post(
        f"{BASE}/categories", data={"name": name, "is_active": "on"}, headers=admin_headers, follow_redirects=False
    )
    assert created.status_code == 303
    assert name in (await api.get(f"{BASE}/categories", headers=admin_headers)).text

    title = f"Uses category {uuid4().hex}"
    await api.post(f"{BASE}/products/new", data=_product_form(category_id, title), headers=admin_headers)

    refused = await api.post(f"{BASE}/categories/{category_id}/delete", headers=admin_headers)
    assert refused.status_code == 409
    assert "Deactivate it instead" in refused.text

    edit_page = await api.get(f"{BASE}/categories", params={"edit": category_id}, headers=admin_headers)
    assert "Save changes" in edit_page.text


async def test_master_category_without_a_name_is_refused(api, admin_headers):
    response = await api.post(f"{BASE}/categories", data={"name": ""}, headers=admin_headers)
    assert response.status_code == 422
    assert "This field is required." in response.text


async def test_master_animal_type_and_breed(api, admin_headers, type_id):
    breed = f"Sahiwal {uuid4().hex[:6]}"
    response = await api.post(
        f"{BASE}/animal-breeds",
        data={"animal_type_id": type_id, "name": breed, "is_active": "on"},
        headers=admin_headers,
        follow_redirects=False,
    )
    assert response.status_code == 303
    assert breed in (await api.get(f"{BASE}/animal-types", headers=admin_headers)).text

    duplicate = await api.post(
        f"{BASE}/animal-breeds", data={"animal_type_id": type_id, "name": breed.upper()}, headers=admin_headers
    )
    assert duplicate.status_code == 422
    assert "already exists" in duplicate.text

    in_use = await api.post(f"{BASE}/animal-types/{type_id}/delete", headers=admin_headers)
    assert in_use.status_code == 409
    assert "Deactivate it instead" in in_use.text


# =========================================================
# FORMATTING
# =========================================================


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (0, "₹0"),
        (999, "₹999"),
        (1000, "₹1,000"),
        (125000, "₹1,25,000"),
        (12345678, "₹1,23,45,678"),
        (Decimal("85000.50"), "₹85,000.50"),
        (Decimal("-1500"), "-₹1,500"),
        (None, "—"),
        ("abc", "—"),
    ],
)
def test_formatting_inr(value, expected):
    assert inr(value) == expected
