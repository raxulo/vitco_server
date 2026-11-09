"""
Marketplace enums.

Python 3.13+
"""

from enum import StrEnum


class ProductStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    ARCHIVED = "ARCHIVED"


class AnimalStatus(StrEnum):
    DRAFT = "DRAFT"
    PUBLISHED = "PUBLISHED"
    RESERVED = "RESERVED"
    SOLD = "SOLD"
    ARCHIVED = "ARCHIVED"


class AnimalGender(StrEnum):
    FEMALE = "FEMALE"
    MALE = "MALE"


class PregnancyStatus(StrEnum):
    NOT_PREGNANT = "NOT_PREGNANT"
    PREGNANT = "PREGNANT"
    UNKNOWN = "UNKNOWN"


class EnquiryStatus(StrEnum):
    NEW = "NEW"
    CONTACTED = "CONTACTED"
    CLOSED = "CLOSED"


class OrderStatus(StrEnum):
    PLACED = "PLACED"
    CONFIRMED = "CONFIRMED"
    PACKED = "PACKED"
    OUT_FOR_DELIVERY = "OUT_FOR_DELIVERY"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"

    def can_move_to(self, target: "OrderStatus") -> bool:
        return target in _ORDER_TRANSITIONS[self]


_ORDER_TRANSITIONS: dict[OrderStatus, frozenset[OrderStatus]] = {
    OrderStatus.PLACED: frozenset({OrderStatus.CONFIRMED, OrderStatus.CANCELLED}),
    OrderStatus.CONFIRMED: frozenset({OrderStatus.PACKED, OrderStatus.CANCELLED}),
    OrderStatus.PACKED: frozenset({OrderStatus.OUT_FOR_DELIVERY, OrderStatus.CANCELLED}),
    OrderStatus.OUT_FOR_DELIVERY: frozenset({OrderStatus.DELIVERED, OrderStatus.CANCELLED}),
    OrderStatus.DELIVERED: frozenset(),
    OrderStatus.CANCELLED: frozenset(),
}


class PaymentMethod(StrEnum):
    COD = "COD"


class PaymentStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    REFUNDED = "REFUNDED"


class BannerPlacement(StrEnum):
    HOME_HERO = "HOME_HERO"
    HOME_MIDDLE = "HOME_MIDDLE"


class BannerState(StrEnum):
    LIVE = "Live"
    SCHEDULED = "Scheduled"
    EXPIRED = "Expired"
    OFF = "Off"


class HomeSectionType(StrEnum):
    CATEGORIES = "CATEGORIES"
    TRENDING = "TRENDING"
    FEATURED_ANIMALS = "FEATURED_ANIMALS"
    FEATURED_PRODUCTS = "FEATURED_PRODUCTS"
    MIDDLE_BANNERS = "MIDDLE_BANNERS"
    CATEGORY_PRODUCTS = "CATEGORY_PRODUCTS"
