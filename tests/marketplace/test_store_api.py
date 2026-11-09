"""The public store API through the real app."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import AnimalStatus, HomeSectionType, ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalImageModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceBannerModel,
    MarketplaceCategoryModel,
    MarketplaceEnquiryModel,
    MarketplaceHomeSectionModel,
    MarketplaceOrderModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
)
from tests.dataexchange.factories import create_user

API = "/api/v1/marketplace"
LIST_KEYS = {"status", "code", "message", "items", "limit", "offset", "total", "pages", "next_page", "has_more"}
RECORD_KEYS = {"status", "code", "message", "data"}


@pytest.fixture(autouse=True)
async def plain_store(database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(
            store_name="Shop", support_phone="9876543210", delivery_charge=Decimal("40"), created_by=uuid4(),
            policies={"returns": "Seven days"},
        ))


@pytest.fixture
async def seller(database) -> UUID:
    return await create_user(database, role=Role.SUPER_ADMIN, name="Secret Seller")


async def _category(database) -> tuple[UUID, str]:
    row_id = uuid4()
    slug = f"c-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=row_id, name=f"Cat {row_id.hex[:6]}", slug=slug))
    return row_id, slug


async def _product(database, seller: UUID, category: UUID, title: str, *, price="100", mrp="120", stock=5, **fields) -> tuple[str, UUID]:
    product_id, variant_id = uuid4(), uuid4()
    slug = f"p-{product_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceProductModel(**({
            "id": product_id, "seller_user_id": seller, "category_id": category, "title": title, "slug": slug, "status": ProductStatus.PUBLISHED,
        } | fields)))
        await session.flush()
        session.add(MarketplaceProductVariantModel(id=variant_id, product_id=product_id, name="1 L", mrp=Decimal(mrp), price=Decimal(price), stock=stock, is_default=True))
        session.add(MarketplaceProductImageModel(product_id=product_id, url=f"/media/{product_id.hex}.webp"))
    return slug, variant_id


async def _animal(database, seller: UUID, title: str, **fields) -> tuple[str, str, UUID]:
    type_id, animal_id = uuid4(), uuid4()
    type_slug, slug = f"t-{type_id.hex}", f"a-{animal_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceAnimalTypeModel(id=type_id, name=f"Cow {type_id.hex}", slug=type_slug))
        await session.flush()
        session.add(MarketplaceAnimalModel(**({
            "id": animal_id, "seller_user_id": seller, "animal_type_id": type_id, "title": title, "slug": slug,
            "price": Decimal("85000.50"), "status": AnimalStatus.PUBLISHED,
        } | fields)))
        await session.flush()
        session.add(MarketplaceAnimalImageModel(animal_id=animal_id, url=f"/media/{animal_id.hex}.webp"))
    return slug, type_slug, type_id


def _order_body(variant: UUID, expected: str, /, **overrides) -> dict:
    return {
        "items": [{"variant_id": str(variant), "quantity": 1}], "buyer_name": "Asha Devi", "buyer_phone": "9876543210",
        "address_line": "12 Temple Road, Ramgarh", "pincode": "302001", "checkout_token": str(uuid4()), "expected_total": expected,
    } | overrides


async def _stock(database, variant: UUID) -> int:
    async with database.transaction() as session:
        return await session.scalar(select(MarketplaceProductVariantModel.stock).where(MarketplaceProductVariantModel.id == variant))


# =========================================================
# READS
# =========================================================


async def test_no_login_needed_and_record_envelope(api):
    response = await api.get(f"{API}/store")
    body = response.json()

    assert response.status_code == 200
    assert set(body) == RECORD_KEYS and body["status"] is True and body["code"] == 200
    assert body["data"]["store_name"] == "Shop"
    assert body["data"]["delivery_charge"] == "40.00"  # amounts are exact strings
    assert body["data"]["policies"] == {"returns": "Seven days"}
    assert "created_by" not in body["data"] and "id" not in body["data"]


async def test_product_list_filters_and_list_envelope(api, database, seller):
    mark = uuid4().hex[:10]
    category, category_slug = await _category(database)
    other, _ = await _category(database)
    cheap, _ = await _product(database, seller, category, f"Cheap {mark}", price="50", mrp="100")
    await _product(database, seller, other, f"Other {mark}", price="300", mrp="300")

    body = (await api.get(f"{API}/products", params={"search": mark, "category": category_slug})).json()
    assert set(body) == LIST_KEYS
    assert (body["total"], body["pages"], body["has_more"], body["next_page"]) == (1, 1, False, None)

    item = body["items"][0]
    assert (item["slug"], item["price"], item["mrp"], item["discount_percent"], item["in_stock"]) == (cheap, "50.00", "100.00", 50, True)
    assert "seller_user_id" not in item

    posted = (await api.post(f"{API}/products/list", json={"search": mark, "max_price": "100"})).json()
    assert [row["slug"] for row in posted["items"]] == [cheap]


async def test_pagination_metadata(api, database, seller):
    mark = uuid4().hex[:10]
    category, _ = await _category(database)
    for number in range(3):
        await _product(database, seller, category, f"{number} {mark}")

    body = (await api.get(f"{API}/products", params={"search": mark, "limit": 2})).json()

    assert (body["total"], body["pages"], body["has_more"], body["next_page"], body["limit"], body["offset"]) == (3, 2, True, 2, 2, 0)
    assert len(body["items"]) == 2


async def test_unknown_category_and_type_are_empty_not_everything(api):
    products = (await api.get(f"{API}/products", params={"category": "no-such"})).json()
    animals = (await api.get(f"{API}/animals", params={"type": "no-such"})).json()
    assert (products["total"], animals["total"]) == (0, 0)


@pytest.mark.parametrize(
    "params", [{"limit": 0}, {"limit": 101}, {"offset": -1}, {"sort": "hack"}, {"min_price": "abc"}, {"min_price": "NaN"}, {"max_price": "-1"}]
)
async def test_bad_query_is_a_clean_422(api, params):
    assert (await api.get(f"{API}/products", params=params)).status_code == 422


async def test_product_detail_is_complete_and_public_only(api, database, seller):
    category, _ = await _category(database)
    slug, variant = await _product(database, seller, category, "Ghee", description="Slow cooked", specifications=[{"label": "Life", "value": "6 months"}], stock=2)
    await _product(database, seller, category, "Related")

    response = await api.get(f"{API}/products/{slug}")
    data = response.json()["data"]

    assert data["product"]["sizes"][0]["variant_id"] == str(variant)
    assert data["product"]["sizes"][0]["few_left"] == 2
    assert "stock" not in data["product"]["sizes"][0]
    assert data["product"]["specifications"] == [{"label": "Life", "value": "6 months"}]
    assert [row["title"] for row in data["related"]] == ["Related"]
    assert str(seller) not in response.text and "Secret Seller" not in response.text


async def test_animal_list_and_detail(api, database, seller):
    mark = uuid4().hex[:10]
    slug, type_slug, type_id = await _animal(database, seller, f"Gir {mark}", lactation_number=2, milk_litres_per_day=Decimal("14.5"), age_months=48, district="Jaipur", health_notes="Healthy")
    breed_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceAnimalBreedModel(id=breed_id, animal_type_id=type_id, name="Gir"))

    listed = (await api.get(f"{API}/animals", params={"search": mark, "type": type_slug, "lactation": 2, "min_milk": "10"})).json()
    assert listed["total"] == 1
    row = listed["items"][0]
    assert (row["price"], row["milk_litres_per_day"], row["lactation_number"], row["location"], row["status"]) == ("85000.50", "14.50", 2, "Jaipur", "PUBLISHED")

    assert (await api.post(f"{API}/animals/list", json={"search": mark, "min_milk": "20"})).json()["total"] == 0

    detail = await api.get(f"{API}/animals/{slug}")
    assert detail.json()["data"]["animal"]["health_notes"] == "Healthy"
    assert str(seller) not in detail.text

    breeds = (await api.get(f"{API}/animal-types/{type_slug}/breeds")).json()
    assert breeds["items"] == [{"id": str(breed_id), "name": "Gir"}]
    assert (await api.get(f"{API}/animal-types/no-such/breeds")).json()["items"] == []


@pytest.mark.parametrize("path", ["products", "animals"])
async def test_unknown_listing_is_404_json(api, path):
    response = await api.get(f"{API}/{path}/nope")
    assert response.status_code == 404
    assert response.json()["success"] is False


async def test_draft_is_404_and_stays_out_of_lists(api, database, seller):
    mark = uuid4().hex[:10]
    category, _ = await _category(database)
    product, _ = await _product(database, seller, category, f"Draft {mark}", status=ProductStatus.DRAFT)
    animal, _, _ = await _animal(database, seller, f"Draft {mark}", status=AnimalStatus.DRAFT)

    assert (await api.get(f"{API}/products/{product}")).status_code == 404
    assert (await api.get(f"{API}/animals/{animal}")).status_code == 404
    assert (await api.get(f"{API}/products", params={"search": mark})).json()["total"] == 0
    assert (await api.get(f"{API}/animals", params={"search": mark})).json()["total"] == 0


async def test_home_follows_sections(api, database, seller):
    category, _ = await _category(database)
    await _product(database, seller, category, "Featured one", is_featured=True)
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceHomeSectionModel))
        await session.execute(delete(MarketplaceBannerModel))
        session.add(MarketplaceHomeSectionModel(section_type=HomeSectionType.FEATURED_PRODUCTS, title="Picks", sort_order=0))
        session.add(MarketplaceBannerModel(title="Hero", image_url="/hero.webp", cta_label="Go", cta_url="/marketplace/products", created_by=uuid4()))

    response = await api.get(f"{API}/home")
    data = response.json()["data"]

    assert data["store"]["store_name"] == "Shop"
    assert [banner["title"] for banner in data["hero_banners"]] == ["Hero"]
    assert "created_by" not in data["hero_banners"][0] and "is_active" not in data["hero_banners"][0]
    assert data["blocks"][0]["section_type"] == "FEATURED_PRODUCTS"
    assert any(row["title"] == "Featured one" for row in data["blocks"][0]["products"])


async def test_categories_and_animal_types_use_the_list_envelope(api, database):
    _, slug = await _category(database)
    body = (await api.get(f"{API}/categories")).json()
    assert set(body) == LIST_KEYS and slug in [row["slug"] for row in body["items"]]
    assert set((await api.get(f"{API}/animal-types")).json()) == LIST_KEYS


# =========================================================
# ENQUIRIES
# =========================================================


async def test_enquiry_saved_and_validated(api, database, seller):
    slug, _, _ = await _animal(database, seller, "Gir")

    created = await api.post(f"{API}/animals/{slug}/enquiries", json={"buyer_name": "Asha", "buyer_phone": "+91 98765 43210"})
    assert created.status_code == 201
    assert created.json()["code"] == 201

    bad = await api.post(f"{API}/animals/{slug}/enquiries", json={"buyer_name": "Asha", "buyer_phone": "123"})
    assert bad.status_code == 422
    assert "buyer_phone" in bad.json()["error"]["details"]

    async with database.transaction() as session:
        phones = list(await session.scalars(select(MarketplaceEnquiryModel.buyer_phone).where(MarketplaceEnquiryModel.animal_title == "Gir", MarketplaceEnquiryModel.buyer_phone == "9876543210")))
    assert "9876543210" in phones

    assert (await api.post(f"{API}/animals/nope/enquiries", json={"buyer_name": "Asha", "buyer_phone": "9876543210"})).status_code == 404


async def test_sold_animal_refuses_enquiry(api, database, seller):
    slug, _, _ = await _animal(database, seller, "Sold", status=AnimalStatus.SOLD)
    response = await api.post(f"{API}/animals/{slug}/enquiries", json={"buyer_name": "Asha", "buyer_phone": "9876543210"})
    assert response.status_code == 409


# =========================================================
# CART & ORDERS
# =========================================================


async def test_quote_prices_the_cart_from_the_server(api, database, seller):
    category, _ = await _category(database)
    _, variant = await _product(database, seller, category, "Ghee", price="100", stock=2)
    gone = uuid4()

    data = (await api.post(f"{API}/cart/quote", json={"items": [{"variant_id": str(variant), "quantity": 5}, {"variant_id": str(gone), "quantity": 1}]})).json()["data"]

    assert data["removed_count"] == 1
    line = data["lines"][0]
    assert (line["quantity"], line["reduced_from"], line["line_total"], line["max_quantity"]) == (2, 5, "200.00", 2)
    assert (data["subtotal"], data["delivery_charge"], data["total"], data["can_check_out"]) == ("200.00", "40.00", "240.00", True)
    assert "stock" not in line


async def test_order_then_track_shows_nothing_personal(api, database, seller):
    category, _ = await _category(database)
    _, variant = await _product(database, seller, category, "Ghee", price="100", stock=5)

    placed = await api.post(f"{API}/orders", json=_order_body(variant, "140.00"))
    assert placed.status_code == 201
    data = placed.json()["data"]
    assert data["total"] == "140.00" and data["status"] == "PLACED"
    assert await _stock(database, variant) == 4

    tracked = await api.post(f"{API}/orders/track", json={"order_ref": data["order_ref"], "phone": "98765 43210"})
    body = tracked.json()["data"]
    assert (body["order_ref"], body["status"], body["total"], body["pincode"]) == (data["order_ref"], "PLACED", "140.00", "302001")
    assert body["lines"][0]["product_title"] == "Ghee"
    for private in ("Asha", "Temple Road", "9876543210"):
        assert private not in tracked.text


async def test_tracking_gives_the_same_answer_for_wrong_reference_and_phone(api, database, seller):
    category, _ = await _category(database)
    _, variant = await _product(database, seller, category, "Ghee")
    order_ref = (await api.post(f"{API}/orders", json=_order_body(variant, "140.00"))).json()["data"]["order_ref"]

    wrong_phone = await api.post(f"{API}/orders/track", json={"order_ref": order_ref, "phone": "9123456789"})
    wrong_ref = await api.post(f"{API}/orders/track", json={"order_ref": "VT-000000-AAAAAA", "phone": "9876543210"})

    assert wrong_phone.status_code == wrong_ref.status_code == 404
    assert wrong_phone.json() == wrong_ref.json()


async def test_api_cannot_set_a_price_or_status(api, database, seller):
    category, _ = await _category(database)
    _, variant = await _product(database, seller, category, "Ghee", price="100")

    cheap = await api.post(f"{API}/orders", json=_order_body(variant, "1.00"))
    assert cheap.status_code == 422 and "Prices changed" in cheap.json()["error"]["details"]["form"]

    sneaky = _order_body(variant, "140.00", status="DELIVERED", payment_status="PAID", total="1.00", subtotal="1.00")
    placed = await api.post(f"{API}/orders", json=sneaky)
    assert placed.status_code == 201
    async with database.transaction() as session:
        order = await session.scalar(select(MarketplaceOrderModel).where(MarketplaceOrderModel.order_ref == placed.json()["data"]["order_ref"]))
    assert (order.total, order.status.value, order.payment_status.value) == (Decimal("140.00"), "PLACED", "PENDING")


async def test_retrying_the_same_token_gives_the_same_order(api, database, seller):
    category, _ = await _category(database)
    _, variant = await _product(database, seller, category, "Ghee", stock=5)
    body = _order_body(variant, "140.00")

    first = await api.post(f"{API}/orders", json=body)
    second = await api.post(f"{API}/orders", json=body)

    assert first.json()["data"]["order_ref"] == second.json()["data"]["order_ref"]
    assert await _stock(database, variant) == 4


@pytest.mark.parametrize(
    "bad",
    [
        {"items": []}, {"checkout_token": "abc"}, {"expected_total": "NaN"}, {"expected_total": "-1"},
        {"items": [{"variant_id": "abc", "quantity": 1}]}, {"buyer_phone": "x" * 21},
    ],
)
async def test_malformed_order_is_a_clean_422(api, database, seller, bad):
    category, _ = await _category(database)
    _, variant = await _product(database, seller, category, "Ghee", stock=5)
    assert (await api.post(f"{API}/orders", json=_order_body(variant, "140.00", **bad))).status_code == 422
    assert await _stock(database, variant) == 5


async def test_quantity_above_the_limit_is_refused(api, database, seller):
    category, _ = await _category(database)
    _, variant = await _product(database, seller, category, "Ghee", stock=500)
    body = _order_body(variant, "5040.00", items=[{"variant_id": str(variant), "quantity": 51}])
    assert (await api.post(f"{API}/orders", json=body)).status_code == 422


async def test_there_is_no_public_way_to_list_or_change_orders(api):
    assert (await api.get(f"{API}/orders")).status_code == 405
    assert (await api.put(f"{API}/orders/{uuid4()}/status", json={"status": "DELIVERED"})).status_code in (404, 405)
