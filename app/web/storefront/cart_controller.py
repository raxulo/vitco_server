"""
Cart, checkout, order placed and tracking pages. Works without JavaScript.

Python 3.13+
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4

from fastapi import Request
from sqlalchemy.exc import OperationalError
from starlette.responses import RedirectResponse, Response

from app.modules.dependencies import GetHandler
from app.modules.marketplace.application.command import PlaceOrderCommand
from app.modules.marketplace.domain.enums import OrderStatus
from app.modules.marketplace.domain.exceptions import (
    ListingValidationException,
    OutOfStockException,
    TooManyRequestsException,
)
from app.modules.marketplace.domain.orders import MAX_CART_LINES, MAX_QUANTITY_PER_LINE, ORDER_STEPS
from app.modules.marketplace.presentation.requests import CheckoutForm, parse_form
from app.web.framework.renderer import Renderer
from app.web.storefront.cart_cookie import PLACED_COOKIE, read_cart, remember_placed_order, write_cart
from app.web.storefront.controller import check_rate_limit, too_many_requests

_CHECKOUT_FIELDS = ("buyer_name", "buyer_phone", "address_line", "city", "state", "pincode", "notes", "checkout_token", "expected_total")


def _variant_id(value: Any) -> UUID | None:
    try:
        return UUID(str(value))
    except ValueError:
        return None


def _quantity(value: Any, default: int) -> int:
    try:
        return min(max(int(str(value)), 0), MAX_QUANTITY_PER_LINE)
    except ValueError:
        return default


class CartController:

    __slots__ = ()

    # =========================================================
    # CART
    # =========================================================

    @staticmethod
    async def cart_page(request: Request) -> Response:
        items = read_cart(request)
        cart = await GetHandler.marketplace_order_handler(request).view_cart(items)
        frame = await GetHandler.storefront_handler(request).frame()
        response = Renderer.page(request=request, template="pages/store/cart.html", model={"frame": frame, "cart": cart})
        if cart.removed_count:
            # Items no longer on sale leave the cookie as well as the page
            write_cart(request, response, {line.variant_id: items[line.variant_id] for line in cart.lines})
        return response

    @staticmethod
    async def add_to_cart(request: Request) -> Response:
        form = await request.form()
        target = "/marketplace/checkout" if "buy_now" in form else "/marketplace/cart"
        response = RedirectResponse(url=target, status_code=303)
        variant_id = _variant_id(form.get("variant_id", ""))
        quantity = max(_quantity(form.get("quantity", "1"), 1), 1)
        if variant_id is None:
            return RedirectResponse(url="/marketplace/cart", status_code=303)

        items = read_cart(request)
        if variant_id in items or len(items) < MAX_CART_LINES:
            items[variant_id] = min(items.get(variant_id, 0) + quantity, MAX_QUANTITY_PER_LINE)
        write_cart(request, response, items)
        return response

    @staticmethod
    async def update_cart(request: Request) -> Response:
        form = await request.form()
        response = RedirectResponse(url="/marketplace/cart", status_code=303)
        variant_id = _variant_id(form.get("variant_id", ""))
        items = read_cart(request)
        if variant_id is not None and variant_id in items:
            quantity = 0 if "remove" in form else _quantity(form.get("quantity", ""), items[variant_id])
            if quantity:
                items[variant_id] = quantity
            else:
                del items[variant_id]
        write_cart(request, response, items)
        return response

    # =========================================================
    # CHECKOUT
    # =========================================================

    @staticmethod
    async def _checkout_view(
        request: Request,
        form: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> Response:
        cart = await GetHandler.marketplace_order_handler(request).view_cart(read_cart(request))
        if not cart.can_check_out:
            return RedirectResponse(url="/marketplace/cart", status_code=303)
        frame = await GetHandler.storefront_handler(request).frame()
        values = form or {}
        return Renderer.page(request=request, template="pages/store/checkout.html", model={
            "frame": frame, "cart": cart, "form": values, "errors": errors or {},
            # The token survives a validation error, so a later double submit is still caught
            "checkout_token": values.get("checkout_token") or str(uuid4()),
        }, status_code=status_code)

    @staticmethod
    async def checkout_page(request: Request) -> Response:
        return await CartController._checkout_view(request)

    @staticmethod
    async def checkout_post(request: Request) -> Response:
        try:
            check_rate_limit(request, "checkout")
        except TooManyRequestsException as exc:
            return await too_many_requests(request, exc)

        form = await request.form()
        data = {name: str(form.get(name, "")) for name in _CHECKOUT_FIELDS}
        parsed, errors = parse_form(CheckoutForm, data)
        if parsed is not None:
            user = getattr(request.state, "user", None)
            fields = parsed.model_dump()
            fields["checkout_token"] = str(fields["checkout_token"])
            try:
                order_ref = await GetHandler.marketplace_order_handler(request).place_order(PlaceOrderCommand(
                    items=read_cart(request), buyer_user_id=user.id if user else None, **fields,
                ))
            except ListingValidationException as exc:
                errors = exc.errors
            except OutOfStockException as exc:
                errors = {"form": exc.message}
            except OperationalError:
                # The database stayed busy past its wait; nothing was saved
                errors = {"form": "We are very busy right now and your order was not placed. Please try again."}
            else:
                response = RedirectResponse(url=f"/marketplace/order-placed/{order_ref}", status_code=303)
                write_cart(request, response, {})
                remember_placed_order(request, response, order_ref)
                return response
        return await CartController._checkout_view(request, data, errors, 422)

    @staticmethod
    async def order_placed_page(request: Request, order_ref: str) -> Response:
        """Only for the browser that placed the order; it shows no personal details anyway."""
        if request.cookies.get(PLACED_COOKIE) != order_ref:
            return RedirectResponse(url="/marketplace/track", status_code=302)
        order = await GetHandler.marketplace_order_handler(request).placed_order(order_ref)
        if order is None:
            return RedirectResponse(url="/marketplace/track", status_code=302)
        frame = await GetHandler.storefront_handler(request).frame()
        return Renderer.page(request=request, template="pages/store/order_placed.html", model={"frame": frame, "order": order})

    # =========================================================
    # TRACKING
    # =========================================================

    @staticmethod
    async def _track_view(request: Request, **model: Any) -> Response:
        frame = await GetHandler.storefront_handler(request).frame()
        return Renderer.page(request=request, template="pages/store/track.html", model={
            "frame": frame, "form": {}, "order": None, "not_found": False, "steps": ORDER_STEPS, **model,
        })

    @staticmethod
    async def track_page(request: Request) -> Response:
        return await CartController._track_view(request)

    @staticmethod
    async def track_post(request: Request) -> Response:
        """A POST, so the phone number stays out of URLs and logs."""
        try:
            check_rate_limit(request, "track")
        except TooManyRequestsException as exc:
            return await too_many_requests(request, exc)

        form = await request.form()
        order_ref = str(form.get("order_ref", ""))[:30]
        phone = str(form.get("phone", ""))[:20]
        order = await GetHandler.marketplace_order_handler(request).track(order_ref, phone)
        reached = ORDER_STEPS.index(order.status) if order and order.status != OrderStatus.CANCELLED else -1
        return await CartController._track_view(
            request, form={"order_ref": order_ref, "phone": phone}, order=order, not_found=order is None, reached=reached
        )
