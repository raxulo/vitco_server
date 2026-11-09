"""Cart, checkout and order management on a real database, including real parallel orders."""

import asyncio
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, select, update

from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.command import MoveOrderCommand, PlaceOrderCommand
from app.modules.marketplace.application.order_handler import MarketplaceOrderHandler
from app.modules.marketplace.domain.enums import OrderStatus, PaymentStatus, ProductStatus
from app.modules.marketplace.domain.exceptions import (
    InvalidOrderMoveException,
    ListingValidationException,
    OrderNotFoundException,
    OutOfStockException,
    SellingNotAllowedException,
)
from app.modules.marketplace.domain.orders import new_order_ref
from app.modules.marketplace.domain.policy import SellerPolicy
from app.modules.marketplace.infrastructure.merchandising_repository import MerchandisingRepository
from app.modules.marketplace.infrastructure.models import (
    MarketplaceCategoryModel,
    MarketplaceOrderItemModel,
    MarketplaceOrderModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
)
from app.modules.marketplace.infrastructure.order_repository import OrderRepository
from tests.dataexchange.factories import create_user


class _InRequest:
    """Runs each call in its own session, as each web request does."""

    def __init__(self, database, target) -> None:
        self._database = database
        self._target = target

    def __getattr__(self, name):
        method = getattr(self._target, name)

        async def call(*args, **kwargs):
            async with self._database.transaction():
                return await method(*args, **kwargs)

        return call


@pytest.fixture
def handler(database) -> MarketplaceOrderHandler:
    return _InRequest(database, MarketplaceOrderHandler(database, OrderRepository(database), MerchandisingRepository(database)))


@pytest.fixture
async def seller(database) -> UUID:
    return await create_user(database, role=Role.SUPER_ADMIN)


@pytest.fixture
def root(seller) -> CurrentUser:
    return CurrentUser(id=seller, role=str(int(Role.SUPER_ADMIN)))


async def _settings(database, **values) -> None:
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(**({"store_name": "Shop"} | values)))


@pytest.fixture(autouse=True)
async def plain_store(database) -> None:
    await _settings(database)


async def _variant(database, seller: UUID, *, price="100", mrp="120", stock=5, status=ProductStatus.PUBLISHED, active=True, deleted=False, category_active=True, title="Ghee") -> UUID:
    category_id, product_id, variant_id = uuid4(), uuid4(), uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=category_id, name="Cat", slug=f"c-{category_id.hex}", is_active=category_active))
        await session.flush()
        session.add(MarketplaceProductModel(id=product_id, seller_user_id=seller, category_id=category_id, title=title,
                                            slug=f"p-{product_id.hex}", status=status, is_deleted=deleted))
        await session.flush()
        session.add(MarketplaceProductVariantModel(id=variant_id, product_id=product_id, name="1 L", mrp=Decimal(mrp), price=Decimal(price), stock=stock, is_active=active))
    return variant_id


async def _stock(database, variant_id: UUID) -> int:
    async with database.transaction() as session:
        return await session.scalar(select(MarketplaceProductVariantModel.stock).where(MarketplaceProductVariantModel.id == variant_id))


def _command(items: dict[UUID, int], total: str, **overrides) -> PlaceOrderCommand:
    return PlaceOrderCommand(**({
        "items": items, "buyer_name": "Asha Devi", "buyer_phone": "+91 98765 43210",
        "address_line": "12 Temple Road, Ramgarh", "pincode": "302001", "checkout_token": str(uuid4()),
        "expected_total": Decimal(total),
    } | overrides))


async def _order(database, ref: str) -> MarketplaceOrderModel:
    async with database.transaction() as session:
        return await session.scalar(select(MarketplaceOrderModel).where(MarketplaceOrderModel.order_ref == ref))


# =========================================================
# CART
# =========================================================


async def test_cart_totals_and_delivery(database, handler, seller):
    await _settings(database, delivery_charge=Decimal("40"), free_delivery_above=Decimal("500"), min_order_amount=Decimal("150"))
    variant = await _variant(database, seller, price="100")

    small = await handler.view_cart({variant: 1})
    assert (small.subtotal, small.delivery_charge, small.total) == (Decimal("100.00"), Decimal("40.00"), Decimal("140.00"))
    assert small.below_minimum_by == Decimal("50.00") and small.can_check_out is False
    assert small.free_delivery_gap == Decimal("400.00")

    medium = await handler.view_cart({variant: 2})
    assert medium.can_check_out is True and medium.delivery_charge == Decimal("40.00")

    free = await handler.view_cart({variant: 5})
    assert (free.subtotal, free.delivery_charge, free.total) == (Decimal("500.00"), Decimal("0"), Decimal("500.00"))
    assert free.free_delivery_gap == 0


async def test_cart_reduces_to_stock_and_drops_what_is_off_sale(database, handler, seller):
    plenty = await _variant(database, seller, stock=2)
    empty = await _variant(database, seller, stock=0)
    hidden = [
        await _variant(database, seller, status=ProductStatus.DRAFT),
        await _variant(database, seller, deleted=True),
        await _variant(database, seller, active=False),
        await _variant(database, seller, category_active=False),
        uuid4(),
    ]

    cart = await handler.view_cart({plenty: 9, empty: 1, **dict.fromkeys(hidden, 1)})

    assert cart.removed_count == 5
    by_id = {line.variant_id: line for line in cart.lines}
    assert (by_id[plenty].quantity, by_id[plenty].reduced_from) == (2, 9)
    assert by_id[empty].is_out_of_stock is True
    assert cart.item_count == 2 and cart.subtotal == Decimal("200.00")


async def test_empty_cart_has_no_delivery_charge(database, handler):
    await _settings(database, delivery_charge=Decimal("40"))
    cart = await handler.view_cart({})
    assert (cart.total, cart.can_check_out) == (Decimal("0"), False)


async def test_cart_with_only_out_of_stock_has_no_delivery_charge(database, handler, seller):
    await _settings(database, delivery_charge=Decimal("40"))
    cart = await handler.view_cart({await _variant(database, seller, stock=0): 1})
    assert cart.total == 0


# =========================================================
# PLACING ORDERS
# =========================================================


async def test_order_saves_snapshots_and_takes_stock(database, handler, seller):
    await _settings(database, delivery_charge=Decimal("40"))
    variant = await _variant(database, seller, price="100", mrp="120", stock=5, title="Desi Ghee")

    ref = await handler.place_order(_command({variant: 2}, "240.00", notes=" Ring twice ", city=" Jaipur "))

    assert await _stock(database, variant) == 3
    order = await _order(database, ref)
    assert (order.subtotal, order.delivery_charge, order.total) == (Decimal("200.00"), Decimal("40.00"), Decimal("240.00"))
    assert (order.buyer_phone, order.notes, order.city, order.status) == ("9876543210", "Ring twice", "Jaipur", OrderStatus.PLACED)
    async with database.transaction() as session:
        line = await session.scalar(select(MarketplaceOrderItemModel).where(MarketplaceOrderItemModel.order_id == order.id))
    assert (line.product_title, line.variant_name, line.unit_price, line.mrp, line.quantity, line.line_total, line.seller_user_id) == (
        "Desi Ghee", "1 L", Decimal("100.00"), Decimal("120.00"), 2, Decimal("200.00"), seller,
    )


async def test_browser_total_cannot_buy_at_a_lower_price(database, handler, seller):
    variant = await _variant(database, seller, price="100")
    with pytest.raises(ListingValidationException) as error:
        await handler.place_order(_command({variant: 1}, "1.00"))
    assert "Prices changed" in error.value.errors["form"]
    assert await _stock(database, variant) == 5


async def test_price_change_after_opening_checkout_stops_the_order(database, handler, seller):
    variant = await _variant(database, seller, price="100")
    seen = (await handler.view_cart({variant: 1})).total
    async with database.transaction() as session:
        await session.execute(update(MarketplaceProductVariantModel).where(MarketplaceProductVariantModel.id == variant).values(price=Decimal("110"), mrp=Decimal("120")))

    with pytest.raises(ListingValidationException):
        await handler.place_order(_command({variant: 1}, str(seen)))


@pytest.mark.parametrize(
    ("bad", "field"),
    [
        ({"buyer_name": " "}, "buyer_name"),
        ({"buyer_phone": "123"}, "buyer_phone"),
        ({"address_line": "short"}, "address_line"),
        ({"pincode": "12"}, "pincode"),
        ({"pincode": "abcdef"}, "pincode"),
    ],
)
async def test_bad_buyer_details_are_refused(database, handler, seller, bad, field):
    variant = await _variant(database, seller)
    with pytest.raises(ListingValidationException) as error:
        await handler.place_order(_command({variant: 1}, "100.00", **bad))
    assert field in error.value.errors
    assert await _stock(database, variant) == 5


async def test_pincode_outside_delivery_area(database, handler, seller):
    await _settings(database, serviceable_pincodes=["302001"])
    variant = await _variant(database, seller)

    with pytest.raises(ListingValidationException) as error:
        await handler.place_order(_command({variant: 1}, "100.00", pincode="110001"))
    assert "do not deliver" in error.value.errors["pincode"]

    assert await handler.place_order(_command({variant: 1}, "100.00", pincode="302001"))


@pytest.mark.parametrize(
    ("settings", "message"),
    [
        ({"is_store_open": False, "closed_message": "Back on Monday"}, "Back on Monday"),
        ({"cod_enabled": False}, "Cash on Delivery"),
        ({"min_order_amount": Decimal("500")}, "minimum order"),
    ],
)
async def test_store_rules_stop_the_order(database, handler, seller, settings, message):
    await _settings(database, **settings)
    variant = await _variant(database, seller)
    with pytest.raises(ListingValidationException) as error:
        await handler.place_order(_command({variant: 1}, "100.00"))
    assert message in error.value.errors["form"]
    assert await _stock(database, variant) == 5


async def test_changed_cart_stops_the_order(database, handler, seller):
    variant = await _variant(database, seller, stock=1)
    empty_cart = {uuid4(): 1}
    for items in ({variant: 2}, empty_cart, {}):
        with pytest.raises(ListingValidationException):
            await handler.place_order(_command(items, "100.00"))
    assert await _stock(database, variant) == 1


async def test_same_checkout_page_submitted_twice_makes_one_order(database, handler, seller):
    variant = await _variant(database, seller, stock=5)
    command = _command({variant: 1}, "100.00")

    first = await handler.place_order(command)
    second = await handler.place_order(command)

    assert first == second
    assert await _stock(database, variant) == 4


async def test_same_token_racing_makes_one_order_and_takes_stock_once(database, handler, seller):
    variant = await _variant(database, seller, stock=20)
    command = _command({variant: 1}, "100.00")

    refs = await asyncio.gather(*(handler.place_order(command) for _ in range(5)))

    assert len(set(refs)) == 1
    assert await _stock(database, variant) == 19


async def test_failing_line_returns_stock_of_earlier_lines(database, seller):
    """Forces the race the cart check cannot see: stock vanishes between reading and taking."""
    first = await _variant(database, seller, stock=5)
    second = await _variant(database, seller, stock=5)

    class StockVanishes(OrderRepository):
        async def take_stock(self, variant_id, quantity):
            if variant_id == second:
                return False
            return await super().take_stock(variant_id, quantity)

    handler = _InRequest(database, MarketplaceOrderHandler(database, StockVanishes(database), MerchandisingRepository(database)))
    with pytest.raises(OutOfStockException):
        await handler.place_order(_command({first: 2, second: 2}, "400.00"))

    assert await _stock(database, first) == 5
    assert await _stock(database, second) == 5


async def test_parallel_orders_never_oversell(database, handler, seller):
    variant = await _variant(database, seller, stock=3)

    results = await asyncio.gather(
        *(handler.place_order(_command({variant: 1}, "100.00")) for _ in range(10)),
        return_exceptions=True,
    )

    placed = [result for result in results if isinstance(result, str)]
    refused = [result for result in results if isinstance(result, (OutOfStockException, ListingValidationException))]
    assert len(placed) == 3, results
    assert len(refused) == 7, results  # no database errors reached the customer
    assert await _stock(database, variant) == 0


def test_order_reference_is_easy_to_read():
    ref = new_order_ref(now_naive_ist())
    assert ref.startswith("VT-") and len(ref) == 16
    assert not set(ref[10:]) & set("01IO")
    assert ref != new_order_ref(now_naive_ist())


# =========================================================
# TRACKING
# =========================================================


async def test_tracking_needs_reference_and_phone(database, handler, seller):
    ref = await handler.place_order(_command({await _variant(database, seller): 1}, "100.00"))

    assert (await handler.track(ref, "9876543210")).order_ref == ref
    assert (await handler.track(f" {ref.lower()} ", "+91 98765 43210")).order_ref == ref
    assert await handler.track(ref, "9123456789") is None
    assert await handler.track("VT-000000-AAAAAA", "9876543210") is None
    assert await handler.track(ref, "") is None
    assert await handler.track("", "9876543210") is None


# =========================================================
# SELLER SIDE
# =========================================================


async def test_full_flow_to_delivered_marks_payment_paid(database, handler, seller, root):
    ref = await handler.place_order(_command({await _variant(database, seller): 1}, "100.00"))
    order_id = (await _order(database, ref)).id

    for status in (OrderStatus.CONFIRMED, OrderStatus.PACKED, OrderStatus.OUT_FOR_DELIVERY):
        moved = await handler.move_order(MoveOrderCommand(owner=root, id=order_id, status=status))
        assert moved.payment_status == PaymentStatus.PENDING
    await handler.move_order(MoveOrderCommand(owner=root, id=order_id, status=OrderStatus.DELIVERED))

    order = await _order(database, ref)
    assert (order.status, order.payment_status) == (OrderStatus.DELIVERED, PaymentStatus.PAID)


@pytest.mark.parametrize("target", [OrderStatus.DELIVERED, OrderStatus.PACKED, OrderStatus.PLACED])
async def test_steps_cannot_be_skipped(database, handler, seller, root, target):
    ref = await handler.place_order(_command({await _variant(database, seller): 1}, "100.00"))
    with pytest.raises(InvalidOrderMoveException):
        await handler.move_order(MoveOrderCommand(owner=root, id=(await _order(database, ref)).id, status=target))


async def test_cancel_returns_stock_once_and_needs_a_reason(database, handler, seller, root):
    variant = await _variant(database, seller, stock=5)
    ref = await handler.place_order(_command({variant: 2}, "200.00"))
    order_id = (await _order(database, ref)).id
    assert await _stock(database, variant) == 3

    with pytest.raises(ListingValidationException):
        await handler.move_order(MoveOrderCommand(owner=root, id=order_id, status=OrderStatus.CANCELLED, cancel_reason=" "))
    assert await _stock(database, variant) == 3

    await handler.move_order(MoveOrderCommand(owner=root, id=order_id, status=OrderStatus.CANCELLED, cancel_reason="Buyer asked"))
    assert await _stock(database, variant) == 5
    assert (await _order(database, ref)).cancel_reason == "Buyer asked"

    with pytest.raises(InvalidOrderMoveException):
        await handler.move_order(MoveOrderCommand(owner=root, id=order_id, status=OrderStatus.CANCELLED, cancel_reason="Again"))
    assert await _stock(database, variant) == 5


async def test_parallel_cancels_return_stock_once(database, handler, seller, root):
    variant = await _variant(database, seller, stock=5)
    ref = await handler.place_order(_command({variant: 2}, "200.00"))
    order_id = (await _order(database, ref)).id
    command = MoveOrderCommand(owner=root, id=order_id, status=OrderStatus.CANCELLED, cancel_reason="Twice")

    results = await asyncio.gather(*(handler.move_order(command) for _ in range(5)), return_exceptions=True)

    assert sum(1 for result in results if not isinstance(result, Exception)) == 1
    assert await _stock(database, variant) == 5


async def test_cancel_when_the_size_was_removed_still_works(database, handler, seller, root):
    variant = await _variant(database, seller, stock=5)
    ref = await handler.place_order(_command({variant: 1}, "100.00"))
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceProductVariantModel).where(MarketplaceProductVariantModel.id == variant))

    moved = await handler.move_order(MoveOrderCommand(owner=root, id=(await _order(database, ref)).id, status=OrderStatus.CANCELLED, cancel_reason="Discontinued"))

    assert moved.status == OrderStatus.CANCELLED
    assert moved.lines[0].product_title == "Ghee"  # history survives


async def test_list_search_and_filter(database, handler, seller, root):
    name = f"Buyer {uuid4().hex[:8]}"
    ref = await handler.place_order(_command({await _variant(database, seller): 2}, "200.00", buyer_name=name))

    items, total = await handler.list_orders(root, name, OrderStatus.PLACED, 0, 10)
    assert total == 1 and items[0].order_ref == ref and items[0].item_count == 2
    assert (await handler.list_orders(root, ref, None, 0, 10))[1] == 1
    assert (await handler.list_orders(root, name, OrderStatus.DELIVERED, 0, 10))[1] == 0


@pytest.mark.parametrize("role", [Role.ADMIN, Role.VLCC, Role.FARMER])
async def test_non_sellers_are_refused(database, handler, role):
    other = CurrentUser(id=await create_user(database, role=role), role=str(int(role)))
    with pytest.raises(SellingNotAllowedException):
        await handler.list_orders(other, None, None, 0, 10)
    with pytest.raises(SellingNotAllowedException):
        await handler.move_order(MoveOrderCommand(owner=other, id=uuid4(), status=OrderStatus.CONFIRMED))


async def test_seller_only_reaches_orders_with_their_items(database, handler, seller, root, monkeypatch):
    monkeypatch.setattr(SellerPolicy, "SELLER_ROLES", frozenset({Role.SUPER_ADMIN, Role.ADMIN}))
    other = CurrentUser(id=await create_user(database, role=Role.ADMIN), role=str(int(Role.ADMIN)))
    ref = await handler.place_order(_command({await _variant(database, seller): 1}, "100.00"))
    order_id = (await _order(database, ref)).id

    assert (await handler.get_order(root, order_id)).order_ref == ref
    with pytest.raises(OrderNotFoundException):
        await handler.get_order(other, order_id)
    with pytest.raises(OrderNotFoundException):
        await handler.move_order(MoveOrderCommand(owner=other, id=order_id, status=OrderStatus.CONFIRMED))
    assert (await handler.list_orders(other, ref, None, 0, 10))[1] == 0
