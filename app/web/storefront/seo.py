"""
What search engines and link previews read: absolute links and structured data.

Python 3.13+
"""

from __future__ import annotations

from typing import Any
from urllib.parse import urlencode, urljoin

from fastapi import Request

from app.config.settings import settings
from app.modules.marketplace.domain.dto import AnimalDetail, ProductDetail
from app.modules.marketplace.domain.enums import AnimalStatus

_IN_STOCK = "https://schema.org/InStock"
_OUT_OF_STOCK = "https://schema.org/OutOfStock"
_SOLD_OUT = "https://schema.org/SoldOut"
_LIMITED = "https://schema.org/LimitedAvailability"


def store_url(request: Request, path: str, **query: Any) -> str:
    """An absolute link; empty query values are left out."""
    base = settings.MARKETPLACE_PUBLIC_URL.rstrip("/") or str(request.base_url).rstrip("/")
    link = urljoin(f"{base}/", path.rstrip("/") or "/")
    values = {key: value for key, value in query.items() if value not in (None, "")}
    return f"{link}?{urlencode(values)}" if values else link


def product_json_ld(request: Request, product: ProductDetail) -> dict[str, Any]:
    url = store_url(request, f"/marketplace/products/{product.slug}")
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": product.title,
        "url": url,
        "image": [store_url(request, image.url) for image in product.images],
        "offers": [
            {
                "@type": "Offer",
                "name": size.name,
                "url": url,
                "price": str(size.price),
                "priceCurrency": "INR",
                "availability": _IN_STOCK if size.in_stock else _OUT_OF_STOCK,
            }
            for size in product.sizes
        ],
    }
    if product.short_description or product.description:
        data["description"] = product.short_description or product.description
    if product.brand:
        data["brand"] = {"@type": "Brand", "name": product.brand}
    return data


def animal_json_ld(request: Request, animal: AnimalDetail) -> dict[str, Any]:
    url = store_url(request, f"/marketplace/animals/{animal.slug}")
    availability = {AnimalStatus.SOLD: _SOLD_OUT, AnimalStatus.RESERVED: _LIMITED}.get(animal.status, _IN_STOCK)
    data: dict[str, Any] = {
        "@context": "https://schema.org",
        "@type": "Product",
        "name": animal.title,
        "url": url,
        "category": animal.type_name,
        "image": [store_url(request, image.url) for image in animal.images],
        "offers": {
            "@type": "Offer",
            "url": url,
            "price": str(animal.price),
            "priceCurrency": "INR",
            "availability": availability,
        },
    }
    if animal.description:
        data["description"] = animal.description
    return data
