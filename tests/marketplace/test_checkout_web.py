"""The buying flow through the real app, as a guest with a cookie jar, and the seller's orders screen."""

import asyncio
import re
from decimal import Decimal
from uuid import UUID, uuid4

import httpx
import pytest
from sqlalchemy import delete, select

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import OrderStatus, ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceCategoryModel,
    MarketplaceOrderModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
)
from app.web.storefront.cart_cookie import cart_count, parse_cart, serialize_cart
from tests.dataexchange.factories import create_user

HTML = {"accept": "text/html"}
BUYER = {
    "buyer_name": "Asha Devi", "buyer_phone": "98765 43210", "address_line": "12 Temple Road, Ramgarh",
    "city": "Jaipur", "state": "Rajasthan", "pincode": "302001",
}


@pytest.fixture
async def guest(api):
    """A browser of its own: same app as `api`, its own cookies."""
    async with httpx.AsyncClient(transport=api._transport, base_url="http://test", headers=HTML) as client:
        yield client


@pytest.fixture(autouse=True)
async def plain_store(database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(store_name="Shop", delivery_charge=Decimal("40"), free_delivery_above=Decimal("500")))


@pytest.fixture
async def seller(database) -> UUID:
    return await create_user(database, role=Role.SUPER_ADMIN)


@pytest.fixture
async def admin_headers(seller, token_for) -> dict[str, str]:
    return token_for(seller, Role.SUPER_ADMIN) | HTML


async def _variant(database, seller: UUID, *, stock=5, price="100", mrp="120", title=None) -> tuple[UUID, str]:
    category_id, product_id, variant_id = uuid4(), uuid4(), uuid4()
    slug = f"p-{product_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=category_id, name="Cat", slug=f"c-{category_id.hex}"))
        await session.flush()
        session.add(MarketplaceProductModel(id=product_id, seller_user_id=seller, category_id=category_id, title=title or f"Ghee {product_id.hex[:6]}", slug=slug, status=ProductStatus.PUBLISHED))
        await session.flush()
        session.add(MarketplaceProductVariantModel(id=variant_id, product_id=product_id, name="1 L", mrp=Decimal(mrp), price=Decimal(price), stock=stock, is_default=True))
        session.add(MarketplaceProductImageModel(product_id=product_id, url=f"/media/{product_id.hex}.webp"))
    return variant_id, slug


async def _stock(database, variant_id: UUID) -> int:
    async with database.transaction() as session:
        return await session.scalar(select(MarketplaceProductVariantModel.stock).where(MarketplaceProductVariantModel.id == variant_id))


def _hidden(page: str, name: str) -> str:
    return re.search(rf'name="{name}" value="([^"]*)"', page).group(1)


async def _checkout_form(guest) -> dict[str, str]:
    page = (await guest.get("/marketplace/checkout")).text
    return {**BUYER, "checkout_token": _hidden(page, "checkout_token"), "expected_total": _hidden(page, "expected_total")}


async def _orders_count(database, phone: str = "9876543210") -> int:
    async with database.transaction() as session:
        return len((await session.scalars(select(MarketplaceOrderModel.id).where(MarketplaceOrderModel.buyer_phone == phone))).all())


# =========================================================
# COOKIE
# =========================================================


def test_cookie_round_trip_and_limits():
    first, second = uuid4(), uuid4()
    assert parse_cart(serialize_cart({first: 2, second: 3})) == {first: 2, second: 3}
    assert cart_count(serialize_cart({first: 2, second: 3})) == 5
    assert parse_cart(f"{first.hex}:9999") == {first: 50}


@pytest.mark.parametrize("junk", ["", "abc", "a:b:c", f"{uuid4().hex}:x", f"{uuid4().hex}:-1", f"{uuid4().hex}:0", ",,,,", "'; DROP TABLE--"])
def test_tampered_cookie_only_loses_items(junk):
    assert parse_cart(junk) == {}


def test_oversized_cookie_is_cut_to_the_line_limit():
    assert len(parse_cart(",".join(f"{uuid4().hex}:1" for _ in range(500)))) == 30


# =========================================================
# CART PAGE
# =========================================================


async def test_add_change_remove_and_header_count(database, seller, guest):
    variant, slug = await _variant(database, seller)

    page = (await guest.get(f"/marketplace/products/{slug}")).text
    assert f'value="{variant}"' in page and "Add to cart" in page and "Buy now" in page

    added = await guest.post("/marketplace/cart/add", data={"variant_id": str(variant), "quantity": "2"}, follow_redirects=False)
    assert (added.status_code, added.headers["location"]) == (303, "/marketplace/cart")

    cart = (await guest.get("/marketplace/cart")).text
    assert "₹200" in cart and "₹240" in cart and 'class="st-cart-count"' in cart
    assert "Add ₹300 more for free delivery" in cart

    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant), "quantity": "1"})
    assert "₹300" in (await guest.get("/marketplace/cart")).text  # adding again adds up

    await guest.post("/marketplace/cart/update", data={"variant_id": str(variant), "quantity": "5"})
    full = (await guest.get("/marketplace/cart")).text
    assert "₹500" in full and "Free" in full  # free delivery reached

    await guest.post("/marketplace/cart/update", data={"variant_id": str(variant), "remove": "1"})
    empty = (await guest.get("/marketplace/cart")).text
    assert "Your cart is empty" in empty and 'class="st-cart-count"' not in empty


async def test_cart_cleans_itself_of_products_taken_off_sale(database, seller, guest):
    variant, _ = await _variant(database, seller)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceProductVariantModel).where(MarketplaceProductVariantModel.id == variant))

    page = (await guest.get("/marketplace/cart")).text

    assert "no longer on sale" in page and "Your cart is empty" in page
    assert "no longer on sale" not in (await guest.get("/marketplace/cart")).text  # said once, cookie is clean


@pytest.mark.parametrize("bad", [{"variant_id": "abc"}, {"variant_id": str(uuid4()), "quantity": "abc"}, {}])
async def test_bad_cart_input_never_errors(guest, bad):
    assert (await guest.post("/marketplace/cart/add", data=bad, follow_redirects=False)).status_code == 303
    assert (await guest.post("/marketplace/cart/update", data=bad, follow_redirects=False)).status_code == 303
    assert (await guest.get("/marketplace/cart")).status_code == 200


async def test_checkout_with_empty_cart_goes_back_to_the_cart(guest):
    response = await guest.get("/marketplace/checkout", follow_redirects=False)
    assert response.headers["location"] == "/marketplace/cart"


async def test_buy_now_goes_to_checkout(database, seller, guest):
    variant, _ = await _variant(database, seller)
    response = await guest.post("/marketplace/cart/add", data={"variant_id": str(variant), "buy_now": "1"}, follow_redirects=False)
    assert response.headers["location"] == "/marketplace/checkout"
    assert "Place order" in (await guest.get("/marketplace/checkout")).text


# =========================================================
# CHECKOUT
# =========================================================


async def test_guest_buys_and_tracks(database, seller, guest):
    variant, _ = await _variant(database, seller, stock=5)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant), "quantity": "2"})

    placed = await guest.post("/marketplace/checkout", data=await _checkout_form(guest), follow_redirects=False)
    assert placed.status_code == 303
    url = placed.headers["location"]
    order_ref = url.rsplit("/", 1)[1]

    thanks = (await guest.get(url)).text
    assert order_ref in thanks and "₹240" in thanks
    assert "Asha" not in thanks and "Temple Road" not in thanks  # no personal details on this page
    assert await _stock(database, variant) == 3
    assert "Your cart is empty" in (await guest.get("/marketplace/cart")).text

    tracked = await guest.post("/marketplace/track", data={"order_ref": order_ref, "phone": "9876543210"})
    assert order_ref in tracked.text and "Placed" in tracked.text and "₹240" in tracked.text
    assert "Temple Road" not in tracked.text


async def test_tracking_gives_the_same_answer_for_wrong_reference_and_wrong_phone(database, seller, guest):
    variant, _ = await _variant(database, seller)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    placed = await guest.post("/marketplace/checkout", data=await _checkout_form(guest), follow_redirects=False)
    order_ref = placed.headers["location"].rsplit("/", 1)[1]

    wrong_phone = await guest.post("/marketplace/track", data={"order_ref": order_ref, "phone": "9123456789"})
    wrong_ref = await guest.post("/marketplace/track", data={"order_ref": "VT-000000-AAAAAA", "phone": "9876543210"})

    message = "We could not find an order"
    assert message in wrong_phone.text and message in wrong_ref.text
    assert wrong_phone.status_code == wrong_ref.status_code == 200
    assert "₹" not in wrong_phone.text.split("<main")[1].split("</main>")[0]


async def test_thank_you_page_only_opens_for_the_browser_that_ordered(database, seller, guest, api):
    variant, _ = await _variant(database, seller)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    placed = await guest.post("/marketplace/checkout", data=await _checkout_form(guest), follow_redirects=False)

    async with httpx.AsyncClient(transport=api._transport, base_url="http://test", headers=HTML) as stranger:
        response = await stranger.get(placed.headers["location"], follow_redirects=False)
    assert response.headers["location"] == "/marketplace/track"


async def test_invalid_details_keep_what_was_typed_and_the_token(database, seller, guest):
    variant, _ = await _variant(database, seller)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    form = await _checkout_form(guest)

    response = await guest.post("/marketplace/checkout", data=form | {"buyer_phone": "123", "pincode": "12"})

    assert response.status_code == 422
    assert "10 digit mobile number" in response.text and "6 digit pincode" in response.text
    assert "Temple Road" in response.text and "Asha Devi" in response.text
    assert _hidden(response.text, "checkout_token") == form["checkout_token"]
    assert await _stock(database, variant) == 5


async def test_tampered_total_stops_the_order(database, seller, guest):
    variant, _ = await _variant(database, seller, price="100")
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    form = await _checkout_form(guest)

    response = await guest.post("/marketplace/checkout", data=form | {"expected_total": "1.00"})

    assert response.status_code == 422
    assert "Prices changed" in response.text
    assert await _stock(database, variant) == 5


@pytest.mark.parametrize("junk", [{"checkout_token": "abc"}, {"expected_total": "abc"}, {"expected_total": "NaN"}])
async def test_junk_hidden_fields_are_refused_cleanly(database, seller, guest, junk):
    variant, _ = await _variant(database, seller)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    form = await _checkout_form(guest)
    assert (await guest.post("/marketplace/checkout", data=form | junk)).status_code == 422
    assert await _stock(database, variant) == 5


async def test_double_submit_makes_one_order(database, seller, guest):
    phone = "9811111111"
    variant, _ = await _variant(database, seller, stock=5)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    form = await _checkout_form(guest) | {"buyer_phone": phone}

    first = await guest.post("/marketplace/checkout", data=form, follow_redirects=False)
    second = await guest.post("/marketplace/checkout", data=form, follow_redirects=False)

    assert first.headers["location"] == second.headers["location"]
    assert await _stock(database, variant) == 4


async def test_parallel_buyers_over_http_never_oversell(database, seller, api):
    variant, _ = await _variant(database, seller, stock=3)
    phone = f"97{uuid4().int % 100000000:08d}"

    async def open_checkout(client):
        await client.post("/marketplace/cart/add", data={"variant_id": str(variant)})
        return await _checkout_form(client)

    # Everyone has the form open before anyone submits, so all ten really compete for the stock
    clients = [httpx.AsyncClient(transport=api._transport, base_url="http://test", headers=HTML) for _ in range(10)]
    try:
        forms = await asyncio.gather(*(open_checkout(client) for client in clients))
        responses = await asyncio.gather(*(
            client.post("/marketplace/checkout", data=form | {"buyer_phone": phone}, follow_redirects=False)
            for client, form in zip(clients, forms)
        ))
    finally:
        await asyncio.gather(*(client.aclose() for client in clients))

    assert sorted(response.status_code for response in responses).count(303) >= 3
    assert all(response.status_code in (303, 422) for response in responses), [r.status_code for r in responses]
    assert await _stock(database, variant) == 0
    assert await _orders_count(database, phone) == 3


async def test_closed_store_stops_buying(database, seller, guest):
    variant, slug = await _variant(database, seller)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant)})
    form = await _checkout_form(guest)
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(store_name="Shop", is_store_open=False, closed_message="Back on Monday"))

    assert "Add to cart" not in (await guest.get(f"/marketplace/products/{slug}")).text
    assert "Back on Monday" in (await guest.get("/marketplace/cart")).text
    response = await guest.post("/marketplace/checkout", data=form, follow_redirects=False)
    assert response.headers["location"] == "/marketplace/cart"  # nothing to check out now
    assert await _stock(database, variant) == 5


async def test_out_of_stock_product_page_disables_buying(database, seller, guest):
    _, slug = await _variant(database, seller, stock=0)
    page = (await guest.get(f"/marketplace/products/{slug}")).text
    assert re.search(r"data-buy\s+disabled", page) and "Out of stock" in page


# =========================================================
# SELLER ORDERS
# =========================================================


async def _placed_order(database, seller, guest, **variant) -> tuple[str, UUID]:
    variant_id, _ = await _variant(database, seller, **variant)
    await guest.post("/marketplace/cart/add", data={"variant_id": str(variant_id)})
    placed = await guest.post("/marketplace/checkout", data=await _checkout_form(guest), follow_redirects=False)
    return placed.headers["location"].rsplit("/", 1)[1], variant_id


async def _order_id(database, order_ref: str) -> UUID:
    async with database.transaction() as session:
        return await session.scalar(select(MarketplaceOrderModel.id).where(MarketplaceOrderModel.order_ref == order_ref))


async def test_seller_runs_an_order_to_delivered(api, database, seller, guest, admin_headers):
    order_ref, _ = await _placed_order(database, seller, guest)
    assert order_ref in (await api.get("/admin/marketplace/orders", params={"status": "PLACED", "search": order_ref}, headers=admin_headers)).text

    order_id = await _order_id(database, order_ref)
    page = (await api.get(f"/admin/marketplace/orders/{order_id}", headers=admin_headers)).text
    assert "Asha Devi" in page and "Temple Road" in page and "Confirm order" in page
    assert "Mark as delivered" not in page  # only the next step is offered

    for status in ("CONFIRMED", "PACKED", "OUT_FOR_DELIVERY", "DELIVERED"):
        moved = await api.post(f"/admin/marketplace/orders/{order_id}/move", data={"status": status}, headers=admin_headers, follow_redirects=False)
        assert moved.status_code == 303, status

    done = (await api.get(f"/admin/marketplace/orders/{order_id}", headers=admin_headers)).text
    assert "This order is finished" in done and "Paid" in done

    tracked = await guest.post("/marketplace/track", data={"order_ref": order_ref, "phone": "9876543210"})
    assert "Paid" in tracked.text and tracked.text.count("st-step-done") == 5


async def test_cancel_needs_reason_returns_stock_and_shows_the_customer(api, database, seller, guest, admin_headers):
    order_ref, variant = await _placed_order(database, seller, guest, stock=5)
    order_id = await _order_id(database, order_ref)
    assert await _stock(database, variant) == 4

    missing = await api.post(f"/admin/marketplace/orders/{order_id}/move", data={"status": "CANCELLED"}, headers=admin_headers)
    assert missing.status_code == 422 and "give a reason" in missing.text
    assert await _stock(database, variant) == 4

    await api.post(f"/admin/marketplace/orders/{order_id}/move", data={"status": "CANCELLED", "cancel_reason": "Out of area"}, headers=admin_headers)
    assert await _stock(database, variant) == 5

    tracked = await guest.post("/marketplace/track", data={"order_ref": order_ref, "phone": "9876543210"})
    assert "was cancelled" in tracked.text and "Out of area" in tracked.text


async def test_skipping_a_step_and_bad_status_are_refused(api, database, seller, guest, admin_headers):
    order_ref, _ = await _placed_order(database, seller, guest)
    order_id = await _order_id(database, order_ref)

    skip = await api.post(f"/admin/marketplace/orders/{order_id}/move", data={"status": "DELIVERED"}, headers=admin_headers)
    bad = await api.post(f"/admin/marketplace/orders/{order_id}/move", data={"status": "HACKED"}, headers=admin_headers)

    assert skip.status_code == 409 and bad.status_code == 422
    async with database.transaction() as session:
        assert await session.scalar(select(MarketplaceOrderModel.status).where(MarketplaceOrderModel.id == order_id)) == OrderStatus.PLACED


async def test_unknown_order_is_404(api, admin_headers):
    assert (await api.get(f"/admin/marketplace/orders/{uuid4()}", headers=admin_headers)).status_code == 404
    assert (await api.post(f"/admin/marketplace/orders/{uuid4()}/move", data={"status": "CONFIRMED"}, headers=admin_headers)).status_code == 404


@pytest.mark.parametrize("role", [Role.ADMIN, Role.VLCC, Role.FARMER])
async def test_orders_are_closed_to_other_roles(api, database, token_for, role):
    headers = token_for(await create_user(database, role=role), role) | HTML
    assert (await api.get("/admin/marketplace/orders", headers=headers)).status_code == 403
    assert (await api.post(f"/admin/marketplace/orders/{uuid4()}/move", data={"status": "CONFIRMED"}, headers=headers)).status_code == 403


async def test_orders_require_login(api):
    response = await api.get("/admin/marketplace/orders", headers=HTML, follow_redirects=False)
    assert response.headers["location"] == "/login"
