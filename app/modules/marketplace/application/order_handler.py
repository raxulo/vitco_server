"""
Cart, guest COD checkout and order management (DECISION-018).

Order writes follow one rule. A savepoint on SQLite opens a deferred transaction, and a
deferred transaction that reads and then writes fails at once if another writer committed
in between. So every read happens before the savepoint, and the first statement inside it
is the guarded stock update, which waits its turn through busy_timeout.

Prices and totals only ever come from the database.

Python 3.13+
"""

from __future__ import annotations

import re
from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.marketplace.application.command import MoveOrderCommand, PlaceOrderCommand
from app.modules.marketplace.domain.contact import normalize_indian_mobile
from app.modules.marketplace.domain.entities import ListingViewer
from app.modules.marketplace.domain.enums import OrderStatus, PaymentStatus
from app.modules.marketplace.domain.exceptions import (
    DuplicateCheckoutException,
    InvalidOrderMoveException,
    ListingValidationException,
    OrderNotFoundException,
    OutOfStockException,
    SellingNotAllowedException,
)
from app.modules.marketplace.domain.irepository import IMerchandisingRepository, IOrderRepository
from app.modules.marketplace.domain.merchandising import StoreSettings
from app.modules.marketplace.domain.orders import (
    MAX_QUANTITY_PER_LINE,
    CartLine,
    CartVariant,
    CartView,
    Order,
    OrderLine,
    OrderSummary,
    new_order_ref,
)
from app.modules.marketplace.domain.policy import SellerPolicy

_PINCODE = re.compile(r"^\d{6}$")
_MIN_ADDRESS_LENGTH = 10
_DEFAULT_STORE_NAME = "Vitco Marketplace"


class MarketplaceOrderHandler:

    __slots__ = ("_database", "_orders", "_content")

    def __init__(
        self,
        database: DatabaseManager,
        orders: IOrderRepository,
        content: IMerchandisingRepository,
    ) -> None:
        self._database = database
        self._orders = orders
        self._content = content

    # =========================================================
    # CART
    # =========================================================

    async def view_cart(self, items: dict[UUID, int]) -> CartView:
        settings = await self._settings()
        variants = {variant.variant_id: variant for variant in await self._orders.cart_variants(set(items))}
        return self._build_cart(items, variants, settings)

    async def _settings(self) -> StoreSettings:
        return await self._content.get_settings() or StoreSettings(store_name=_DEFAULT_STORE_NAME)

    @staticmethod
    def _build_cart(items: dict[UUID, int], variants: dict[UUID, CartVariant], settings: StoreSettings) -> CartView:
        cart = CartView(
            min_order_amount=settings.min_order_amount,
            free_delivery_above=settings.free_delivery_above,
            is_store_open=settings.is_store_open,
            closed_message=settings.closed_message,
            cod_enabled=settings.cod_enabled,
        )
        for variant_id, wanted in items.items():
            variant = variants.get(variant_id)
            if variant is None:
                cart.removed_count += 1
                continue
            wanted = min(wanted, MAX_QUANTITY_PER_LINE)
            quantity = min(wanted, variant.stock)
            cart.lines.append(CartLine(
                variant_id=variant.variant_id, slug=variant.slug, title=variant.title, size=variant.size,
                price=variant.price, mrp=variant.mrp, quantity=quantity, line_total=variant.price * quantity,
                stock=variant.stock, image_url=variant.image_url, reduced_from=wanted if quantity < wanted else None,
            ))
        cart.subtotal = sum((line.line_total for line in cart.lines), start=cart.subtotal)
        if cart.payable_lines:
            cart.delivery_charge = settings.delivery_for(cart.subtotal)
        cart.total = cart.subtotal + cart.delivery_charge
        return cart

    # =========================================================
    # CHECKOUT
    # =========================================================

    async def place_order(self, command: PlaceOrderCommand) -> str:
        """The order reference. Submitting the same checkout page twice returns the same order."""
        existing = await self._orders.ref_for_token(command.checkout_token)
        if existing is not None:
            return existing

        settings = await self._settings()
        phone = self._check_buyer(command, settings)
        variants = {variant.variant_id: variant for variant in await self._orders.cart_variants(set(command.items))}
        cart = self._build_cart(command.items, variants, settings)
        self._check_cart(cart, command, settings)

        now = now_naive_ist()
        order = Order(
            id=uuid4(),
            order_ref=new_order_ref(now),
            checkout_token=command.checkout_token,
            buyer_user_id=command.buyer_user_id,
            buyer_name=command.buyer_name.strip(),
            buyer_phone=phone,
            address_line=command.address_line.strip(),
            city=(command.city or "").strip() or None,
            state=(command.state or "").strip() or None,
            pincode=command.pincode.strip(),
            notes=(command.notes or "").strip() or None,
            subtotal=cart.subtotal,
            delivery_charge=cart.delivery_charge,
            total=cart.total,
            lines=[
                OrderLine(
                    id=uuid4(),
                    product_id=variants[line.variant_id].product_id,
                    variant_id=line.variant_id,
                    seller_user_id=variants[line.variant_id].seller_user_id,
                    product_title=line.title,
                    variant_name=line.size,
                    image_url=line.image_url,
                    mrp=line.mrp,
                    unit_price=line.price,
                    quantity=line.quantity,
                    line_total=line.line_total,
                )
                for line in cart.payable_lines
            ],
        )

        try:
            async with self._database.transaction():
                for line in order.lines:
                    if not await self._orders.take_stock(line.variant_id, line.quantity):
                        raise OutOfStockException()
                await self._orders.add_order(order)
        except DuplicateCheckoutException:
            # Two submits raced; the savepoint gave this one's stock back and the other one won
            winner = await self._orders.ref_for_token(command.checkout_token)
            if winner is None:
                raise
            return winner
        return order.order_ref

    @staticmethod
    def _check_buyer(command: PlaceOrderCommand, settings: StoreSettings) -> str:
        errors: dict[str, str] = {}
        if len(command.buyer_name.strip()) < 2:
            errors["buyer_name"] = "Please enter your name."
        phone = normalize_indian_mobile(command.buyer_phone)
        if phone is None:
            errors["buyer_phone"] = "Please enter a 10 digit mobile number."
        if len(command.address_line.strip()) < _MIN_ADDRESS_LENGTH:
            errors["address_line"] = "Please enter your full address, with house and area."
        pincode = command.pincode.strip()
        if not _PINCODE.match(pincode):
            errors["pincode"] = "Please enter a 6 digit pincode."
        elif not settings.serves(pincode):
            errors["pincode"] = "Sorry, we do not deliver to this pincode yet."
        if errors:
            raise ListingValidationException(errors)
        return phone

    @staticmethod
    def _check_cart(cart: CartView, command: PlaceOrderCommand, settings: StoreSettings) -> None:
        if not settings.is_store_open:
            raise ListingValidationException({"form": settings.closed_message or "We are not taking orders right now."})
        if not settings.cod_enabled:
            raise ListingValidationException({"form": "Cash on Delivery is not available right now."})
        if not cart.payable_lines:
            raise ListingValidationException({"form": "Your cart is empty or its items are out of stock."})
        if cart.removed_count or any(line.reduced_from for line in cart.lines):
            raise ListingValidationException({"form": "Some items in your cart changed. Please review it and try again."})
        if cart.below_minimum_by > 0:
            raise ListingValidationException({"form": "Your order is below the minimum order amount."})
        if cart.total != command.expected_total:
            raise ListingValidationException({"form": "Prices changed since you opened this page. Please check the new total."})

    async def placed_order(self, order_ref: str) -> Order | None:
        """For the thank-you page, which shows only the reference and amounts."""
        return await self._orders.get_by_ref(order_ref)

    # =========================================================
    # TRACKING
    # =========================================================

    async def track(self, order_ref: str, phone: str) -> Order | None:
        """Needs both values. A wrong reference and a wrong phone give the same answer."""
        normalized = normalize_indian_mobile(phone)
        if normalized is None or not order_ref.strip():
            return None
        return await self._orders.find_for_tracking(order_ref.strip().upper(), normalized)

    # =========================================================
    # SELLER SIDE
    # =========================================================

    @staticmethod
    def _seller(owner: ListingViewer | None) -> ListingViewer:
        if owner is None:
            raise SellingNotAllowedException()
        SellerPolicy.ensure_can_sell(owner.role_type)
        return owner

    async def list_orders(
        self, owner: ListingViewer | None, keyword: str | None, status: OrderStatus | None, offset: int, limit: int
    ) -> tuple[list[OrderSummary], int]:
        return await self._orders.list_orders(self._seller(owner), keyword, status, offset, limit)

    async def get_order(self, owner: ListingViewer | None, order_id: UUID) -> Order:
        order = await self._orders.get_order(order_id, self._seller(owner))
        if order is None:
            raise OrderNotFoundException()
        return order

    async def move_order(self, command: MoveOrderCommand) -> Order:
        seller = self._seller(command.owner)
        order = await self._orders.get_order(command.id, seller)
        if order is None:
            raise OrderNotFoundException()
        if not order.status.can_move_to(command.status):
            raise InvalidOrderMoveException()

        reason = (command.cancel_reason or "").strip() or None
        if command.status == OrderStatus.CANCELLED and reason is None:
            raise ListingValidationException({"cancel_reason": "Please give a reason for cancelling."})

        from_status = order.status
        order.status = command.status
        if command.status == OrderStatus.DELIVERED:
            order.payment_status = PaymentStatus.PAID  # Cash on Delivery was collected
        if command.status == OrderStatus.CANCELLED:
            order.cancel_reason = reason

        async with self._database.transaction():
            # Conditional on the old status, so two clicks can never return stock twice
            if not await self._orders.move_order(order, from_status):
                raise InvalidOrderMoveException()
            if command.status == OrderStatus.CANCELLED:
                for line in order.lines:
                    if line.variant_id is not None:
                        await self._orders.return_stock(line.variant_id, line.quantity)
        return order
