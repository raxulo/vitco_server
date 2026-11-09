"""
Control Center: orders.

Python 3.13+
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import Request
from starlette.responses import RedirectResponse, Response

from app.modules.dependencies import GetHandler
from app.modules.marketplace.application.command import MoveOrderCommand
from app.modules.marketplace.domain.enums import OrderStatus
from app.modules.marketplace.domain.exceptions import (
    InvalidOrderMoveException,
    ListingValidationException,
    OrderNotFoundException,
)
from app.web.marketplace_admin.controller import (
    _BASE,
    _PAGE_SIZE,
    _not_found,
    _page,
    _pagination,
    _parse_choice,
    _seller,
)


class OrderController:

    __slots__ = ()

    @staticmethod
    async def orders_page(request: Request, search: str = "", status: str = "", page: int = 1) -> Response:
        user = _seller(request)
        page = max(page, 1)
        items, total = await GetHandler.marketplace_order_handler(request).list_orders(
            user, search or None, _parse_choice(OrderStatus, status), (page - 1) * _PAGE_SIZE, _PAGE_SIZE
        )
        return _page(request, "orders.html", "orders", {
            "items": items, "search": search, "status": status, "statuses": list(OrderStatus),
            **_pagination(total, page),
        })

    @staticmethod
    async def _order_view(request: Request, order_id: UUID, **model: Any) -> Response:
        user = _seller(request)
        status_code = model.pop("status_code", 200)
        try:
            order = await GetHandler.marketplace_order_handler(request).get_order(user, order_id)
        except OrderNotFoundException:
            raise _not_found() from None
        return _page(request, "order_detail.html", "orders", {
            "order": order, "errors": {}, "OrderStatus": OrderStatus, **model,
        }, status_code)

    @staticmethod
    async def order_page(request: Request, order_id: UUID) -> Response:
        return await OrderController._order_view(request, order_id)

    @staticmethod
    async def order_move(request: Request, order_id: UUID) -> Response:
        user = _seller(request)
        form = await request.form()
        status = _parse_choice(OrderStatus, str(form.get("status", "")))
        if status is None:
            return await OrderController._order_view(request, order_id, page_error="Choose a valid status.", status_code=422)
        try:
            await GetHandler.marketplace_order_handler(request).move_order(MoveOrderCommand(
                owner=user, id=order_id, status=status, cancel_reason=str(form.get("cancel_reason", "")),
            ))
        except OrderNotFoundException:
            raise _not_found() from None
        except InvalidOrderMoveException as exc:
            return await OrderController._order_view(request, order_id, page_error=exc.message, status_code=409)
        except ListingValidationException as exc:
            return await OrderController._order_view(request, order_id, errors=exc.errors, status_code=422)
        return RedirectResponse(url=f"{_BASE}/orders/{order_id}?done=saved", status_code=303)
