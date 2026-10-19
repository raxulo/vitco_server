"""
Marketplace API Router

Provides REST APIs for Marketplace Catalog, Banners, Trending Tags,
Product Categories, Cattle/Livestock Animals, Products, and Orders.

All list endpoints strictly conform to standard response envelope format:
status, code, message, items, limit, offset, total, pages, next_page, has_more.

Python 3.13+
"""
import math
from typing import Any, List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Request

from app.api.v1.schemas.marketplace import (
    AnimalSchema,
    BannerSchema,
    CatalogData,
    CategorySchema,
    CreateAnimalRequest,
    CreateBannerRequest,
    CreateCategoryRequest,
    CreateOrderRequest,
    CreateProductRequest,
    CreateTrendingTagRequest,
    MarketplaceCatalogResponse,
    MarketplaceListResponse,
    MarketplaceSingleResponse,
    OrderSchema,
    ProductSchema,
    TrendingTagSchema,
    UpdateOrderStatusRequest,
)
from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.marketplace.domain.enums import AnimalType

router = APIRouter(
    prefix="/marketplace",
    tags=["Marketplace"],
)


def _compute_pagination(total: int, limit: int, offset: int):
    """Compute pagination metadata (pages, next_page, has_more)."""
    limit_val = max(1, limit)
    offset_val = max(0, offset)
    pages = math.ceil(total / limit_val) if total > 0 else 1
    current_page = (offset_val // limit_val) + 1
    has_more = (offset_val + limit_val) < total
    next_page = (current_page + 1) if has_more else None
    return {
        "limit": limit_val,
        "offset": offset_val,
        "total": total,
        "pages": pages,
        "next_page": next_page,
        "has_more": has_more,
    }


# --- 1. Catalog Summary API ---

@router.get("/catalog", response_model=CatalogData)
@router.get("", response_model=CatalogData)
@router.get("/", response_model=CatalogData)
async def get_marketplace_catalog(
    request: Request,
    category: str = Query("all", description="Category ID or slug filter ('all' for all)"),
    animal_type: str = Query("all", description="Animal type filter ('all', 'Cow', 'Buffalo', etc.)"),
    query: str = Query("", description="Search term"),
    sort_by: str = Query("default", description="Sort criteria ('price_asc', 'price_desc', 'newest')"),
):
    """Get Marketplace Catalog summary (banners, trending tags, categories, animals, products, animal_types)."""
    handler = GetHandler.marketplace_handler(request)

    try:
        raw_banners = await handler.get_banners()
        raw_tags = await handler.get_trending_tags()
        raw_categories = await handler.get_categories()
        raw_animals = await handler.get_animals(animal_type=animal_type, category=category, query=query, sort_by=sort_by)
        raw_products = await handler.get_products(category_id=category, query=query, sort_by=sort_by)
        animal_types = [t.value for t in AnimalType]
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch marketplace catalog: {str(exc)}")

    banners = [
        BannerSchema(
            id=str(b.get("id", "")),
            title=b.get("title", ""),
            subtitle=b.get("subtitle"),
            badge=b.get("badge"),
            image_url=b.get("image_url"),
            image=b.get("image"),
            cta_text=b.get("cta_text"),
            cta_target_url=b.get("cta_target_url") or b.get("cta_target"),
            bg_gradient=b.get("bg_gradient"),
            sort_order=b.get("sort_order", 0),
            is_active=b.get("is_active", True),
        )
        for b in raw_banners
    ]

    trending_tags = [
        TrendingTagSchema(
            id=str(t.get("id", "")),
            title=t.get("title", ""),
            url_path=t.get("url_path") or t.get("path", ""),
            sort_order=t.get("sort_order", 0),
            is_active=t.get("is_active", True),
        )
        for t in raw_tags
    ]

    categories = [
        CategorySchema(
            id=str(c.get("id", "")),
            name=c.get("name", "") or c.get("title", ""),
            slug=c.get("slug", "") or c.get("path_url", ""),
            description=c.get("description") or c.get("subtitle"),
            color=c.get("color"),
            icon=c.get("icon"),
            sort_order=c.get("sort_order", 0),
            is_active=c.get("is_active", True),
        )
        for c in raw_categories
    ]

    animals = [
        AnimalSchema(
            id=str(a.get("id", "")),
            seller_user_id=str(a.get("seller_user_id")) if a.get("seller_user_id") else None,
            seller_name=a.get("seller_name"),
            animal_type=str(a.get("animal_type") or a.get("type", "Cow")),
            title=a.get("title", ""),
            price=float(a.get("price", 0.0)),
            original_price=float(a.get("original_price")) if a.get("original_price") else None,
            breed=a.get("breed"),
            age_months=a.get("age_months"),
            milk_yield_liters=float(a.get("milk_yield_liters")) if a.get("milk_yield_liters") else None,
            lactation=a.get("lactation_num") if a.get("lactation_num") is not None else a.get("lactation"),
            discount_percent=float(a.get("discount_percent")) if a.get("discount_percent") else None,
            badge=a.get("badge"),
            description=a.get("description"),
            images=a.get("images") or [],
            is_active=a.get("is_active", True),
        )
        for a in raw_animals
    ]

    products = [
        ProductSchema(
            id=str(p.get("id", "")),
            category_id=str(p.get("category_id", "")),
            category_name=p.get("category_name"),
            title=p.get("title", ""),
            price=float(p.get("price", 0.0)),
            compare_at_price=float(p.get("compare_at_price")) if p.get("compare_at_price") else None,
            discount_percent=float(p.get("discount_percent")) if p.get("discount_percent") else None,
            brand_name=p.get("brand_name"),
            description=p.get("description"),
            badge=p.get("badge"),
            is_featured=p.get("is_featured", False),
            images=p.get("images") or [],
            is_active=p.get("is_active", True),
        )
        for p in raw_products
    ]

    return CatalogData(
        banners=banners,
        trending_tags=trending_tags,
        categories=categories,
        animals=animals,
        products=products,
        animal_types=animal_types,
    )


# --- 2. Cattle Animals API ---

@router.get("/animals", response_model=MarketplaceListResponse)
@router.post("/animals/list", response_model=MarketplaceListResponse)
async def list_animals(
    request: Request,
    animal_type: str = Query("all", description="Cow, Buffalo, etc."),
    category: str = Query("all", description="Category filter"),
    query: str = Query("", description="Search query"),
    sort_by: str = Query("default", description="Sort order"),
    limit: int = Query(20, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Fetch paginated list of Cattle / Livestock animals."""
    handler = GetHandler.marketplace_handler(request)

    try:
        raw_animals = await handler.get_animals(animal_type=animal_type, category=category, query=query, sort_by=sort_by)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch animals: {str(exc)}")

    total_count = len(raw_animals)
    paginated_raw = raw_animals[offset : offset + limit]

    items = [
        AnimalSchema(
            id=str(a.get("id", "")),
            seller_user_id=str(a.get("seller_user_id")) if a.get("seller_user_id") else None,
            seller_name=a.get("seller_name"),
            animal_type=str(a.get("animal_type") or a.get("type", "Cow")),
            title=a.get("title", ""),
            price=float(a.get("price", 0.0)),
            original_price=float(a.get("original_price")) if a.get("original_price") else None,
            breed=a.get("breed"),
            age_months=a.get("age_months"),
            milk_yield_liters=float(a.get("milk_yield_liters")) if a.get("milk_yield_liters") else None,
            lactation=a.get("lactation_num") if a.get("lactation_num") is not None else a.get("lactation"),
            discount_percent=float(a.get("discount_percent")) if a.get("discount_percent") else None,
            badge=a.get("badge"),
            description=a.get("description"),
            images=a.get("images") or [],
            is_active=a.get("is_active", True),
        )
        for a in paginated_raw
    ]

    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return MarketplaceListResponse(
        status=True,
        code=200,
        message="Animals fetched successfully",
        items=items,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
        type="animal",
    )


@router.post("/animals", response_model=MarketplaceSingleResponse)
async def create_animal(
    request: Request,
    payload: CreateAnimalRequest,
):
    """Post a new Cattle/Livestock Animal listing."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)

    data_dict = {
        "seller_user_id": str(user_state.id),
        "animal_type": payload.animal_type,
        "title": payload.title,
        "price": payload.price,
        "breed": payload.breed,
        "age_months": payload.age_months,
        "milk_yield_liters": payload.milk_yield_liters,
        "lactation": payload.lactation,
        "discount_percent": payload.discount_percent,
        "badge": payload.badge,
        "description": payload.description,
        "images": payload.images,
    }

    try:
        created = await handler.add_animal(data_dict)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create animal listing: {str(exc)}")

    return MarketplaceSingleResponse(
        status=True,
        code=200,
        message="Animal listing created successfully",
        type="animal",
        data=created,
    )


@router.delete("/animals/{id}")
async def delete_animal(
    request: Request,
    id: str,
):
    """Delete animal listing."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)

    try:
        await handler.delete_entity("animal", id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to delete animal listing: {str(exc)}")

    return {"status": True, "code": 200, "message": "Animal listing deleted successfully"}


# --- 3. Catalog Products API ---

@router.get("/products", response_model=MarketplaceListResponse)
@router.post("/products/list", response_model=MarketplaceListResponse)
async def list_products(
    request: Request,
    category_id: str = Query("all", description="Category ID filter"),
    query: str = Query("", description="Search term"),
    sort_by: str = Query("default", description="Sort order"),
    limit: int = Query(20, ge=1, le=500, description="Items per page"),
    offset: int = Query(0, ge=0, description="Offset for pagination"),
):
    """Fetch paginated list of catalog products."""
    handler = GetHandler.marketplace_handler(request)

    try:
        raw_products = await handler.get_products(category_id=category_id, query=query, sort_by=sort_by)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch products: {str(exc)}")

    total_count = len(raw_products)
    paginated_raw = raw_products[offset : offset + limit]

    items = [
        ProductSchema(
            id=str(p.get("id", "")),
            category_id=str(p.get("category_id", "")),
            category_name=p.get("category_name"),
            title=p.get("title", ""),
            price=float(p.get("price", 0.0)),
            compare_at_price=float(p.get("compare_at_price")) if p.get("compare_at_price") else None,
            discount_percent=float(p.get("discount_percent")) if p.get("discount_percent") else None,
            brand_name=p.get("brand_name"),
            description=p.get("description"),
            badge=p.get("badge"),
            is_featured=p.get("is_featured", False),
            images=p.get("images") or [],
            is_active=p.get("is_active", True),
        )
        for p in paginated_raw
    ]

    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return MarketplaceListResponse(
        status=True,
        code=200,
        message="Products fetched successfully",
        items=items,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
        type="product",
    )


@router.post("/products", response_model=MarketplaceSingleResponse)
async def create_product(
    request: Request,
    payload: CreateProductRequest,
):
    """Create a new catalog product."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)

    data_dict = {
        "category_id": str(payload.category_id),
        "title": payload.title,
        "price": payload.price,
        "compare_at_price": payload.compare_at_price,
        "brand_name": payload.brand_name,
        "description": payload.description,
        "badge": payload.badge,
        "is_featured": payload.is_featured,
        "images": payload.images,
    }

    try:
        created = await handler.add_product(data_dict)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create product: {str(exc)}")

    return MarketplaceSingleResponse(
        status=True,
        code=200,
        message="Product created successfully",
        type="product",
        data=created,
    )


@router.delete("/products/{id}")
async def delete_product(
    request: Request,
    id: str,
):
    """Delete product."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)

    try:
        await handler.delete_entity("product", id)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to delete product: {str(exc)}")

    return {"status": True, "code": 200, "message": "Product deleted successfully"}


# --- 4. Detail API ---

@router.get("/detail/{kind}/{item_id}", response_model=MarketplaceSingleResponse)
async def get_marketplace_item_detail(
    request: Request,
    kind: str,
    item_id: str,
):
    """
    Get detailed record for animal or product by ID.
    kind: 'animal' or 'product'
    """
    handler = GetHandler.marketplace_handler(request)
    kind_lower = kind.lower().strip()

    try:
        if kind_lower == "animal":
            animals = await handler.get_animals()
            matched = next((a for a in animals if str(a.get("id")) == item_id), None)
            if not matched:
                raise HTTPException(status_code=404, detail="Animal listing not found")
            return MarketplaceSingleResponse(
                status=True,
                code=200,
                message="Animal detail fetched successfully",
                type="animal",
                data=matched,
            )
        elif kind_lower in ("product", "item"):
            products = await handler.get_products()
            matched = next((p for p in products if str(p.get("id")) == item_id), None)
            if not matched:
                raise HTTPException(status_code=404, detail="Product not found")
            return MarketplaceSingleResponse(
                status=True,
                code=200,
                message="Product detail fetched successfully",
                type="product",
                data=matched,
            )
        else:
            raise HTTPException(status_code=400, detail="Invalid detail kind. Must be 'animal' or 'product'")
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch item detail: {str(exc)}")


# --- 5. Banners API ---

@router.get("/banners", response_model=MarketplaceListResponse)
async def list_banners(request: Request):
    """List all hero banners."""
    handler = GetHandler.marketplace_handler(request)
    banners = await handler.get_banners()
    return MarketplaceListResponse(
        status=True,
        code=200,
        message="Banners fetched successfully",
        items=banners,
        total=len(banners),
        pages=1,
        next_page=None,
        has_more=False,
        type="banner",
    )


@router.post("/banners", response_model=MarketplaceSingleResponse)
async def create_banner(request: Request, payload: CreateBannerRequest):
    """Create a new hero banner."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    banner_dict = payload.model_dump()
    try:
        created = await handler.add_banner(banner_dict)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create banner: {str(exc)}")

    return MarketplaceSingleResponse(
        status=True,
        code=200,
        message="Banner created successfully",
        type="banner",
        data=created,
    )


@router.delete("/banners/{id}")
async def delete_banner(request: Request, id: str):
    """Delete a hero banner."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    await handler.delete_entity("banner", id)
    return {"status": True, "code": 200, "message": "Banner deleted successfully"}


# --- 6. Trending Tags API ---

@router.get("/trending-tags", response_model=MarketplaceListResponse)
async def list_trending_tags(request: Request):
    """List all trending search tags."""
    handler = GetHandler.marketplace_handler(request)
    tags = await handler.get_trending_tags()
    return MarketplaceListResponse(
        status=True,
        code=200,
        message="Trending tags fetched successfully",
        items=tags,
        total=len(tags),
        pages=1,
        next_page=None,
        has_more=False,
        type="tag",
    )


@router.post("/trending-tags", response_model=MarketplaceSingleResponse)
async def create_trending_tag(request: Request, payload: CreateTrendingTagRequest):
    """Create a trending search tag."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    try:
        created = await handler.add_trending(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create trending tag: {str(exc)}")

    return MarketplaceSingleResponse(
        status=True,
        code=200,
        message="Trending tag created successfully",
        type="tag",
        data=created,
    )


@router.delete("/trending-tags/{id}")
async def delete_trending_tag(request: Request, id: str):
    """Delete trending search tag."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    await handler.delete_entity("trending", id)
    return {"status": True, "code": 200, "message": "Trending tag deleted successfully"}


# --- 7. Categories API ---

@router.get("/categories", response_model=MarketplaceListResponse)
async def list_categories(request: Request):
    """List product categories."""
    handler = GetHandler.marketplace_handler(request)
    categories = await handler.get_categories()
    return MarketplaceListResponse(
        status=True,
        code=200,
        message="Categories fetched successfully",
        items=categories,
        total=len(categories),
        pages=1,
        next_page=None,
        has_more=False,
        type="category",
    )


@router.post("/categories", response_model=MarketplaceSingleResponse)
async def create_category(request: Request, payload: CreateCategoryRequest):
    """Create product category."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    try:
        created = await handler.add_category(payload.model_dump())
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to create category: {str(exc)}")

    return MarketplaceSingleResponse(
        status=True,
        code=200,
        message="Category created successfully",
        type="category",
        data=created,
    )


@router.delete("/categories/{id}")
async def delete_category(request: Request, id: str):
    """Delete category."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    await handler.delete_entity("category", id)
    return {"status": True, "code": 200, "message": "Category deleted successfully"}


# --- 8. Orders API ---

@router.get("/orders", response_model=MarketplaceListResponse)
async def list_orders(
    request: Request,
    limit: int = Query(20, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """Fetch marketplace orders list."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    try:
        orders = await handler.get_orders_by_user_id(user_state.id)
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Failed to fetch orders: {str(exc)}")

    total_count = len(orders)
    paginated_orders = orders[offset : offset + limit]
    pag_meta = _compute_pagination(total=total_count, limit=limit, offset=offset)

    return MarketplaceListResponse(
        status=True,
        code=200,
        message="Orders fetched successfully",
        items=paginated_orders,
        limit=pag_meta["limit"],
        offset=pag_meta["offset"],
        total=pag_meta["total"],
        pages=pag_meta["pages"],
        next_page=pag_meta["next_page"],
        has_more=pag_meta["has_more"],
        type="order",
    )


@router.post("/orders", response_model=MarketplaceSingleResponse)
async def create_order(request: Request, payload: CreateOrderRequest):
    """Place a new Marketplace Order."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    data_dict = {
        "buyer_user_id": str(user_state.id),
        "item_type": payload.item_type,
        "item_id": str(payload.item_id),
        "quantity": payload.quantity,
        "delivery_address": payload.delivery_address,
        "contact_phone": payload.contact_phone,
        "notes": payload.notes,
    }

    try:
        created = await handler.create_order(data_dict)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to place order: {str(exc)}")

    return MarketplaceSingleResponse(
        status=True,
        code=200,
        message="Order placed successfully",
        type="order",
        data=created,
    )


@router.put("/orders/{id}/status", response_model=MarketplaceSingleResponse)
async def update_order_status(request: Request, id: str, payload: UpdateOrderStatusRequest):
    """Update order status."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    try:
        updated = await handler.update_order_status(id, payload.status)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Failed to update order status: {str(exc)}")

    return MarketplaceSingleResponse(
        status=True,
        code=200,
        message="Order status updated successfully",
        type="order",
        data=updated,
    )


@router.delete("/orders/{id}")
async def delete_order(request: Request, id: str):
    """Delete an order."""
    user_state: CurrentUser | None = getattr(request.state, "user", None)
    if not user_state:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.marketplace_handler(request)
    await handler.delete_order(id)
    return {"status": True, "code": 200, "message": "Order deleted successfully"}
