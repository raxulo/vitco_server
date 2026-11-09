"""
Public store API, for the mobile app (REQ-46). No login is needed (DECISION-019).

Python 3.13+
"""

from __future__ import annotations

import math
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.exc import OperationalError

from app.api.v1.schemas.marketplace import (
    AnimalCardOut,
    AnimalListRequest,
    AnimalPageOut,
    AnimalTypeOut,
    BreedOut,
    CartOut,
    CartQuoteRequest,
    CategoryOut,
    EnquiryRequest,
    HomeOut,
    OrderRequest,
    ProductCardOut,
    ProductListRequest,
    ProductPageOut,
    StoreOut,
    TrackedOrderOut,
    TrackRequest,
)
from app.modules.dependencies import GetHandler
from app.modules.marketplace.application.command import CreateEnquiryCommand, PlaceOrderCommand
from app.modules.marketplace.domain.dto import AnimalFilters, ProductFilters
from app.modules.marketplace.domain.exceptions import (
    AnimalNotFoundException,
    OrderNotFoundException,
    ProductNotFoundException,
    TooManyRequestsException,
)

router = APIRouter(prefix="/marketplace", tags=["Marketplace"])


# =========================================================
# ENVELOPES
# =========================================================


def _compute_pagination(total: int, limit: int, offset: int) -> dict[str, Any]:
    """Compute pagination metadata (pages, next_page, has_more)."""
    limit_val = max(1, limit)
    offset_val = max(0, offset)
    pages = math.ceil(total / limit_val) if total > 0 else 1
    current_page = (offset_val // limit_val) + 1
    has_more = (offset_val + limit_val) < total
    return {
        "limit": limit_val,
        "offset": offset_val,
        "total": total,
        "pages": pages,
        "next_page": (current_page + 1) if has_more else None,
        "has_more": has_more,
    }


def _dump(value: BaseModel) -> dict[str, Any]:
    return value.model_dump(mode="json")


def _record(data: BaseModel | dict[str, Any], message: str, code: int = 200) -> JSONResponse:
    payload = _dump(data) if isinstance(data, BaseModel) else data
    return JSONResponse(status_code=code, content={"status": True, "code": code, "message": message, "data": payload})


def _records(schema: type[BaseModel], rows: list[Any], total: int, limit: int, offset: int, message: str) -> JSONResponse:
    return JSONResponse(content={
        "status": True,
        "code": 200,
        "message": message,
        "items": [_dump(schema.model_validate(row)) for row in rows],
        **_compute_pagination(total, limit, offset),
    })


def _all_records(schema: type[BaseModel], rows: list[Any], message: str) -> JSONResponse:
    return _records(schema, rows, len(rows), max(len(rows), 1), 0, message)


def _too_many(error: TooManyRequestsException) -> JSONResponse:
    return JSONResponse(
        status_code=error.status_code,
        headers={"Retry-After": str(error.retry_after)},
        content={"success": False, "error": {"code": error.code, "message": error.message, "details": error.details}},
    )


def _limit(request: Request, action: str) -> JSONResponse | None:
    client = request.client.host if request.client else None
    try:
        GetHandler.store_rate_limiter(request).ensure_allowed(action, client)
    except TooManyRequestsException as error:
        return _too_many(error)
    return None


# =========================================================
# STORE
# =========================================================


@router.get("/store")
async def store_info(request: Request) -> JSONResponse:
    frame = await GetHandler.storefront_handler(request).frame()
    return _record(StoreOut.model_validate(frame.settings), "Store fetched successfully")


@router.get("/home")
async def home(request: Request) -> JSONResponse:
    page = await GetHandler.storefront_handler(request).home()
    return _record(
        HomeOut.model_validate({
            "store": StoreOut.model_validate(page.frame.settings),
            "trending_tags": page.frame.trending_tags,
            "hero_banners": page.hero_banners,
            "blocks": page.blocks,
        }, from_attributes=True),
        "Home fetched successfully",
    )


@router.get("/categories")
async def categories(request: Request) -> JSONResponse:
    frame = await GetHandler.storefront_handler(request).frame()
    return _all_records(CategoryOut, frame.categories, "Categories fetched successfully")


@router.get("/animal-types")
async def animal_types(request: Request) -> JSONResponse:
    frame = await GetHandler.storefront_handler(request).frame()
    return _all_records(AnimalTypeOut, frame.animal_types, "Animal types fetched successfully")


@router.get("/animal-types/{slug}/breeds")
async def breeds(request: Request, slug: str) -> JSONResponse:
    handler = GetHandler.storefront_handler(request)
    type_id = await handler.animal_type_id(slug)
    rows = await handler.breeds_of_type(type_id) if type_id else []
    return _all_records(BreedOut, rows, "Breeds fetched successfully")


# =========================================================
# PRODUCTS
# =========================================================


async def _list_products(request: Request, query: ProductListRequest) -> JSONResponse:
    handler = GetHandler.storefront_handler(request)
    category_ids = None
    if query.category:
        found = await handler.category_ids(query.category)
        category_ids = found[1] if found else set()  # an unknown category has no products
    items, total = await handler.list_products(ProductFilters(
        search=query.search or None, category_ids=category_ids, min_price=query.min_price, max_price=query.max_price,
        in_stock_only=query.in_stock, sort=query.sort, offset=query.offset, limit=query.limit,
    ))
    return _records(ProductCardOut, items, total, query.limit, query.offset, "Products fetched successfully")


@router.get("/products")
async def products(request: Request, query: Annotated[ProductListRequest, Query()]) -> JSONResponse:
    return await _list_products(request, query)


@router.post("/products/list")
async def products_list(request: Request, query: ProductListRequest) -> JSONResponse:
    return await _list_products(request, query)


@router.get("/products/{slug}")
async def product(request: Request, slug: str) -> JSONResponse:
    found = await GetHandler.storefront_handler(request).product_page(slug)
    if found is None:
        raise ProductNotFoundException()
    detail, related = found
    return _record(
        ProductPageOut.model_validate({"product": detail, "related": related}, from_attributes=True),
        "Product fetched successfully",
    )


# =========================================================
# ANIMALS
# =========================================================


async def _list_animals(request: Request, query: AnimalListRequest) -> JSONResponse:
    handler = GetHandler.storefront_handler(request)
    type_id: UUID | None = None
    if query.type:
        type_id = await handler.animal_type_id(query.type)
        if type_id is None:
            return _records(AnimalCardOut, [], 0, query.limit, query.offset, "Animals fetched successfully")
    items, total = await handler.list_animals(AnimalFilters(
        search=query.search or None, animal_type_id=type_id, breed_id=query.breed, min_price=query.min_price,
        max_price=query.max_price, min_milk=query.min_milk, lactation=query.lactation,
        location=query.location or None, sort=query.sort, offset=query.offset, limit=query.limit,
    ))
    return _records(AnimalCardOut, items, total, query.limit, query.offset, "Animals fetched successfully")


@router.get("/animals")
async def animals(request: Request, query: Annotated[AnimalListRequest, Query()]) -> JSONResponse:
    return await _list_animals(request, query)


@router.post("/animals/list")
async def animals_list(request: Request, query: AnimalListRequest) -> JSONResponse:
    return await _list_animals(request, query)


@router.get("/animals/{slug}")
async def animal(request: Request, slug: str) -> JSONResponse:
    found = await GetHandler.storefront_handler(request).animal_page(slug)
    if found is None:
        raise AnimalNotFoundException()
    detail, similar = found
    return _record(
        AnimalPageOut.model_validate({"animal": detail, "similar": similar}, from_attributes=True),
        "Animal fetched successfully",
    )


@router.post("/animals/{slug}/enquiries")
async def create_enquiry(request: Request, slug: str, body: EnquiryRequest) -> JSONResponse:
    if (limited := _limit(request, "enquiry")) is not None:
        return limited
    await GetHandler.storefront_handler(request).create_enquiry(
        CreateEnquiryCommand(animal_slug=slug, **body.model_dump())
    )
    return _record({"received": True}, "Enquiry sent successfully", 201)


# =========================================================
# CART & ORDERS
# =========================================================


@router.post("/cart/quote")
async def cart_quote(request: Request, body: CartQuoteRequest) -> JSONResponse:
    """The app keeps the cart; this returns today's prices, stock and totals for it."""
    cart = await GetHandler.marketplace_order_handler(request).view_cart(
        {item.variant_id: item.quantity for item in body.items}
    )
    return _record(CartOut.model_validate(cart), "Cart priced successfully")


@router.post("/orders")
async def create_order(request: Request, body: OrderRequest) -> JSONResponse:
    if (limited := _limit(request, "checkout")) is not None:
        return limited
    user = getattr(request.state, "user", None)
    fields = body.model_dump(exclude={"items", "checkout_token"})
    handler = GetHandler.marketplace_order_handler(request)
    try:
        order_ref = await handler.place_order(PlaceOrderCommand(
            items={item.variant_id: item.quantity for item in body.items},
            checkout_token=str(body.checkout_token),
            buyer_user_id=user.id if user else None,
            **fields,
        ))
    except OperationalError:
        return JSONResponse(status_code=503, headers={"Retry-After": "5"}, content={
            "success": False,
            "error": {"code": "MARKETPLACE_BUSY", "message": "We are very busy and the order was not placed. Please try again.", "details": {}},
        })
    order = await handler.placed_order(order_ref)
    return _record(
        {"order_ref": order_ref, "total": str(order.total), "status": order.status.value},
        "Order placed successfully",
        201,
    )


@router.post("/orders/track")
async def track_order(request: Request, body: TrackRequest) -> JSONResponse:
    if (limited := _limit(request, "track")) is not None:
        return limited
    order = await GetHandler.marketplace_order_handler(request).track(body.order_ref, body.phone)
    if order is None:
        raise OrderNotFoundException()  # the same answer for a wrong reference and a wrong phone
    return _record(TrackedOrderOut.model_validate(order), "Order fetched successfully")
