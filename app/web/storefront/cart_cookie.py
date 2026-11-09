"""
The cart lives in a cookie as "variant:quantity" pairs. It holds no prices: the server
revalidates it on every page, so changing it by hand can change only what is in the cart.

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID

from starlette.requests import Request
from starlette.responses import Response

from app.modules.marketplace.domain.orders import MAX_CART_LINES, MAX_QUANTITY_PER_LINE

CART_COOKIE = "mkt_cart"
PLACED_COOKIE = "mkt_placed"
_COOKIE_PATH = "/marketplace"
_CART_MAX_AGE = 30 * 24 * 3600
_PLACED_MAX_AGE = 3600


def parse_cart(value: str | None) -> dict[UUID, int]:
    """Whatever cannot be understood is dropped, so a tampered cookie only loses items."""
    items: dict[UUID, int] = {}
    for pair in (value or "").split(",")[:MAX_CART_LINES]:
        variant, _, quantity = pair.partition(":")
        try:
            variant_id, count = UUID(variant), int(quantity)
        except ValueError:
            continue
        if count > 0:
            items[variant_id] = min(count, MAX_QUANTITY_PER_LINE)
    return items


def serialize_cart(items: dict[UUID, int]) -> str:
    return ",".join(f"{variant_id.hex}:{quantity}" for variant_id, quantity in items.items())


def cart_count(value: str | None) -> int:
    return sum(parse_cart(value).values())


def read_cart(request: Request) -> dict[UUID, int]:
    return parse_cart(request.cookies.get(CART_COOKIE))


def write_cart(request: Request, response: Response, items: dict[UUID, int]) -> None:
    if not items:
        response.delete_cookie(CART_COOKIE, path=_COOKIE_PATH)
        return
    response.set_cookie(
        CART_COOKIE, serialize_cart(items), max_age=_CART_MAX_AGE, path=_COOKIE_PATH,
        httponly=True, samesite="lax", secure=request.url.scheme == "https",
    )


def remember_placed_order(request: Request, response: Response, order_ref: str) -> None:
    response.set_cookie(
        PLACED_COOKIE, order_ref, max_age=_PLACED_MAX_AGE, path=_COOKIE_PATH,
        httponly=True, samesite="lax", secure=request.url.scheme == "https",
    )
