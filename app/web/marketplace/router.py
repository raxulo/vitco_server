"""
Marketplace Web Router

Defines APIRouter endpoints for:
- GET /marketplace/setup - SuperAdmin setup page
- GET /marketplace - Marketplace browsing catalog page
- GET /marketplace/detail/{kind}/{item_id} - Item detail view
"""

from __future__ import annotations

from fastapi import APIRouter, Request, Query
from fastapi.responses import HTMLResponse

from app.web.marketplace.controller import MarketplaceWebController

marketplace_router = APIRouter(
    prefix="/marketplace",
    tags=["Web Marketplace"],
)


@marketplace_router.get("/setup", response_class=HTMLResponse)
async def setup_page(request: Request) -> HTMLResponse:
    """SuperAdmin Only Setup Page for Banners, Trending Tags, Categories, and Animal Types."""
    return await MarketplaceWebController.setup_page(request)


@marketplace_router.get("", response_class=HTMLResponse)
@marketplace_router.get("/", response_class=HTMLResponse)
async def index_page(
    request: Request,
    category: str = Query("all"),
    animal_type: str = Query("all"),
    query: str = Query(""),
    sort_by: str = Query("default"),
) -> HTMLResponse:
    """Browse Marketplace page accessible to all users."""
    return await MarketplaceWebController.index_page(
        request=request,
        category=category,
        animal_type=animal_type,
        query=query,
        sort_by=sort_by,
    )


@marketplace_router.get("/detail/{kind}/{item_id}", response_class=HTMLResponse)
async def detail_page(request: Request, kind: str, item_id: str) -> HTMLResponse:
    """Detailed view for Animals or Products."""
    return await MarketplaceWebController.detail_page(request, kind=kind, item_id=item_id)


# =========================================================
# Setup Form Actions (POST)
# =========================================================
@marketplace_router.post("/setup/category/add")
async def add_category_action(request: Request):
    return await MarketplaceWebController.add_category_action(request)


@marketplace_router.post("/setup/category/update/{item_id}")
async def update_category_action(request: Request, item_id: str):
    return await MarketplaceWebController.update_category_action(request, item_id=item_id)


@marketplace_router.post("/setup/banner/add")
async def add_banner_action(request: Request):
    return await MarketplaceWebController.add_banner_action(request)


@marketplace_router.post("/setup/banner/update/{item_id}")
async def update_banner_action(request: Request, item_id: str):
    return await MarketplaceWebController.update_banner_action(request, item_id=item_id)


@marketplace_router.post("/setup/trending/add")
async def add_trending_action(request: Request):
    return await MarketplaceWebController.add_trending_action(request)


@marketplace_router.post("/setup/trending/update/{item_id}")
async def update_trending_action(request: Request, item_id: str):
    return await MarketplaceWebController.update_trending_action(request, item_id=item_id)


@marketplace_router.post("/setup/animal/add")
async def add_animal_action(request: Request):
    return await MarketplaceWebController.add_animal_action(request)


@marketplace_router.post("/setup/animal/update/{item_id}")
async def update_animal_action(request: Request, item_id: str):
    return await MarketplaceWebController.update_animal_action(request, item_id=item_id)


@marketplace_router.post("/setup/product/add")
async def add_product_action(request: Request):
    return await MarketplaceWebController.add_product_action(request)


@marketplace_router.post("/setup/{entity}/delete/{item_id}")
async def delete_action(request: Request, entity: str, item_id: str):
    return await MarketplaceWebController.delete_action(request, entity=entity, item_id=item_id)


# =========================================================
# Order Management Routes (POST)
# =========================================================
@marketplace_router.post("/order/create")
async def create_order_action(request: Request):
    return await MarketplaceWebController.create_order_action(request)


@marketplace_router.post("/setup/order/status/{item_id}")
async def update_order_status_action(request: Request, item_id: str):
    return await MarketplaceWebController.update_order_status_action(request, item_id=item_id)


@marketplace_router.post("/setup/order/delete/{item_id}")
async def delete_order_action(request: Request, item_id: str):
    return await MarketplaceWebController.delete_order_action(request, item_id=item_id)

