"""
Control Center form input.

Blank form fields arrive as "" and mean "not given". `parse_form` turns Pydantic's
errors into one readable message per form field.

Python 3.13+
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Annotated, Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationError, model_validator

from app.modules.marketplace.domain.enums import (
    AnimalGender,
    AnimalStatus,
    BannerPlacement,
    EnquiryStatus,
    PregnancyStatus,
    ProductStatus,
)

Money = Annotated[Decimal, Field(max_digits=12, decimal_places=2, allow_inf_nan=False)]
Measure = Annotated[Decimal, Field(max_digits=6, decimal_places=2, allow_inf_nan=False)]
Count = Annotated[int, Field(ge=-2_000_000_000, le=2_000_000_000)]


class _Form(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)

    @model_validator(mode="before")
    @classmethod
    def _blank_is_missing(cls, data: Any) -> Any:
        if isinstance(data, dict):
            return {key: value for key, value in data.items() if value != ""}
        return data


class CategoryForm(_Form):
    name: str = Field(max_length=120)
    parent_id: UUID | None = None
    description: str | None = Field(default=None, max_length=2000)
    sort_order: Count = 0
    is_active: bool = False
    remove_image: bool = False


class AnimalTypeForm(_Form):
    name: str = Field(max_length=80)
    sort_order: Count = 0
    is_active: bool = False
    remove_image: bool = False


class AnimalBreedForm(_Form):
    animal_type_id: UUID
    name: str = Field(max_length=100)
    sort_order: Count = 0
    is_active: bool = False


class VariantForm(_Form):
    id: UUID | None = None
    name: str = Field(default="", max_length=100)
    sku: str | None = Field(default=None, max_length=100)
    mrp: Money
    price: Money
    stock: Count = 0
    low_stock_threshold: Count = 5
    is_default: bool = False
    is_active: bool = True


class ProductForm(_Form):
    category_id: UUID
    title: str = Field(max_length=200)
    brand: str | None = Field(default=None, max_length=120)
    short_description: str | None = Field(default=None, max_length=300)
    description: str | None = None
    status: ProductStatus = ProductStatus.DRAFT
    is_featured: bool = False
    is_trending: bool = False
    sort_order: Count = 0
    specifications: list[dict[str, str]] = []
    variants: list[VariantForm] = []
    keep_image_ids: list[UUID] = []


class AnimalForm(_Form):
    animal_type_id: UUID
    breed_id: UUID | None = None
    title: str = Field(max_length=200)
    gender: AnimalGender = AnimalGender.FEMALE
    price: Money
    is_negotiable: bool = False
    age_months: Count | None = None
    lactation_number: Count | None = None
    milk_litres_per_day: Measure | None = None
    fat_percent: Measure | None = None
    pregnancy_status: PregnancyStatus = PregnancyStatus.UNKNOWN
    pregnancy_months: Count | None = None
    calf_details: str | None = Field(default=None, max_length=300)
    health_notes: str | None = None
    vaccination_notes: str | None = None
    state: str | None = Field(default=None, max_length=100)
    district: str | None = Field(default=None, max_length=100)
    village: str | None = Field(default=None, max_length=100)
    description: str | None = None
    status: AnimalStatus = AnimalStatus.DRAFT
    is_featured: bool = False
    is_trending: bool = False
    sort_order: Count = 0
    keep_image_ids: list[UUID] = []


class EnquiryForm(_Form):
    buyer_name: str = Field(max_length=120)
    buyer_phone: str = Field(max_length=20)
    location: str | None = Field(default=None, max_length=200)
    message: str | None = Field(default=None, max_length=1000)


class CheckoutForm(_Form):
    buyer_name: str = Field(max_length=120)
    buyer_phone: str = Field(max_length=20)
    address_line: str = Field(max_length=500)
    city: str | None = Field(default=None, max_length=100)
    state: str | None = Field(default=None, max_length=100)
    pincode: str = Field(max_length=10)
    notes: str | None = Field(default=None, max_length=500)
    checkout_token: UUID
    expected_total: Money


class EnquiryUpdateForm(_Form):
    status: EnquiryStatus
    admin_notes: str | None = Field(default=None, max_length=1000)


class BannerForm(_Form):
    title: str = Field(max_length=150)
    subtitle: str | None = Field(default=None, max_length=255)
    cta_label: str | None = Field(default=None, max_length=60)
    cta_url: str | None = Field(default=None, max_length=500)
    placement: BannerPlacement = BannerPlacement.HOME_HERO
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    sort_order: Count = 0
    is_active: bool = False
    remove_mobile_image: bool = False


class HomeSectionForm(_Form):
    title: str = Field(max_length=120)
    subtitle: str | None = Field(default=None, max_length=255)
    category_id: UUID | None = None
    item_limit: Count = 8
    is_visible: bool = False


class TrendingTagForm(_Form):
    label: str = Field(max_length=80)
    url: str = Field(max_length=500)
    sort_order: Count = 0
    is_active: bool = False


class SettingsForm(_Form):
    store_name: str = Field(max_length=120)
    tagline: str | None = Field(default=None, max_length=200)
    support_phone: str | None = Field(default=None, max_length=20)
    whatsapp_number: str | None = Field(default=None, max_length=20)
    support_email: str | None = Field(default=None, max_length=200)
    address: str | None = Field(default=None, max_length=1000)
    delivery_charge: Money = Decimal("0")
    free_delivery_above: Money | None = None
    min_order_amount: Money = Decimal("0")
    cod_enabled: bool = False
    serviceable_pincodes: list[str] = []
    is_store_open: bool = False
    closed_message: str | None = Field(default=None, max_length=300)
    policies: dict[str, str] = {}
    remove_logo: bool = False


def _message(error: dict[str, Any]) -> str:
    kind = error["type"]
    if kind == "missing":
        return "This field is required."
    if kind == "string_too_long":
        return f"Keep this under {error['ctx']['max_length']} characters."
    if kind.startswith(("decimal", "int", "float")):
        return "Enter a valid number."
    if kind.startswith("uuid"):
        return "Choose a value from the list."
    if kind == "enum":
        return "Choose a value from the list."
    if kind.startswith("datetime"):
        return "Enter a valid date and time."
    return "This value is not valid."


def parse_form[T: BaseModel](model: type[T], data: dict[str, Any]) -> tuple[T | None, dict[str, str]]:
    """The validated form, or None and a message per field. Size rows are reported together."""
    try:
        return model.model_validate(data), {}
    except ValidationError as exc:
        errors: dict[str, str] = {}
        for error in exc.errors():
            location = error["loc"]
            if location and location[0] == "variants" and len(location) > 1:
                errors.setdefault("variants", f"Size row {int(location[1]) + 1}: {_message(error)}")
            elif location:
                errors.setdefault(str(location[0]), _message(error))
        return None, errors
