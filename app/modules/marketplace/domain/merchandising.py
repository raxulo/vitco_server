"""
Storefront content and store settings, all run by the Super Admin.

Python 3.13+
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from app.modules.marketplace.domain.enums import BannerPlacement, BannerState, HomeSectionType
from app.modules.marketplace.domain.links import is_safe_link

_PHONE = re.compile(r"^\+?\d{10,15}$")
_PINCODE = re.compile(r"^\d{6}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")

UNSAFE_LINK = "Use a site path such as /marketplace/products, or a full http(s) address."
POLICY_KEYS = ("shipping", "returns", "terms", "privacy")


@dataclass(slots=True, kw_only=True)
class Banner:
    id: UUID
    title: str
    image_url: str
    subtitle: str | None = None
    cta_label: str | None = None
    cta_url: str | None = None
    mobile_image_url: str | None = None
    placement: BannerPlacement = BannerPlacement.HOME_HERO
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    sort_order: int = 0
    is_active: bool = True
    created_by: UUID | None = None

    def state(self, now: datetime) -> BannerState:
        if not self.is_active:
            return BannerState.OFF
        if self.starts_at is not None and now < self.starts_at:
            return BannerState.SCHEDULED
        if self.ends_at is not None and now >= self.ends_at:
            return BannerState.EXPIRED
        return BannerState.LIVE

    def problems(self) -> dict[str, str]:
        problems: dict[str, str] = {}
        if not self.title.strip():
            problems["title"] = "Enter a title."
        if self.cta_url and not is_safe_link(self.cta_url):
            problems["cta_url"] = UNSAFE_LINK
        if self.cta_label and not self.cta_url:
            problems["cta_url"] = "Add the link this button opens."
        if self.starts_at and self.ends_at and self.ends_at <= self.starts_at:
            problems["ends_at"] = "The end must be after the start."
        return problems


@dataclass(slots=True, kw_only=True)
class HomeSection:
    id: UUID
    section_type: HomeSectionType
    title: str
    subtitle: str | None = None
    category_id: UUID | None = None
    item_limit: int = 8
    sort_order: int = 0
    is_visible: bool = True

    @property
    def can_delete(self) -> bool:
        """Built-in sections can only be hidden; there would be no way to add them back."""
        return self.section_type == HomeSectionType.CATEGORY_PRODUCTS

    def problems(self) -> dict[str, str]:
        problems: dict[str, str] = {}
        if not self.title.strip():
            problems["title"] = "Enter a heading."
        if not 1 <= self.item_limit <= 24:
            problems["item_limit"] = "Show between 1 and 24 items."
        if self.section_type == HomeSectionType.CATEGORY_PRODUCTS and self.category_id is None:
            problems["category_id"] = "Choose a category."
        return problems


@dataclass(slots=True, kw_only=True)
class TrendingTag:
    id: UUID
    label: str
    url: str
    sort_order: int = 0
    is_active: bool = True

    def problems(self) -> dict[str, str]:
        problems: dict[str, str] = {}
        if not self.label.strip():
            problems["label"] = "Enter a label."
        if not is_safe_link(self.url):
            problems["url"] = UNSAFE_LINK
        return problems


@dataclass(slots=True, kw_only=True)
class StoreSettings:
    store_name: str
    tagline: str | None = None
    logo_url: str | None = None
    support_phone: str | None = None
    whatsapp_number: str | None = None
    support_email: str | None = None
    address: str | None = None
    delivery_charge: Decimal = Decimal("0")
    free_delivery_above: Decimal | None = None
    min_order_amount: Decimal = Decimal("0")
    cod_enabled: bool = True
    serviceable_pincodes: list[str] = field(default_factory=list)
    is_store_open: bool = True
    closed_message: str | None = None
    policies: dict[str, str] = field(default_factory=dict)

    def delivery_for(self, subtotal: Decimal) -> Decimal:
        if self.free_delivery_above is not None and subtotal >= self.free_delivery_above:
            return Decimal("0")
        return self.delivery_charge

    def serves(self, pincode: str) -> bool:
        """An empty list means every pincode is served."""
        return not self.serviceable_pincodes or pincode in self.serviceable_pincodes

    def problems(self) -> dict[str, str]:
        problems: dict[str, str] = {}
        if not self.store_name.strip():
            problems["store_name"] = "Enter the store name."
        for name, value, label in (
            ("support_phone", self.support_phone, "Phone"),
            ("whatsapp_number", self.whatsapp_number, "WhatsApp number"),
        ):
            if value and not _PHONE.match(value):
                problems[name] = f"{label} must have 10 to 15 digits."
        if self.support_email and not _EMAIL.match(self.support_email):
            problems["support_email"] = "Enter a valid email address."
        for name, value, label in (
            ("delivery_charge", self.delivery_charge, "Delivery charge"),
            ("free_delivery_above", self.free_delivery_above, "Free delivery amount"),
            ("min_order_amount", self.min_order_amount, "Minimum order"),
        ):
            if value is not None and value < 0:
                problems[name] = f"{label} cannot be negative."
        bad = [code for code in self.serviceable_pincodes if not _PINCODE.match(code)]
        if bad:
            problems["serviceable_pincodes"] = f"Pincodes have 6 digits. Check: {', '.join(bad[:5])}"
        return problems
