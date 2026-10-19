"""
Marketplace Web Controller

Handles Web HTML rendering for:
1. /marketplace/setup - SuperAdmin Only Setup Center (Category, Banner, Trending, Animal Type)
2. /marketplace - Public/All Users Marketplace Catalog & Detail Views
"""

from __future__ import annotations

from uuid import UUID
from typing import Any
from fastapi import Request, HTTPException, status
from starlette.responses import Response

from app.web.framework.renderer import Renderer
from app.modules.dependencies import GetHandler
from app.modules.marketplace.application.handler import MarketplaceCommandHandler
from app.modules.marketplace.application.command import (
    CreateBannerCommand,
    UpdateBannerCommand,
    CreateProductCategoryCommand,
    UpdateProductCategoryCommand,
    UpdateTrendingTagCommand,
)
from app.modules.marketplace.domain.enums import AnimalType


def check_super_admin(request: Request) -> bool:
    """Verifies if the current authenticated session user is a SuperAdmin (role == 1 or 0)."""
    user = getattr(request.state, "user", None)
    if not user:
        return False
    # Role 1 represents SuperAdmin in QuickYee, 0 is Admin
    user_role = getattr(user, "role", None)
    is_super = getattr(user, "is_superadmin", False)
    return is_super or str(user_role) in ("1", "0") or user_role in (0, 1)


def check_can_post(request: Request) -> bool:
    """Verifies if the user is authenticated and NOT a Farmer (Role 6). All other logged-in users can manage posts."""
    user = getattr(request.state, "user", None)
    if not user:
        return False
    user_role = getattr(user, "role", None)
    if user_role is None:
        return False
    # Role 6 represents FARMER
    return str(user_role) != "6" and user_role != 6


class MarketplaceWebController:
    """Web Controller for Marketplace pages and admin setup center."""

    # =========================================================
    # 1. SETUP PAGE (/marketplace/setup)
    # =========================================================
    @staticmethod
    async def setup_page(request: Request) -> Response:
        user = getattr(request.state, "user", None)
        if not user:
            return Renderer.redirect("/login")

        if not check_can_post(request):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Access Denied: Farmers are not authorized to access the marketplace setup center.",
            )

        is_super = check_super_admin(request)
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        
        banners = await handler.get_banners()
        trending_tags = await handler.get_trending_tags()
        categories = await handler.get_categories()
        animals = await handler.get_animals()
        products = await handler.get_products()
        orders = await handler.get_orders()
        animal_types = [t.value for t in AnimalType]

        return Renderer.page(
            request=request,
            template="pages/marketplace/setup.html",
            model={
                "active_tab": "setup",
                "banners": banners,
                "trending_tags": trending_tags,
                "categories": categories,
                "animals": animals,
                "products": products,
                "orders": orders,
                "animal_types": animal_types,
                "is_superadmin": is_super,
                "can_post": True,
                "page_title": "Marketplace Setup Center" if is_super else "Marketplace Posts Setup",
            },
        )

    # =========================================================
    # 2. ALL USERS MARKETPLACE CATALOG PAGE (/marketplace)
    # =========================================================
    @staticmethod
    async def index_page(
        request: Request,
        category: str = "all",
        animal_type: str = "all",
        query: str = "",
        sort_by: str = "default",
    ) -> Response:
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)

        banners = await handler.get_banners()
        trending_tags = await handler.get_trending_tags()
        categories = await handler.get_categories()
        animals = await handler.get_animals(animal_type=animal_type, category=category, query=query, sort_by=sort_by)
        products = await handler.get_products(category_id=category, query=query, sort_by=sort_by)
        animal_types = [t.value for t in AnimalType]

        return Renderer.page(
            request=request,
            template="pages/marketplace/index.html",
            model={
                "banners": banners,
                "trending_tags": trending_tags,
                "categories": categories,
                "animals": animals,
                "products": products,
                "animal_types": animal_types,
                "selected_category": category,
                "selected_animal_type": animal_type,
                "search_query": query,
                "sort_by": sort_by,
                "is_superadmin": check_super_admin(request),
                "can_post": check_can_post(request),
                "page_title": "Vitco Marketplace",
            },
        )

    # =========================================================
    # 3. DETAIL PAGE (/marketplace/detail/{kind}/{id})
    # =========================================================
    @staticmethod
    async def detail_page(request: Request, kind: str, item_id: str) -> Response:
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)

        item = None
        if kind == "animal":
            animals = await handler.get_animals()
            item = next((a for a in animals if str(a["id"]) == str(item_id)), animals[0] if animals else None)
        else:
            products = await handler.get_products()
            item = next((p for p in products if str(p["id"]) == str(item_id)), products[0] if products else None)

        title = item.get("title", "Item Details") if item else "Details"

        return Renderer.page(
            request=request,
            template="pages/marketplace/detail.html",
            model={
                "kind": kind,
                "item": item,
                "is_superadmin": check_super_admin(request),
                "can_post": check_can_post(request),
                "page_title": f"{title} - Marketplace",
            },
        )

    # =========================================================
    # 4. FORM ACTIONS (/marketplace/setup/...)
    # =========================================================
    @staticmethod
    async def add_category_action(request: Request) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required for category setup")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        name = str(form.get("name", "")).strip()
        icon_file = form.get("icon_file") or form.get("image_file")
        _slug = str(form.get("slug", "")).strip().lower().replace(" ", "-") or name.lower().replace(" ", "-")
        if name:
            cmd = CreateProductCategoryCommand(
                name=name,
                slug=_slug,
                description=str(form.get("description", "")).strip(),
                icon_file=icon_file if (icon_file and getattr(icon_file, "filename", None)) else None,
                color=str(form.get("color", "")).strip() or "#059669",
            )
            await handler.add_category(cmd)
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def update_category_action(request: Request, item_id: str) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required for category setup")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        name = str(form.get("name", "")).strip()
        icon_file = form.get("icon_file") or form.get("image_file")
        icon = str(form.get("icon", "")).strip() or None

        if name:
            cmd = UpdateProductCategoryCommand(
                id=item_id,
                name=name,
                slug=str(form.get("slug", "")).strip().lower().replace(" ", "-") or name.lower().replace(" ", "-"),
                description=str(form.get("description", "")).strip(),
                icon=icon,
                icon_file=icon_file if (icon_file and getattr(icon_file, "filename", None)) else None,
                color=str(form.get("color", "")).strip() or "#059669",
            )
            await handler.update_category(item_id, cmd)
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def add_banner_action(request: Request) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required for banner setup")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()
        
        image_file = form.get("image_file")
        image_url = str(form.get("image_url", "")).strip()

        if title:
            cmd = CreateBannerCommand(
                title=title,
                subtitle=str(form.get("subtitle", "")).strip(),
                badge=str(form.get("badge", "")).strip() or "NEW",
                image_url=image_url or None,
                image_file=image_file if (image_file and getattr(image_file, "filename", None)) else None,
                cta_text=str(form.get("cta_text", "")).strip() or "Explore Now",
                cta_target_url=str(form.get("cta_target_url", "")).strip() or "/marketplace",
                bg_gradient=str(form.get("bg_gradient", "")).strip() or "linear-gradient(to right, #4facfe 0%, #00f2fe 100%)",
            )
            await handler.add_banner(cmd)
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def update_banner_action(request: Request, item_id: str) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required for banner setup")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()
        
        image_file = form.get("image_file")
        image_url = str(form.get("image_url", "")).strip()

        if title:
            cmd = UpdateBannerCommand(
                id=item_id,
                title=title,
                subtitle=str(form.get("subtitle", "")).strip(),
                badge=str(form.get("badge", "")).strip() or "NEW",
                image_url=image_url or None,
                image_file=image_file if (image_file and getattr(image_file, "filename", None)) else None,
                cta_text=str(form.get("cta_text", "")).strip() or "Explore Now",
                cta_target_url=str(form.get("cta_target_url", "")).strip() or "/marketplace",
                bg_gradient=str(form.get("bg_gradient", "")).strip() or "linear-gradient(to right, #4facfe 0%, #00f2fe 100%)",
            )
            await handler.update_banner(item_id, cmd)
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def add_trending_action(request: Request) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required for trending setup")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()
        if title:
            await handler.add_trending_tag({
                "title": title,
                "url_path": str(form.get("url_path", "")).strip() or "/marketplace",
            })
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def update_trending_action(request: Request, item_id: str) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required for trending setup")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()
        if title:
            cmd = UpdateTrendingTagCommand(
                id=UUID(item_id) if isinstance(item_id, str) else item_id,
                title=title,
                url_path=str(form.get("url_path", "")).strip() or "/marketplace",
            )
            await handler.update_trending_tag(item_id, cmd)
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def add_animal_action(request: Request) -> Response:
        if not check_can_post(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage posts")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None)
        
        image_files = form.getlist("image_files")
        if not image_files:
            single_f = form.get("image_file")
            if single_f and getattr(single_f, "filename", None):
                image_files = [single_f]

        if title:
            await handler.add_animal_listing({
                "seller_user_id": user_id,
                "title": title,
                "animal_type": str(form.get("animal_type", "Cow")).strip() or "Cow",
                "breed": str(form.get("breed", "")).strip() or "Desi Breed",
                "age_months": int(form.get("age_months", 24) or 24),
                "milk_yield_liters": float(form.get("milk_yield_liters", 12.0) or 12.0),
                "lactation": int(form.get("lactation", 1) or 1),
                "price": float(form.get("price", 50000.0) or 50000.0),
                "badge": str(form.get("badge", "")).strip() or "VERIFIED MILK",
                "description": str(form.get("description", "")).strip(),
                "image_files": image_files,
            })
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def update_animal_action(request: Request, item_id: str) -> Response:
        if not check_can_post(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage posts")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()
        user = getattr(request.state, "user", None)
        user_id = getattr(user, "id", None)

        image_files = form.getlist("image_files")
        if not image_files:
            single_f = form.get("image_file")
            if single_f and getattr(single_f, "filename", None):
                image_files = [single_f]

        if title:
            await handler.update_animal_listing(item_id, {
                "seller_user_id": user_id,
                "title": title,
                "animal_type": str(form.get("animal_type", "Cow")).strip() or "Cow",
                "breed": str(form.get("breed", "")).strip() or "Desi Breed",
                "age_months": int(form.get("age_months", 24) or 24),
                "milk_yield_liters": float(form.get("milk_yield_liters", 12.0) or 12.0),
                "lactation": int(form.get("lactation", 1) or 1),
                "price": float(form.get("price", 50000.0) or 50000.0),
                "badge": str(form.get("badge", "")).strip() or "VERIFIED MILK",
                "description": str(form.get("description", "")).strip(),
                "image_files": image_files,
            })
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def add_product_action(request: Request) -> Response:
        if not check_can_post(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage posts")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()

        image_files = form.getlist("image_files")
        if not image_files:
            single_f = form.get("image_file")
            if single_f and getattr(single_f, "filename", None):
                image_files = [single_f]

        if title:
            await handler.add_product_listing({
                "title": title,
                "category_id": form.get("category_id"),
                "brand_name": str(form.get("brand_name", "")).strip() or "Vitco Feeds",
                "price": float(form.get("price", 1450.0) or 1450.0),
                "compare_at_price": float(form.get("compare_at_price", 1650.0) or 1650.0),
                "badge": str(form.get("badge", "")).strip() or "BESTSELLER",
                "unit": str(form.get("unit", "")).strip() or "50 kg Bag",
                "description": str(form.get("description", "")).strip(),
                "image_files": image_files,
            })
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def update_product_action(request: Request, item_id: str) -> Response:
        if not check_can_post(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to manage posts")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        title = str(form.get("title", "")).strip()

        image_files = form.getlist("image_files")
        if not image_files:
            single_f = form.get("image_file")
            if single_f and getattr(single_f, "filename", None):
                image_files = [single_f]

        if title:
            await handler.update_product_listing(item_id, {
                "title": title,
                "category_id": form.get("category_id"),
                "brand_name": str(form.get("brand_name", "")).strip() or "Vitco Feeds",
                "price": float(form.get("price", 1450.0) or 1450.0),
                "compare_at_price": float(form.get("compare_at_price", 1650.0) or 1650.0),
                "badge": str(form.get("badge", "")).strip() or "BESTSELLER",
                "unit": str(form.get("unit", "")).strip() or "50 kg Bag",
                "description": str(form.get("description", "")).strip(),
                "image_files": image_files,
            })
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def delete_action(request: Request, entity: str, item_id: str) -> Response:
        if entity in ("category", "banner", "trending"):
            if not check_super_admin(request):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required for setup deletion")
        elif entity in ("animal", "product"):
            if not check_can_post(request):
                raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Not authorized to delete posts")
        else:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid entity type")

        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        if entity == "category":
            await handler.delete_category(item_id)
        elif entity == "banner":
            await handler.delete_banner(item_id)
        elif entity == "trending":
            await handler.delete_trending_tag(item_id)
        elif entity == "animal":
            await handler.delete_animal_listing(item_id)
        elif entity == "product":
            await handler.delete_product_listing(item_id)
        return Renderer.redirect("/marketplace/setup")

    # =========================================================
    # 5. ORDER ACTIONS
    # =========================================================
    @staticmethod
    async def create_order_action(request: Request) -> Response:
        try:
            data = await request.json()
        except Exception:
            form = await request.form()
            data = dict(form)

        from uuid import uuid4
        from starlette.responses import JSONResponse

        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        order_data = {
            "order_ref": str(data.get("order_ref", "")).strip() or f"VIT-{uuid4().hex[:6].upper()}",
            "buyer_name": str(data.get("buyer_name", "")).strip() or "Customer",
            "buyer_phone": str(data.get("buyer_phone", "")).strip() or "-",
            "delivery_address": str(data.get("delivery_address", "")).strip() or "-",
            "payment_method": str(data.get("payment_method", "cod")).strip(),
            "total_amount": float(data.get("total_amount", 0.0) or 0.0),
            "items_json": data.get("items") or [],
            "status": "PENDING",
        }
        res = await handler.create_order(order_data)
        return JSONResponse({"success": True, "order": res})

    @staticmethod
    async def update_order_status_action(request: Request, item_id: str) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required")
        form = await request.form()
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        new_status = str(form.get("status", "PENDING")).strip().upper()
        await handler.update_order_status(item_id, new_status)
        return Renderer.redirect("/marketplace/setup")

    @staticmethod
    async def delete_order_action(request: Request, item_id: str) -> Response:
        if not check_super_admin(request):
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="SuperAdmin required")
        handler: MarketplaceCommandHandler = GetHandler.marketplace_handler(request)
        await handler.delete_order(item_id)
        return Renderer.redirect("/marketplace/setup")


