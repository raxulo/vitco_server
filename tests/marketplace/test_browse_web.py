"""Store pages and the enquiry inbox through the real app."""

import re
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import AnimalStatus, EnquiryStatus, HomeSectionType, ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalImageModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceEnquiryModel,
    MarketplaceHomeSectionModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
)
from tests.dataexchange.factories import create_user

HTML = {"accept": "text/html"}


@pytest.fixture
async def seller(database) -> UUID:
    return await create_user(database, role=Role.SUPER_ADMIN)


@pytest.fixture
async def admin_headers(seller, token_for) -> dict[str, str]:
    return token_for(seller, Role.SUPER_ADMIN) | HTML


@pytest.fixture
async def contacts(database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(
            store_name="Shop", support_phone="9876543210", whatsapp_number="919876543210",
            policies={"returns": "Seven days to return."},
        ))


async def _category(database, name: str | None = None) -> tuple[UUID, str]:
    row_id = uuid4()
    slug = f"c-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=row_id, name=name or f"Cat {row_id.hex[:6]}", slug=slug))
    return row_id, slug


async def _product(database, seller: UUID, category: UUID, title: str, **fields) -> str:
    row_id = uuid4()
    slug = f"p-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceProductModel(**({
            "id": row_id, "seller_user_id": seller, "category_id": category, "title": title, "slug": slug,
            "status": ProductStatus.PUBLISHED,
        } | fields)))
        await session.flush()
        session.add(MarketplaceProductVariantModel(product_id=row_id, name="1 L", mrp=Decimal("800"), price=Decimal("600"), stock=40, is_default=True, sort_order=0))
        session.add(MarketplaceProductVariantModel(product_id=row_id, name="500 ml", mrp=Decimal("400"), price=Decimal("400"), stock=2, sort_order=1))
        session.add(MarketplaceProductImageModel(product_id=row_id, url=f"/media/{row_id.hex}.webp", sort_order=0))
        session.add(MarketplaceProductImageModel(product_id=row_id, url=f"/media/{row_id.hex}-2.webp", sort_order=1))
    return slug


async def _animal_type(database) -> tuple[UUID, str]:
    row_id = uuid4()
    slug = f"t-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceAnimalTypeModel(id=row_id, name=f"Cow {row_id.hex}", slug=slug))
    return row_id, slug


async def _animal(database, seller: UUID, type_id: UUID, title: str, **fields) -> str:
    row_id = uuid4()
    slug = f"a-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceAnimalModel(**({
            "id": row_id, "seller_user_id": seller, "animal_type_id": type_id, "title": title, "slug": slug,
            "price": Decimal("85000"), "status": AnimalStatus.PUBLISHED,
        } | fields)))
        await session.flush()
        session.add(MarketplaceAnimalImageModel(animal_id=row_id, url=f"/media/{row_id.hex}.webp"))
    return slug


# =========================================================
# LISTINGS
# =========================================================


async def test_product_listing_filters_through_the_url(api, database, seller):
    mark = uuid4().hex[:10]
    category, slug = await _category(database, f"Ghee {mark}")
    other, _ = await _category(database)
    await _product(database, seller, category, f"In category {mark}")
    await _product(database, seller, other, f"Elsewhere {mark}")

    page = (await api.get("/marketplace/products", params={"search": mark, "category": slug}, headers=HTML)).text

    assert f"In category {mark}" in page and f"Elsewhere {mark}" not in page
    assert f"Ghee {mark}" in page  # the heading names the category
    assert "1 product" in page and "Clear all filters" in page


async def test_animal_listing_shows_breeds_only_after_choosing_a_type(api, database, seller):
    mark = uuid4().hex[:10]
    type_id, type_slug = await _animal_type(database)
    breed_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceAnimalBreedModel(id=breed_id, animal_type_id=type_id, name=f"Gir{mark}"))
    await _animal(database, seller, type_id, f"With breed {mark}", breed_id=breed_id, milk_litres_per_day=Decimal("14.5"), lactation_number=2)
    await _animal(database, seller, type_id, f"No breed {mark}")

    assert 'name="breed"' not in (await api.get("/marketplace/animals", params={"search": mark}, headers=HTML)).text

    page = (await api.get("/marketplace/animals", params={"search": mark, "type": type_slug, "breed": str(breed_id)}, headers=HTML)).text
    assert 'name="breed"' in page and f"Gir{mark}" in page
    assert f"With breed {mark}" in page and f"No breed {mark}" not in page
    assert "14.5 L" in page and "₹85,000" in page


@pytest.mark.parametrize("url", ["/marketplace/products", "/marketplace/animals"])
@pytest.mark.parametrize(
    "junk",
    [
        {"page": "abc"}, {"page": "-5"}, {"page": "99999999999999999999"}, {"min_price": "abc"}, {"max_price": "NaN"},
        {"min_price": "Infinity"}, {"max_price": "1e999"}, {"min_price": "-1"}, {"sort": "'; DROP TABLE users;--"},
        {"category": "no-such"}, {"type": "no-such"}, {"breed": "not-a-uuid"}, {"breed": str(uuid4())},
        {"lactation": "x"}, {"min_milk": "abc"}, {"search": "%' OR 1=1 --"}, {"search": "x" * 5000}, {"in_stock": "maybe"},
    ],
    ids=lambda value: next(iter(value)) + "=" + str(next(iter(value.values())))[:12],
)
async def test_bad_query_values_never_break_a_listing(api, url, junk):
    assert (await api.get(url, params=junk, headers=HTML)).status_code == 200


async def test_pager_keeps_filters(api, database, seller):
    mark = uuid4().hex[:10]
    category, _ = await _category(database)
    for number in range(25):
        await _product(database, seller, category, f"{number} {mark}")

    first = (await api.get("/marketplace/products", params={"search": mark, "sort": "price_asc"}, headers=HTML)).text
    assert "Page 1 of 2" in first
    next_link = re.search(r'rel="next" href="([^"]+)"', first).group(1).replace("&amp;", "&")
    assert f"search={mark}" in next_link and "sort=price_asc" in next_link

    second = (await api.get(next_link, headers=HTML)).text
    assert "Page 2 of 2" in second


async def test_empty_results_offer_a_way_out(api):
    page = (await api.get("/marketplace/animals", params={"search": uuid4().hex}, headers=HTML)).text
    assert "No animals found" in page and "Clear all filters" in page


# =========================================================
# DETAILS
# =========================================================


async def test_product_detail_shows_sizes_prices_and_specs(api, database, seller):
    category, _ = await _category(database)
    title = f"Ghee {uuid4().hex[:8]}"
    slug = await _product(database, seller, category, title, description="Slow cooked.", specifications=[{"label": "Shelf life", "value": "6 months"}])
    await _product(database, seller, category, "Related item")

    page = (await api.get(f"/marketplace/products/{slug}", headers=HTML)).text

    for text in (title, "₹600", "25% off", "1 L", "500 ml", "Slow cooked.", "Shelf life", "6 months", "In stock", "Only 2 left", "You may also like"):
        assert text in page, text
    assert page.count("<h1") == 1


async def test_animal_detail_has_everything_buyers_asked_for(api, database, seller, contacts):
    type_id, _ = await _animal_type(database)
    title = f"Gir {uuid4().hex[:8]}"
    slug = await _animal(
        database, seller, type_id, title, lactation_number=2, milk_litres_per_day=Decimal("14.5"), age_months=48,
        is_negotiable=True, description="Calm and healthy.", health_notes="Vet checked.", vaccination_notes="FMD done.", district="Jaipur",
    )

    page = (await api.get(f"/marketplace/animals/{slug}", headers=HTML)).text

    for text in (title, "₹85,000", "Negotiable", "14.5 litres", "4 yrs", "Calm and healthy.", "Vet checked.", "FMD done.", "Jaipur",
                 'href="tel:9876543210"', "https://wa.me/919876543210?text=Hello", "Send enquiry"):
        assert text in page, text
    assert "/marketplace/cart/add" not in page  # DECISION-017


async def test_whatsapp_message_is_url_encoded(api, database, seller, contacts):
    type_id, _ = await _animal_type(database)
    slug = await _animal(database, seller, type_id, 'Cow & "calf" <b>')
    page = (await api.get(f"/marketplace/animals/{slug}", headers=HTML)).text

    link = re.search(r'href="(https://wa\.me/[^"]+)"', page).group(1)
    assert " " not in link and "<" not in link and '"' not in link
    assert "<b>" not in page


async def test_sold_animal_has_no_contact_or_form(api, database, seller, contacts):
    type_id, _ = await _animal_type(database)
    slug = await _animal(database, seller, type_id, "Sold cow", status=AnimalStatus.SOLD)

    page = (await api.get(f"/marketplace/animals/{slug}", headers=HTML)).text

    assert "has been sold" in page
    assert "Send enquiry" not in page and "tel:" not in page.split("st-footer")[0]


@pytest.mark.parametrize("path", ["products", "animals"])
async def test_unknown_listing_is_a_store_404(api, path):
    response = await api.get(f"/marketplace/{path}/nope", headers=HTML)
    assert response.status_code == 404
    assert "We could not find that" in response.text and "css/store.css" in response.text


async def test_draft_listing_is_404_even_with_the_link(api, database, seller):
    category, _ = await _category(database)
    type_id, _ = await _animal_type(database)
    product = await _product(database, seller, category, "Draft", status=ProductStatus.DRAFT)
    animal = await _animal(database, seller, type_id, "Draft", status=AnimalStatus.DRAFT)
    assert (await api.get(f"/marketplace/products/{product}", headers=HTML)).status_code == 404
    assert (await api.get(f"/marketplace/animals/{animal}", headers=HTML)).status_code == 404


# =========================================================
# ENQUIRY FORM
# =========================================================


async def _saved(database, slug: str) -> list[MarketplaceEnquiryModel]:
    async with database.transaction() as session:
        animal_id = await session.scalar(select(MarketplaceAnimalModel.id).where(MarketplaceAnimalModel.slug == slug))
        return list(await session.scalars(select(MarketplaceEnquiryModel).where(MarketplaceEnquiryModel.animal_id == animal_id)))


async def test_guest_enquiry_then_thank_you(api, database, seller):
    type_id, _ = await _animal_type(database)
    slug = await _animal(database, seller, type_id, "Gir")

    sent = await api.post(f"/marketplace/animals/{slug}/enquiry", data={"buyer_name": "Asha", "buyer_phone": "98765 43210", "message": "Is she calm?"}, headers=HTML, follow_redirects=False)
    assert sent.status_code == 303

    thanks = (await api.get(sent.headers["location"], headers=HTML)).text
    assert "The seller will call you soon" in thanks and "Send enquiry" not in thanks

    saved = await _saved(database, slug)
    assert [(item.buyer_name, item.buyer_phone, item.message) for item in saved] == [("Asha", "9876543210", "Is she calm?")]


async def test_invalid_enquiry_keeps_what_was_typed(api, database, seller):
    type_id, _ = await _animal_type(database)
    slug = await _animal(database, seller, type_id, "Gir")

    response = await api.post(f"/marketplace/animals/{slug}/enquiry", data={"buyer_name": "Asha", "buyer_phone": "123", "message": "Typed text"}, headers=HTML)

    assert response.status_code == 422
    assert "10 digit mobile number" in response.text
    assert "Asha" in response.text and "Typed text" in response.text
    assert await _saved(database, slug) == []


async def test_missing_fields_and_overlong_message_are_refused(api, database, seller):
    type_id, _ = await _animal_type(database)
    slug = await _animal(database, seller, type_id, "Gir")
    assert (await api.post(f"/marketplace/animals/{slug}/enquiry", data={}, headers=HTML)).status_code == 422
    long = await api.post(f"/marketplace/animals/{slug}/enquiry", data={"buyer_name": "Asha", "buyer_phone": "9876543210", "message": "x" * 1001}, headers=HTML)
    assert long.status_code == 422
    assert await _saved(database, slug) == []


async def test_honeypot_looks_like_success_and_saves_nothing(api, database, seller):
    type_id, _ = await _animal_type(database)
    slug = await _animal(database, seller, type_id, "Gir")

    response = await api.post(f"/marketplace/animals/{slug}/enquiry", data={"buyer_name": "Bot", "buyer_phone": "9876543210", "website": "http://spam"}, headers=HTML, follow_redirects=False)

    assert response.status_code == 303
    assert await _saved(database, slug) == []


async def test_enquiry_for_sold_and_unknown_animals(api, database, seller):
    type_id, _ = await _animal_type(database)
    sold = await _animal(database, seller, type_id, "Sold", status=AnimalStatus.SOLD)
    form = {"buyer_name": "Asha", "buyer_phone": "9876543210"}

    assert (await api.post(f"/marketplace/animals/{sold}/enquiry", data=form, headers=HTML)).status_code == 422
    assert await _saved(database, sold) == []
    assert (await api.post("/marketplace/animals/nope/enquiry", data=form, headers=HTML)).status_code == 404


# =========================================================
# SEARCH, POLICIES, LINKS
# =========================================================


async def test_search_finds_animals_and_products(api, database, seller):
    mark = uuid4().hex[:10]
    category, _ = await _category(database)
    type_id, _ = await _animal_type(database)
    await _product(database, seller, category, f"Product {mark}")
    await _animal(database, seller, type_id, f"Animal {mark}")

    page = (await api.get("/marketplace/search", params={"q": mark}, headers=HTML)).text

    assert f"Product {mark}" in page and f"Animal {mark}" in page
    assert "1 animal and 1 product" in page
    assert f'value="{mark}"' in page  # the search box keeps the words


async def test_search_with_nothing_and_with_no_results(api):
    blank = await api.get("/marketplace/search", params={"q": "  "}, headers=HTML, follow_redirects=False)
    assert blank.headers["location"] == "/marketplace"
    assert "Nothing found" in (await api.get("/marketplace/search", params={"q": uuid4().hex}, headers=HTML)).text


async def test_policy_pages(api, contacts):
    assert "Seven days to return." in (await api.get("/marketplace/policies/returns", headers=HTML)).text
    assert (await api.get("/marketplace/policies/terms", headers=HTML)).status_code == 404  # not written yet
    assert (await api.get("/marketplace/policies/hack", headers=HTML)).status_code == 404


async def test_every_link_on_the_home_page_opens(api, database, seller, contacts):
    category, _ = await _category(database)
    type_id, _ = await _animal_type(database)
    await _product(database, seller, category, "Linked", is_featured=True)
    await _animal(database, seller, type_id, "Linked", is_featured=True)
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceHomeSectionModel))
        for order, kind in enumerate((HomeSectionType.CATEGORIES, HomeSectionType.FEATURED_ANIMALS, HomeSectionType.FEATURED_PRODUCTS)):
            session.add(MarketplaceHomeSectionModel(section_type=kind, title=kind.value, sort_order=order))

    page = (await api.get("/marketplace", headers=HTML)).text
    links = {link.replace("&amp;", "&") for link in re.findall(r'href="(/[^"]*)"', page)} - {"/login"}

    assert len(links) > 8
    for link in links:
        assert (await api.get(link, headers=HTML)).status_code == 200, link


# =========================================================
# INBOX
# =========================================================


async def test_customer_enquiry_reaches_the_inbox_and_can_be_closed(api, database, seller, admin_headers):
    type_id, _ = await _animal_type(database)
    title = f"Gir {uuid4().hex[:8]}"
    slug = await _animal(database, seller, type_id, title)
    await api.post(f"/marketplace/animals/{slug}/enquiry", data={"buyer_name": "Asha", "buyer_phone": "9876543210", "location": "Jaipur"}, headers=HTML)

    page = (await api.get("/admin/marketplace/enquiries", params={"search": title}, headers=admin_headers)).text
    assert title in page and "Asha" in page and "Jaipur" in page
    assert 'href="tel:9876543210"' in page and "wa.me/919876543210" in page

    enquiry_id = (await _saved(database, slug))[0].id
    saved = await api.post(f"/admin/marketplace/enquiries/{enquiry_id}", data={"status": "CLOSED", "admin_notes": "Sold to her"}, headers=admin_headers, follow_redirects=False)
    assert saved.status_code == 303

    item = (await _saved(database, slug))[0]
    assert (item.status, item.admin_notes) == (EnquiryStatus.CLOSED, "Sold to her")
    assert "No enquiries match" in (await api.get("/admin/marketplace/enquiries", params={"search": title, "status": "NEW"}, headers=admin_headers)).text


async def test_bad_status_changes_nothing(api, database, seller, admin_headers):
    type_id, _ = await _animal_type(database)
    slug = await _animal(database, seller, type_id, "Gir")
    await api.post(f"/marketplace/animals/{slug}/enquiry", data={"buyer_name": "Asha", "buyer_phone": "9876543210"}, headers=HTML)
    enquiry_id = (await _saved(database, slug))[0].id

    await api.post(f"/admin/marketplace/enquiries/{enquiry_id}", data={"status": "HACKED"}, headers=admin_headers)

    assert (await _saved(database, slug))[0].status == EnquiryStatus.NEW
    assert (await api.post(f"/admin/marketplace/enquiries/{uuid4()}", data={"status": "CLOSED"}, headers=admin_headers)).status_code == 404


@pytest.mark.parametrize("role", [Role.ADMIN, Role.VLCC, Role.FARMER])
async def test_inbox_is_closed_to_other_roles(api, database, token_for, role):
    headers = token_for(await create_user(database, role=role), role) | HTML
    assert (await api.get("/admin/marketplace/enquiries", headers=headers)).status_code == 403
    assert (await api.post(f"/admin/marketplace/enquiries/{uuid4()}", data={"status": "CLOSED"}, headers=headers)).status_code == 403


async def test_inbox_requires_login(api):
    response = await api.get("/admin/marketplace/enquiries", headers=HTML, follow_redirects=False)
    assert response.headers["location"] == "/login"
