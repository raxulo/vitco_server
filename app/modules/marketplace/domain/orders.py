"""
Cart and orders.

Python 3.13+
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.marketplace.domain.enums import OrderStatus, PaymentMethod, PaymentStatus

MAX_QUANTITY_PER_LINE = 50
MAX_CART_LINES = 30

# Steps a customer sees, in order; a cancelled order leaves this path
ORDER_STEPS = (
    OrderStatus.PLACED,
    OrderStatus.CONFIRMED,
    OrderStatus.PACKED,
    OrderStatus.OUT_FOR_DELIVERY,
    OrderStatus.DELIVERED,
)

# No 0/O or 1/I, because customers read these out over the phone
_REF_ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def new_order_ref(now: datetime) -> str:
    code = "".join(secrets.choice(_REF_ALPHABET) for _ in range(6))
    return f"VT-{now:%y%m%d}-{code}"


@dataclass(slots=True, kw_only=True)
class CartVariant:
    """A size that can be bought now, as the database says."""

    variant_id: UUID
    product_id: UUID
    seller_user_id: UUID
    slug: str
    title: str
    size: str
    price: Decimal
    mrp: Decimal
    stock: int
    image_url: str | None = None


@dataclass(slots=True, kw_only=True)
class CartLine:
    variant_id: UUID
    slug: str
    title: str
    size: str
    price: Decimal
    mrp: Decimal
    quantity: int
    line_total: Decimal
    stock: int
    image_url: str | None = None
    reduced_from: int | None = None  # asked for more than is in stock

    @property
    def is_out_of_stock(self) -> bool:
        return self.quantity == 0

    @property
    def max_quantity(self) -> int:
        return min(self.stock, MAX_QUANTITY_PER_LINE)


@dataclass(slots=True, kw_only=True)
class CartView:
    lines: list[CartLine] = field(default_factory=list)
    removed_count: int = 0  # items no longer on sale
    subtotal: Decimal = Decimal("0")
    delivery_charge: Decimal = Decimal("0")
    total: Decimal = Decimal("0")
    min_order_amount: Decimal = Decimal("0")
    free_delivery_above: Decimal | None = None
    is_store_open: bool = True
    closed_message: str | None = None
    cod_enabled: bool = True

    @property
    def payable_lines(self) -> list[CartLine]:
        return [line for line in self.lines if not line.is_out_of_stock]

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)

    @property
    def below_minimum_by(self) -> Decimal:
        return max(self.min_order_amount - self.subtotal, Decimal("0"))

    @property
    def free_delivery_gap(self) -> Decimal:
        if self.free_delivery_above is None or self.delivery_charge == 0:
            return Decimal("0")
        return max(self.free_delivery_above - self.subtotal, Decimal("0"))

    @property
    def can_check_out(self) -> bool:
        return bool(self.payable_lines) and self.is_store_open and self.cod_enabled and self.below_minimum_by == 0


@dataclass(slots=True, kw_only=True)
class OrderLine:
    id: UUID
    product_title: str
    variant_name: str
    mrp: Decimal
    unit_price: Decimal
    quantity: int
    line_total: Decimal
    product_id: UUID | None = None
    variant_id: UUID | None = None
    seller_user_id: UUID | None = None
    image_url: str | None = None


@dataclass(slots=True, kw_only=True)
class Order:
    id: UUID
    order_ref: str
    buyer_name: str
    buyer_phone: str
    address_line: str
    pincode: str
    subtotal: Decimal
    delivery_charge: Decimal
    total: Decimal
    lines: list[OrderLine] = field(default_factory=list)
    buyer_user_id: UUID | None = None
    city: str | None = None
    state: str | None = None
    notes: str | None = None
    checkout_token: str | None = None
    payment_method: PaymentMethod = PaymentMethod.COD
    payment_status: PaymentStatus = PaymentStatus.PENDING
    status: OrderStatus = OrderStatus.PLACED
    cancel_reason: str | None = None
    created_at: datetime | None = None

    @property
    def next_statuses(self) -> list[OrderStatus]:
        return [status for status in OrderStatus if self.status.can_move_to(status)]

    @property
    def item_count(self) -> int:
        return sum(line.quantity for line in self.lines)


@dataclass(slots=True, kw_only=True)
class OrderSummary:
    """Row of the seller's order list."""

    id: UUID
    order_ref: str
    buyer_name: str
    buyer_phone: str
    pincode: str
    total: Decimal
    status: OrderStatus
    payment_status: PaymentStatus
    item_count: int
    created_at: datetime | None = None
