"""
Public store pages (DECISION-019, DECISION-020).

Query values come from shared or hand-edited URLs, so anything invalid is ignored
instead of producing an error page.

Python 3.13+
"""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any
from urllib.parse import quote, urlencode
from uuid import UUID

from fastapi import Request
from starlette.responses import RedirectResponse, Response

from app.modules.dependencies import GetHandler
from app.modules.marketplace.application.command import CreateEnquiryCommand
from app.modules.marketplace.domain.dto import AnimalFilters, ProductFilters
from app.modules.marketplace.domain.exceptions import (
    AnimalNotAvailableException,
    AnimalNotFoundException,
    ListingValidationException,
    TooManyRequestsException,
)
from app.modules.marketplace.presentation.requests import EnquiryForm, parse_form
from app.web.framework.renderer import Renderer
from app.web.storefront.seo import animal_json_ld, product_json_ld

_PAGE_SIZE = 24
_SEARCH_PREVIEW = 8
_MAX_FILTER_NUMBER = Decimal("9999999999")
_POLICY_TITLES = {
    "shipping": "Shipping",
    "returns": "Returns and refunds",
    "terms": "Terms",
    "privacy": "Privacy",
}
_PRODUCT_SORTS = (
    ("newest", "Newest"),
    ("price_asc", "Price: low to high"),
    ("price_desc", "Price: high to low"),
)
_ANIMAL_SORTS = (*_PRODUCT_SORTS, ("milk_desc", "Milk per day: highest"))
_LACTATIONS = ((1, "First"), (2, "Second"), (3, "Third"), (4, "Fourth or later"))


def _text(request: Request, name: str, max_length: int = 100) -> str:
    return request.query_params.get(name, "").strip()[:max_length]


def _number(request: Request, name: str) -> Decimal | None:
    try:
        value = Decimal(request.query_params.get(name, "").strip())
    except InvalidOperation:
        return None
    return value if value.is_finite() and 0 <= value <= _MAX_FILTER_NUMBER else None


def _page_number(request: Request) -> int:
    try:
        return min(max(int(request.query_params.get("page", "1")), 1), 100_000)
    except ValueError:
        return 1


def _uuid(value: str) -> UUID | None:
    try:
        return UUID(value)
    except ValueError:
        return None


def _sort(request: Request, options: tuple[tuple[str, str], ...]) -> str:
    value = request.query_params.get("sort", "")
    return value if value in {key for key, _ in options} else "newest"


def _query(values: dict[str, Any]) -> str:
    """Filters for the pager links; empty ones are left out so URLs stay short."""
    return urlencode({key: value for key, value in values.items() if value not in (None, "", False)})


def _pages(total: int) -> int:
    return max((total + _PAGE_SIZE - 1) // _PAGE_SIZE, 1)


def _whatsapp_url(number: str | None, message: str) -> str | None:
    if not number:
        return None
    digits = number.lstrip("+")
    if len(digits) == 10:
        digits = f"91{digits}"
    return f"https://wa.me/{digits}?text={quote(message)}"


async def too_many_requests(request: Request, error: TooManyRequestsException) -> Response:
    """Used by every store form: asks the visitor to wait, without losing the page they know."""
    frame = await GetHandler.storefront_handler(request).frame()
    response = Renderer.page(
        request=request, template="pages/store/too_many.html", model={"frame": frame}, status_code=429
    )
    response.headers["Retry-After"] = str(error.retry_after)
    return response


def check_rate_limit(request: Request, action: str) -> None:
    client = request.client.host if request.client else None
    GetHandler.store_rate_limiter(request).ensure_allowed(action, client)


class StorefrontController:

    __slots__ = ()

    @staticmethod
    async def _not_found(request: Request) -> Response:
        frame = await GetHandler.storefront_handler(request).frame()
        return Renderer.page(request=request, template="pages/store/not_found.html", model={"frame": frame}, status_code=404)

    # =========================================================
    # HOME
    # =========================================================

    @staticmethod
    async def home_page(request: Request) -> Response:
        home = await GetHandler.storefront_handler(request).home()
        return Renderer.page(
            request=request,
            template="pages/store/home.html",
            model={"frame": home.frame, "hero_banners": home.hero_banners, "blocks": home.blocks},
        )

    # =========================================================
    # PRODUCTS
    # =========================================================

    @staticmethod
    async def products_page(request: Request) -> Response:
        handler = GetHandler.storefront_handler(request)
        page = _page_number(request)
        search, category = _text(request, "search"), _text(request, "category")
        min_price, max_price = _number(request, "min_price"), _number(request, "max_price")
        in_stock = request.query_params.get("in_stock") == "1"
        sort = _sort(request, _PRODUCT_SORTS)

        found = await handler.category_ids(category) if category else None
        items, total = await handler.list_products(ProductFilters(
            search=search or None,
            category_ids=found[1] if found else None,
            min_price=min_price,
            max_price=max_price,
            in_stock_only=in_stock,
            sort=sort,
            offset=(page - 1) * _PAGE_SIZE,
            limit=_PAGE_SIZE,
        ))
        category = category if found else ""
        active = sum(1 for value in (search, category, min_price, max_price, in_stock) if value not in ("", None, False))
        return Renderer.page(request=request, template="pages/store/products.html", model={
            "frame": await handler.frame(), "items": items, "total": total, "page": page, "pages": _pages(total),
            "search_query": search, "search": search, "category": category, "category_name": found[0] if found else None,
            "min_price": min_price, "max_price": max_price, "in_stock": in_stock, "sort": sort, "sorts": _PRODUCT_SORTS,
            "active_filters": active,
            "query": _query({
                "search": search, "category": category, "min_price": min_price, "max_price": max_price,
                "in_stock": "1" if in_stock else "", "sort": "" if sort == "newest" else sort,
            }),
        })

    @staticmethod
    async def product_page(request: Request, slug: str) -> Response:
        handler = GetHandler.storefront_handler(request)
        found = await handler.product_page(slug)
        if found is None:
            return await StorefrontController._not_found(request)
        product, related = found
        return Renderer.page(request=request, template="pages/store/product_detail.html", model={
            "frame": await handler.frame(), "product": product, "related": related,
            "json_ld": product_json_ld(request, product),
        })

    # =========================================================
    # ANIMALS
    # =========================================================

    @staticmethod
    async def animals_page(request: Request) -> Response:
        handler = GetHandler.storefront_handler(request)
        page = _page_number(request)
        search, type_slug = _text(request, "search"), _text(request, "type")
        location = _text(request, "location")
        min_price, max_price = _number(request, "min_price"), _number(request, "max_price")
        min_milk = _number(request, "min_milk")
        sort = _sort(request, _ANIMAL_SORTS)

        lactation_text = request.query_params.get("lactation", "")
        lactation = int(lactation_text) if lactation_text in {"1", "2", "3", "4"} else None

        type_id = await handler.animal_type_id(type_slug) if type_slug else None
        type_slug = type_slug if type_id else ""
        breeds = await handler.breeds_of_type(type_id) if type_id else []
        breed_id = _uuid(request.query_params.get("breed", ""))
        if breed_id not in {breed.id for breed in breeds}:
            breed_id = None

        items, total = await handler.list_animals(AnimalFilters(
            search=search or None,
            animal_type_id=type_id,
            breed_id=breed_id,
            min_price=min_price,
            max_price=max_price,
            min_milk=min_milk,
            lactation=lactation,
            location=location or None,
            sort=sort,
            offset=(page - 1) * _PAGE_SIZE,
            limit=_PAGE_SIZE,
        ))
        active = sum(
            1 for value in (search, type_slug, breed_id, min_price, max_price, min_milk, lactation, location)
            if value not in ("", None)
        )
        return Renderer.page(request=request, template="pages/store/animals.html", model={
            "frame": await handler.frame(), "items": items, "total": total, "page": page, "pages": _pages(total),
            "search_query": search, "search": search, "type_slug": type_slug, "breeds": breeds, "breed_id": breed_id,
            "min_price": min_price, "max_price": max_price, "min_milk": min_milk, "lactation": lactation,
            "lactations": _LACTATIONS, "location": location, "sort": sort, "sorts": _ANIMAL_SORTS, "active_filters": active,
            "query": _query({
                "search": search, "type": type_slug, "breed": breed_id, "min_price": min_price, "max_price": max_price,
                "min_milk": min_milk, "lactation": lactation, "location": location,
                "sort": "" if sort == "newest" else sort,
            }),
        })

    @staticmethod
    async def _animal_view(
        request: Request,
        slug: str,
        form: dict[str, Any] | None = None,
        errors: dict[str, str] | None = None,
        status_code: int = 200,
    ) -> Response:
        handler = GetHandler.storefront_handler(request)
        found = await handler.animal_page(slug)
        if found is None:
            return await StorefrontController._not_found(request)
        animal, similar = found
        frame = await handler.frame()
        return Renderer.page(request=request, template="pages/store/animal_detail.html", model={
            "frame": frame, "animal": animal, "similar": similar, "form": form or {}, "errors": errors or {},
            "json_ld": animal_json_ld(request, animal),
            "enquiry_sent": request.query_params.get("enquiry") == "sent",
            "whatsapp_url": _whatsapp_url(
                frame.settings.whatsapp_number, f"Hello, I am interested in {animal.title}: {request.url_for('animal_page', slug=slug)}"
            ),
        }, status_code=status_code)

    @staticmethod
    async def animal_page(request: Request, slug: str) -> Response:
        return await StorefrontController._animal_view(request, slug)

    @staticmethod
    async def enquiry_post(request: Request, slug: str) -> Response:
        try:
            check_rate_limit(request, "enquiry")
        except TooManyRequestsException as exc:
            return await too_many_requests(request, exc)

        form = await request.form()
        data = {name: str(form.get(name, "")) for name in ("buyer_name", "buyer_phone", "location", "message")}
        done = RedirectResponse(url=f"/marketplace/animals/{slug}?enquiry=sent#enquiry", status_code=303)

        # Only bots fill this hidden field. They see the normal success, and nothing is saved.
        if str(form.get("website", "")).strip():
            return done

        parsed, errors = parse_form(EnquiryForm, data)
        if parsed is not None:
            try:
                await GetHandler.storefront_handler(request).create_enquiry(
                    CreateEnquiryCommand(animal_slug=slug, **parsed.model_dump())
                )
                return done
            except ListingValidationException as exc:
                errors = exc.errors
            except AnimalNotFoundException:
                return await StorefrontController._not_found(request)
            except AnimalNotAvailableException as exc:
                errors = {"form": exc.message}
        return await StorefrontController._animal_view(request, slug, data, errors, 422)

    # =========================================================
    # SEARCH & POLICIES
    # =========================================================

    @staticmethod
    async def search_page(request: Request) -> Response:
        handler = GetHandler.storefront_handler(request)
        query = _text(request, "q")
        if not query:
            return RedirectResponse(url="/marketplace", status_code=302)
        animals, animal_total = await handler.list_animals(AnimalFilters(search=query, limit=_SEARCH_PREVIEW))
        products, product_total = await handler.list_products(ProductFilters(search=query, limit=_SEARCH_PREVIEW))
        return Renderer.page(request=request, template="pages/store/search.html", model={
            "frame": await handler.frame(), "search_query": query, "animals": animals, "animal_total": animal_total,
            "products": products, "product_total": product_total, "query": _query({"search": query}),
        })

    @staticmethod
    async def policy_page(request: Request, key: str) -> Response:
        frame = await GetHandler.storefront_handler(request).frame()
        text = frame.settings.policies.get(key)
        if key not in _POLICY_TITLES or not text:
            return await StorefrontController._not_found(request)
        return Renderer.page(request=request, template="pages/store/policy.html", model={
            "frame": frame, "title": _POLICY_TITLES[key], "text": text,
        })
