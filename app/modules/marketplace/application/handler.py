"""
Marketplace Application Handler

Command & Query Handlers for:
- Hero Banners
- Trending Search Tags
- Browse Category Cards
- Product Categories
- Livestock Animal Listings
- Catalog Products & Offers

Follows QuickYee enterprise CQRS pattern with DatabaseManager transaction support.
"""

from __future__ import annotations

from typing import Any
from uuid import UUID, uuid4
from datetime import date, datetime
from decimal import Decimal

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.media.application.services import MediaService, MediaUrlService
from app.modules.media.domain.enums import MediaCategory
from app.modules.marketplace.infrastructure.models import (
    MarketplaceBannerModel,
    MarketplaceTrendingTagModel,
    MarketplaceBrowseCategoryModel,
    ProductCategoryModel,
    AnimalTypeModel,
    MarketplaceProductModel,
    ProductVariantModel,
    ProductOfferModel,
    InventoryModel,
    AnimalModel,
)
from app.modules.marketplace.infrastructure.repository import MarketplaceRepository
from app.modules.marketplace.application.command import (
    CreateBannerCommand,
    UpdateBannerCommand,
    DeleteBannerCommand,
    CreateTrendingTagCommand,
    UpdateTrendingTagCommand,
    DeleteTrendingTagCommand,
    CreateBrowseCategoryCommand,
    UpdateBrowseCategoryCommand,
    DeleteBrowseCategoryCommand,
    CreateProductCategoryCommand,
    UpdateProductCategoryCommand,
    DeleteProductCategoryCommand,
    CreateProductCommand,
    UpdateProductCommand,
    DeleteProductCommand,
    CreateProductOfferCommand,
    CreateAnimalListingCommand,
    UpdateAnimalListingCommand,
    DeleteAnimalListingCommand,
    CreateAnimalCommand,
    UpdateAnimalCommand,
    DeleteAnimalCommand,
)


class MarketplaceCommandHandler:
    """Enterprise Command & Query Handler for Marketplace module."""

    __slots__ = (
        "_database",
        "_repository",
        "_media_service",
    )

    def __init__(
        self,
        repository: MarketplaceRepository,
        database: DatabaseManager | None = None,
        media_service: MediaService | None = None,
    ) -> None:
        self._database = database
        self._repository = repository
        self._media_service = media_service

    # =========================================================
    # 1. HERO BANNERS HANDLERS
    # =========================================================

    async def get_banners(self) -> list[dict[str, Any]]:
        banners = await self._repository.get_banners()
        return [
            {
                "id": str(b.id),
                "title": b.title,
                "subtitle": b.subtitle,
                "badge": b.badge,
                "image_url": getattr(b, "image_url", None),
                "image": getattr(b, "image_url", None) or "https://images.unsplash.com/photo-1542838132-92c53300491e?auto=format&fit=crop&w=1200&q=80",
                "cta_text": b.cta_text,
                "cta_target_url": b.cta_target_url,
                "cta_target": b.cta_target_url,
                "bg_gradient": b.bg_gradient,
                "sort_order": b.sort_order,
                "is_active": b.is_active,
            }
            for b in banners
        ]

    async def handle_create_banner(self, command: CreateBannerCommand) -> MarketplaceBannerModel:
        if not command.image_file or not getattr(command.image_file, "filename", None):
            raise ValidationException("Image file is required to create a banner.")

        banner_id = uuid4()
        image_url = command.image_url
        if self._media_service:
            try:
                media = await self._media_service.upload_image(
                    file=command.image_file,
                    category=MediaCategory.BANNER,
                    entity_id=banner_id,
                )
                if media and getattr(media, "storage_key", None):
                    image_url = MediaUrlService.build(media.storage_key)
            except Exception:
                pass
        if not image_url and self._repository:
            uploaded_url = await self._repository.process_image_upload(
                file=command.image_file,
                category=MediaCategory.BANNER,
                entity_id=banner_id,
            )
            if uploaded_url:
                image_url = uploaded_url

        data = {
            "id": banner_id,
            "title": command.title,
            "subtitle": command.subtitle,
            "badge": command.badge,
            "image_url": image_url,
            "cta_text": command.cta_text,
            "cta_target_url": command.cta_target_url,
            "bg_gradient": command.bg_gradient,
            "sort_order": command.sort_order,
            "is_active": True,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_banner(data)
        return await self._repository.save_banner(data)

    async def handle_update_banner(self, command: UpdateBannerCommand) -> MarketplaceBannerModel:
        banner_id = UUID(str(command.id)) if isinstance(command.id, str) else command.id
        image_url = command.image_url
        if command.image_file and getattr(command.image_file, "filename", None):
            if self._media_service:
                try:
                    media = await self._media_service.upload_image(
                        file=command.image_file,
                        category=MediaCategory.BANNER,
                        entity_id=banner_id,
                    )
                    if media and getattr(media, "storage_key", None):
                        image_url = MediaUrlService.build(media.storage_key)
                except Exception:
                    pass
            if not image_url and self._repository:
                uploaded_url = await self._repository.process_image_upload(
                    file=command.image_file,
                    category=MediaCategory.BANNER,
                    entity_id=banner_id,
                )
                if uploaded_url:
                    image_url = uploaded_url

        data = {
            "title": command.title,
            "subtitle": command.subtitle,
            "badge": command.badge,
            "image_url": image_url,
            "cta_text": command.cta_text,
            "cta_target_url": command.cta_target_url,
            "bg_gradient": command.bg_gradient,
            "sort_order": command.sort_order,
            "is_active": command.is_active,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_banner(data, banner_id=banner_id)
        return await self._repository.save_banner(data, banner_id=banner_id)

    async def handle_delete_banner(self, command: DeleteBannerCommand) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_banner(command.id)
        return await self._repository.delete_banner(command.id)

    # UI Helper methods
    async def add_banner(self, command: CreateBannerCommand | dict[str, Any]) -> dict[str, Any]:
        if isinstance(command, dict):
            command = CreateBannerCommand(
                title=command.get("title", ""),
                subtitle=command.get("subtitle"),
                badge=command.get("badge"),
                image_url=command.get("image_url"),
                image_file=command.get("image_file"),
                cta_text=command.get("cta_text"),
                cta_target_url=command.get("cta_target_url"),
                bg_gradient=command.get("bg_gradient"),
                sort_order=command.get("sort_order", 0),
            )
        banner = await self.handle_create_banner(command)
        return {
            "id": str(banner.id),
            "title": banner.title,
            "subtitle": banner.subtitle,
            "badge": banner.badge,
            "image_url": getattr(banner, "image_url", None),
            "cta_text": banner.cta_text,
            "cta_target_url": banner.cta_target_url,
            "bg_gradient": banner.bg_gradient,
            "sort_order": banner.sort_order,
            "is_active": banner.is_active,
        }

    async def update_banner(self, banner_id: str, command: UpdateBannerCommand | dict[str, Any]) -> dict[str, Any]:
        if isinstance(command, dict):
            command = UpdateBannerCommand(
                id=UUID(banner_id) if isinstance(banner_id, str) else banner_id,
                title=command.get("title", ""),
                subtitle=command.get("subtitle"),
                badge=command.get("badge"),
                image_url=command.get("image_url"),
                image_file=command.get("image_file"),
                cta_text=command.get("cta_text"),
                cta_target_url=command.get("cta_target_url"),
                bg_gradient=command.get("bg_gradient"),
                sort_order=command.get("sort_order", 0),
                is_active=command.get("is_active", True),
            )
        banner = await self.handle_update_banner(command)
        return {
            "id": str(banner.id),
            "title": banner.title,
            "subtitle": banner.subtitle,
            "badge": banner.badge,
            "image_url": getattr(banner, "image_url", None),
            "cta_text": banner.cta_text,
            "cta_target_url": banner.cta_target_url,
            "bg_gradient": banner.bg_gradient,
            "sort_order": banner.sort_order,
            "is_active": banner.is_active,
        }

    async def delete_banner(self, banner_id: str) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_banner(banner_id)
        return await self._repository.delete_banner(banner_id)

    # =========================================================
    # 2. TRENDING TAGS HANDLERS
    # =========================================================
    async def get_trending_tags(self) -> list[dict[str, Any]]:
        tags = await self._repository.get_trending_tags()
        return [
            {
                "id": str(t.id),
                "title": t.title,
                "label": t.title,
                "target_url": t.url_path,
                "url_path": t.url_path,
                "sort_order": t.sort_order,
            }
            for t in tags
        ]

    async def handle_create_trending_tag(self, command: CreateTrendingTagCommand) -> MarketplaceTrendingTagModel:
        data = {
            "title": command.title,
            "url_path": command.url_path,
            "sort_order": command.sort_order,
            "is_active": True,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_trending_tag(data)
        return await self._repository.save_trending_tag(data)

    async def handle_update_trending_tag(self, command: UpdateTrendingTagCommand) -> MarketplaceTrendingTagModel:
        data = {
            "title": command.title,
            "url_path": command.url_path,
            "sort_order": command.sort_order,
            "is_active": command.is_active,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_trending_tag(data, tag_id=command.id)
        return await self._repository.save_trending_tag(data, tag_id=command.id)

    async def handle_delete_trending_tag(self, command: DeleteTrendingTagCommand) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_trending_tag(command.id)
        return await self._repository.delete_trending_tag(command.id)

    async def add_trending_tag(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._database:
            async with self._database.transaction():
                res = await self._repository.save_trending_tag(data)
        else:
            res = await self._repository.save_trending_tag(data)
        return {"id": str(res.id), **data}

    async def update_trending_tag(self, tag_id: str, command: UpdateTrendingTagCommand | dict[str, Any]) -> dict[str, Any]:
        if isinstance(command, dict):
            command = UpdateTrendingTagCommand(
                id=UUID(tag_id) if isinstance(tag_id, str) else tag_id,
                title=command.get("title") or command.get("label", ""),
                url_path=command.get("url_path") or command.get("target_url", "/marketplace"),
                sort_order=command.get("sort_order", 0),
                is_active=command.get("is_active", True),
            )
        tag = await self.handle_update_trending_tag(command)
        return {
            "id": str(tag.id),
            "title": tag.title,
            "label": tag.title,
            "url_path": tag.url_path,
            "target_url": tag.url_path,
            "sort_order": tag.sort_order,
        }

    async def delete_trending_tag(self, tag_id: str) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_trending_tag(tag_id)
        return await self._repository.delete_trending_tag(tag_id)

    # =========================================================
    # 3. PRODUCT & BROWSE CATEGORIES HANDLERS
    # =========================================================
    async def get_categories(self) -> list[dict[str, Any]]:
        cats = await self._repository.get_product_categories()
        return [
            {
                "id": str(c.id),
                "name": c.name,
                "title": c.name,
                "slug": c.slug,
                "description": c.description,
                "subtitle": c.description,
                "icon": c.icon or "fa-solid fa-layer-group",
                "color": c.color or "#059669",
                "path_url": f"/marketplace/products?category={c.slug}",
            }
            for c in cats
        ]

    async def handle_create_category(self, command: CreateProductCategoryCommand) -> ProductCategoryModel:
        cat_id = uuid4()
        icon = None
        if command.icon_file and getattr(command.icon_file, "filename", None):
            if self._media_service:
                try:
                    media = await self._media_service.upload_image(
                        file=command.icon_file,
                        category=MediaCategory.CATEGORY,
                        entity_id=cat_id,
                    )
                    if media and getattr(media, "storage_key", None):
                        icon = MediaUrlService.build(media.storage_key)
                except Exception:
                    pass
            if not icon and self._repository:
                uploaded_url = await self._repository.process_image_upload(
                    file=command.icon_file,
                    category=MediaCategory.CATEGORY,
                    entity_id=cat_id,
                )
                if uploaded_url:
                    icon = uploaded_url

        data = {
            "id": cat_id,
            "name": command.name,
            "slug": command.slug,
            "parent_id": command.parent_id,
            "description": command.description,
            "icon": icon,
            "color": command.color,
            "sort_order": command.sort_order,
            "is_active": True,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_product_category(data)
        return await self._repository.save_product_category(data)

    async def handle_update_category(self, command: UpdateProductCategoryCommand) -> ProductCategoryModel:
        cat_id = UUID(str(command.id)) if isinstance(command.id, str) else command.id
        icon = command.icon
        if command.icon_file and getattr(command.icon_file, "filename", None):
            if self._media_service:
                try:
                    media = await self._media_service.upload_image(
                        file=command.icon_file,
                        category=MediaCategory.CATEGORY,
                        entity_id=cat_id,
                    )
                    if media and getattr(media, "storage_key", None):
                        icon = MediaUrlService.build(media.storage_key)
                except Exception:
                    pass
            if not icon and self._repository:
                uploaded_url = await self._repository.process_image_upload(
                    file=command.icon_file,
                    category=MediaCategory.CATEGORY,
                    entity_id=cat_id,
                )
                if uploaded_url:
                    icon = uploaded_url

        data = {
            "name": command.name,
            "slug": command.slug,
            "parent_id": command.parent_id,
            "description": command.description,
            "icon": icon,
            "color": command.color,
            "sort_order": command.sort_order,
            "is_active": command.is_active,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_product_category(data, cat_id=cat_id)
        return await self._repository.save_product_category(data, cat_id=cat_id)

    async def handle_delete_category(self, command: DeleteProductCategoryCommand) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_product_category(command.id)
        return await self._repository.delete_product_category(command.id)

    async def add_category(self, command: CreateProductCategoryCommand) -> dict[str, Any]:
        res = await self.handle_create_category(command)
        return {"id": str(res.id), "name": res.name, "slug": res.slug, "icon": res.icon, "color": res.color}

    async def update_category(self, category_id: str, command: UpdateProductCategoryCommand | dict[str, Any]) -> dict[str, Any]:
        if isinstance(command, dict):
            command = UpdateProductCategoryCommand(
                id=UUID(category_id) if isinstance(category_id, str) else category_id,
                name=command.get("name", ""),
                slug=command.get("slug", ""),
                parent_id=command.get("parent_id"),
                description=command.get("description"),
                icon=command.get("icon"),
                icon_file=command.get("icon_file") or command.get("image_file"),
                color=command.get("color"),
                sort_order=command.get("sort_order", 0),
                is_active=command.get("is_active", True),
            )
        res = await self.handle_update_category(command)
        return {"id": str(res.id), "name": res.name, "slug": res.slug, "icon": res.icon, "color": res.color}

    async def delete_category(self, category_id: str) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_product_category(category_id)
        return await self._repository.delete_product_category(category_id)

    # =========================================================
    # 4. CATTLE & LIVESTOCK ANIMAL LISTINGS HANDLERS
    # =========================================================
    async def get_animals(self, animal_type: str = "all", category: str = "all", state: str = "All India", query: str = "", sort_by: str = "default") -> list[dict[str, Any]]:
        animals = await self._repository.get_animals()
        results = []
        default_img = "https://images.unsplash.com/photo-1570042707222-7728b9d033a3?auto=format&fit=crop&w=600&q=80"
        
        cat_lower = str(category or "all").strip().lower()
        is_animal_cat = (
            cat_lower == "all"
            or any(kw in cat_lower for kw in ["pashu", "cattle", "livestock", "animal", "cow", "buffalo", "goat", "sheep"])
        )

        for item in animals:
            try:
                if len(item) == 3:
                    a, user, atype = item
                elif len(item) == 2:
                    a, user = item
                    atype = None
                else:
                    a, user, atype = item[0], None, None
            except (TypeError, ValueError):
                a, user, atype = item, None, None

            seller_name = getattr(user, "name", None) or "Breeder / Farmer"
            seller_mobile = getattr(user, "mobile", None) or "+91 98765 43210"
            animal_type_name = getattr(atype, "name", None) or "Cow"
            atype_slug = getattr(atype, "slug", "") or ""

            # 1. Filter by Category selection
            if not is_animal_cat:
                cat_name_match = (
                    cat_lower in animal_type_name.lower()
                    or cat_lower in (getattr(a, "breed", "") or "").lower()
                    or cat_lower in (getattr(a, "title", "") or "").lower()
                    or cat_lower in str(getattr(a, "animal_type_id", "")).lower()
                )
                if not cat_name_match:
                    continue

            # 2. Filter by Animal Type tab selection (e.g., Cow, Buffalo, Goat, Sheep)
            if animal_type and animal_type.strip().lower() != "all":
                target_type = animal_type.strip().lower()
                atype_lower = animal_type_name.lower()
                breed_lower = (getattr(a, "breed", "") or "").lower()
                title_lower = (getattr(a, "title", "") or "").lower()
                type_slug_lower = str(atype_slug).lower()

                if (target_type not in atype_lower and 
                    target_type not in breed_lower and 
                    target_type not in title_lower and 
                    target_type not in type_slug_lower):
                    continue

            # 3. Filter by Search Query
            if query and query.strip():
                q = query.strip().lower()
                searchable = f"{a.title} {a.breed} {a.description} {animal_type_name} {seller_name}".lower()
                if q not in searchable:
                    continue

            imgs = getattr(a, "images", None) or []
            main_img = getattr(a, "image_url", None)
            if not main_img and imgs:
                main_img = imgs[0]
            if not main_img:
                main_img = default_img
            if not imgs:
                imgs = [main_img]

            results.append({
                "id": str(a.id),
                "title": a.title,
                "breed": a.breed or "Desi Breed",
                "age_months": getattr(a, "age_months", 24) or 24,
                "milk_yield_liters": float(a.milk_yield_liters or 12.0),
                "milk_yield": f"{a.milk_yield_liters or 12.0} Ltr / Day",
                "lactation": f"{a.lactation or 1}st Lactation",
                "lactation_num": getattr(a, "lactation", 1) or 1,
                "type": animal_type_name,
                "price": float(a.price),
                "old_price": float(a.price * Decimal("1.1")),
                "badge": a.badge or "VERIFIED MILK",
                "seller_name": seller_name,
                "seller_mobile": seller_mobile,
                "location": "Rohtak, Haryana",
                "description": a.description or "",
                "image": main_img,
                "images": imgs,
            })

        # 4. Sorting
        if sort_by == "price_low":
            results.sort(key=lambda x: x["price"])
        elif sort_by == "price_high":
            results.sort(key=lambda x: x["price"], reverse=True)
        elif sort_by == "newest":
            results.reverse()

        return results

    async def handle_create_animal_listing(self, command: CreateAnimalListingCommand, owner_id: UUID | None = None) -> AnimalModel:
        data = {
            "seller_user_id": owner_id or command.seller_user_id,
            "animal_type_id": command.animal_type_id,
            "title": command.title,
            "breed": command.breed,
            "age_months": command.age_months,
            "milk_yield_liters": command.milk_yield_liters,
            "lactation": command.lactation,
            "pregnancy_date": command.pregnancy_date,
            "price": command.price,
            "discount_percent": command.discount_percent,
            "badge": command.badge,
            "description": command.description,
            "is_active": True,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_animal(data, owner_id)
        return await self._repository.save_animal(data, owner_id)

    async def handle_update_animal_listing(self, command: UpdateAnimalListingCommand, owner_id: UUID | None = None) -> AnimalModel:
        data = {
            "seller_user_id": owner_id or command.seller_user_id,
            "animal_type_id": command.animal_type_id,
            "title": command.title,
            "breed": command.breed,
            "age_months": command.age_months,
            "milk_yield_liters": command.milk_yield_liters,
            "lactation": command.lactation,
            "pregnancy_date": command.pregnancy_date,
            "price": command.price,
            "discount_percent": command.discount_percent,
            "badge": command.badge,
            "description": command.description,
            "is_active": command.is_active,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_animal(data, created_by=owner_id, animal_id=command.id)
        return await self._repository.save_animal(data, created_by=owner_id, animal_id=command.id)

    async def handle_delete_animal_listing(self, command: DeleteAnimalListingCommand) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_animal(command.id)
        return await self._repository.delete_animal(command.id)

    async def add_animal_listing(self, data: dict[str, Any], owner_id: UUID | None = None) -> dict[str, Any]:
        image_files = data.pop("image_files", [])
        if not image_files and data.get("image_file"):
            image_files = [data.pop("image_file")]

        uploaded_urls = []
        for file in image_files:
            if file and getattr(file, "filename", None):
                url = await self._repository.process_image_upload(file, category=MediaCategory.ANIMAL)
                if url:
                    uploaded_urls.append(url)

        existing_urls = data.get("image_urls") or []
        if isinstance(existing_urls, str):
            existing_urls = [u.strip() for u in existing_urls.split(",") if u.strip()]

        all_images = uploaded_urls + existing_urls
        if all_images:
            data["image_url"] = all_images[0]
            data["images"] = all_images

        if self._database:
            async with self._database.transaction():
                res = await self._repository.save_animal(data, created_by=owner_id or data.get("seller_user_id"))
        else:
            res = await self._repository.save_animal(data, created_by=owner_id or data.get("seller_user_id"))
        return {"id": str(res.id), **data}

    async def update_animal_listing(self, animal_id: str, data: dict[str, Any], owner_id: UUID | None = None) -> dict[str, Any]:
        image_files = data.pop("image_files", [])
        if not image_files and data.get("image_file"):
            image_files = [data.pop("image_file")]

        uploaded_urls = []
        for file in image_files:
            if file and getattr(file, "filename", None):
                url = await self._repository.process_image_upload(file, category=MediaCategory.ANIMAL)
                if url:
                    uploaded_urls.append(url)

        existing_urls = data.get("image_urls") or []
        if isinstance(existing_urls, str):
            existing_urls = [u.strip() for u in existing_urls.split(",") if u.strip()]

        all_images = uploaded_urls + existing_urls
        if all_images:
            data["image_url"] = all_images[0]
            data["images"] = all_images

        if self._database:
            async with self._database.transaction():
                res = await self._repository.save_animal(data, created_by=owner_id or data.get("seller_user_id"), animal_id=animal_id)
        else:
            res = await self._repository.save_animal(data, created_by=owner_id or data.get("seller_user_id"), animal_id=animal_id)
        return {"id": str(res.id), **data}

    async def delete_animal_listing(self, animal_id: str) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_animal(animal_id)
        return await self._repository.delete_animal(animal_id)

    # =========================================================
    # 5. CATALOG PRODUCTS HANDLERS
    # =========================================================
    async def get_products(self, category_id: str = "all", query: str = "", sort_by: str = "default") -> list[dict[str, Any]]:
        prods = await self._repository.get_products()
        results = []
        default_img = "https://images.unsplash.com/photo-1500595046743-cd271d694d30?auto=format&fit=crop&w=600&q=80"
        
        target_cat = str(category_id or "all").strip().lower()

        for item in prods:
            try:
                if len(item) == 2:
                    p, cat = item
                else:
                    p, cat = item[0], None
            except (TypeError, ValueError):
                p, cat = item, None

            p_cat_id = str(getattr(p, "category_id", "") or "").lower()
            p_cat_slug = str(getattr(cat, "slug", "") or "").lower()
            p_cat_name = str(getattr(cat, "name", "") or "").lower()

            # 1. Filter by category
            if target_cat != "all":
                if any(kw in target_cat for kw in ["pashu", "cattle", "livestock"]):
                    is_pashu_prod = any(kw in p_cat_slug for kw in ["pashu", "cattle", "livestock"]) or any(kw in p_cat_name for kw in ["pashu", "cattle", "livestock"])
                    if not is_pashu_prod:
                        continue
                else:
                    match_id = (p_cat_id == target_cat)
                    match_slug = (p_cat_slug == target_cat)
                    match_name = (target_cat in p_cat_name or p_cat_name in target_cat)
                    if not (match_id or match_slug or match_name):
                        continue

            # 2. Filter by search query
            if query and query.strip():
                q = query.strip().lower()
                searchable = f"{p.title} {getattr(p, 'brand_name', '')} {p.description} {p_cat_name}".lower()
                if q not in searchable:
                    continue

            imgs = getattr(p, "images", None) or []
            main_img = getattr(p, "image_url", None)
            if not main_img and imgs:
                main_img = imgs[0]
            if not main_img:
                main_img = default_img
            if not imgs:
                imgs = [main_img]

            price_val = float(getattr(p, "price", 1450.0) or 1450.0)
            old_price_val = float(getattr(p, "compare_at_price", price_val * 1.15) or (price_val * 1.15))

            results.append({
                "id": str(p.id),
                "name": p.title,
                "title": p.title,
                "brand_name": getattr(p, "brand_name", "Vitco Feeds") or "Vitco Feeds",
                "category_id": str(p.category_id),
                "category_name": p_cat_name.title() or getattr(cat, "name", "Dairy & Feeds") or "Dairy & Feeds",
                "price": price_val,
                "old_price": old_price_val,
                "compare_at_price": old_price_val,
                "badge": getattr(p, "badge", "BESTSELLER") or "BESTSELLER",
                "unit": getattr(p, "unit", "50 kg Bag") or "50 kg Bag",
                "badge_color": "#10b981",
                "stock_qty": 50,
                "seller_name": "Agro Feeds Ltd",
                "seller_mobile": "+91 98123 45678",
                "location": "Karnal, Haryana",
                "description": p.description or "",
                "image": main_img,
                "images": imgs,
            })

        # 3. Sort results
        if sort_by == "price_low":
            results.sort(key=lambda x: x["price"])
        elif sort_by == "price_high":
            results.sort(key=lambda x: x["price"], reverse=True)
        elif sort_by == "newest":
            results.reverse()

        return results

    async def handle_create_product(self, command: CreateProductCommand) -> MarketplaceProductModel:
        data = {
            "category_id": command.category_id,
            "title": command.title,
            "slug": command.slug,
            "description": command.description,
            "brand_name": command.brand_name,
            "status": command.status,
            "is_featured": command.is_featured,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_product(data)
        return await self._repository.save_product(data)

    async def handle_update_product(self, command: UpdateProductCommand) -> MarketplaceProductModel:
        data = {
            "category_id": command.category_id,
            "title": command.title,
            "slug": command.slug,
            "description": command.description,
            "brand_name": command.brand_name,
            "status": command.status,
            "is_featured": command.is_featured,
        }
        if self._database:
            async with self._database.transaction():
                return await self._repository.save_product(data, product_id=command.id)
        return await self._repository.save_product(data, product_id=command.id)

    async def handle_delete_product(self, command: DeleteProductCommand) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_product(command.id)
        return await self._repository.delete_product(command.id)

    async def add_product_listing(self, data: dict[str, Any]) -> dict[str, Any]:
        image_files = data.pop("image_files", [])
        if not image_files and data.get("image_file"):
            image_files = [data.pop("image_file")]

        uploaded_urls = []
        for file in image_files:
            if file and getattr(file, "filename", None):
                url = await self._repository.process_image_upload(file, category=MediaCategory.PRODUCT)
                if url:
                    uploaded_urls.append(url)

        existing_urls = data.get("image_urls") or []
        if isinstance(existing_urls, str):
            existing_urls = [u.strip() for u in existing_urls.split(",") if u.strip()]

        all_images = uploaded_urls + existing_urls
        if all_images:
            data["image_url"] = all_images[0]
            data["images"] = all_images

        if self._database:
            async with self._database.transaction():
                res = await self._repository.save_product(data)
        else:
            res = await self._repository.save_product(data)
        return {"id": str(res.id), **data}

    async def update_product_listing(self, product_id: str, data: dict[str, Any]) -> dict[str, Any]:
        image_files = data.pop("image_files", [])
        if not image_files and data.get("image_file"):
            image_files = [data.pop("image_file")]

        uploaded_urls = []
        for file in image_files:
            if file and getattr(file, "filename", None):
                url = await self._repository.process_image_upload(file, category=MediaCategory.PRODUCT)
                if url:
                    uploaded_urls.append(url)

        existing_urls = data.get("image_urls") or []
        if isinstance(existing_urls, str):
            existing_urls = [u.strip() for u in existing_urls.split(",") if u.strip()]

        all_images = uploaded_urls + existing_urls
        if all_images:
            data["image_url"] = all_images[0]
            data["images"] = all_images

        if self._database:
            async with self._database.transaction():
                res = await self._repository.save_product(data, product_id=product_id)
        else:
            res = await self._repository.save_product(data, product_id=product_id)
        return {"id": str(res.id), **data}

    async def delete_product_listing(self, product_id: str) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_product(product_id)
        return await self._repository.delete_product(product_id)

    # =========================================================
    # ORDERS APPLICATION METHODS
    # =========================================================
    async def create_order(self, data: dict[str, Any]) -> dict[str, Any]:
        if self._database:
            async with self._database.transaction():
                order = await self._repository.create_order(data)
        else:
            order = await self._repository.create_order(data)
        return {
            "id": str(order.id),
            "order_ref": order.order_ref,
            "buyer_name": order.buyer_name,
            "buyer_phone": order.buyer_phone,
            "delivery_address": order.delivery_address,
            "payment_method": order.payment_method,
            "total_amount": float(order.total_amount or 0.0),
            "order_items": order.items_json or [],
            "status": order.status,
            "created_at": order.created_at.strftime("%d %b %Y, %I:%M %p") if getattr(order, "created_at", None) else "Just now",
        }

    async def get_orders(self) -> list[dict[str, Any]]:
        orders = await self._repository.get_orders()
        res = []
        for o in orders:
            res.append({
                "id": str(o.id),
                "buyer_id": o.buyer_id,
                "order_ref": getattr(o, "order_ref", f"#VIT-{str(o.id)[:6]}"),
                "buyer_name": getattr(o, "buyer_name", "Customer"),
                "buyer_phone": getattr(o, "buyer_phone", "-"),
                "delivery_address": getattr(o, "delivery_address", "-"),
                "payment_method": getattr(o, "payment_method", "cod").upper(),
                "total_amount": float(getattr(o, "total_amount", 0.0) or 0.0),
                "order_items": getattr(o, "items_json", []) or [],
                "status": getattr(o, "status", "PENDING") or "PENDING",
                "created_at": o.created_at.strftime("%d %b %Y, %I:%M %p") if getattr(o, "created_at", None) else "Recently",
            })
        return res

    async def get_orders_by_user_id(self,user_id:UUID) -> list[dict[str, Any]]:
        orders = await self._repository.get_orders_by_user_id(user_id)
        res = []
        for o in orders:
            res.append({
                "id": str(o.id),
                "buyer_id": o.buyer_id,
                "order_ref": getattr(o, "order_ref", f"#VIT-{str(o.id)[:6]}"),
                "buyer_name": getattr(o, "buyer_name", "Customer"),
                "buyer_phone": getattr(o, "buyer_phone", "-"),
                "delivery_address": getattr(o, "delivery_address", "-"),
                "payment_method": getattr(o, "payment_method", "cod").upper(),
                "total_amount": float(getattr(o, "total_amount", 0.0) or 0.0),
                "order_items": getattr(o, "items_json", []) or [],
                "status": getattr(o, "status", "PENDING") or "PENDING",
                "created_at": o.created_at.strftime("%d %b %Y, %I:%M %p") if getattr(o, "created_at", None) else "Recently",
            })
        return res

    async def update_order_status(self, order_id: str, new_status: str) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.update_order_status(order_id, new_status)
        return await self._repository.update_order_status(order_id, new_status)

    async def delete_order(self, order_id: str) -> bool:
        if self._database:
            async with self._database.transaction():
                return await self._repository.delete_order(order_id)
        return await self._repository.delete_order(order_id)


# Alias for backward compatibility
MarketplaceHandler = MarketplaceCommandHandler

