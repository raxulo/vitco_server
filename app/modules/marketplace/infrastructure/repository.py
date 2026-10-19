"""
Marketplace Infrastructure Repository

Enterprise-grade repository handling database persistence and media module integration for:
- Hero Banners (MarketplaceBannerModel)
- Trending Tags (MarketplaceTrendingTagModel)
- Browse Category Cards (MarketplaceBrowseCategoryModel)
- Product Categories (ProductCategoryModel)
- Animal Types Master (AnimalTypeModel)
- Catalog Products & Variants (MarketplaceProductModel, ProductVariantModel)
- Product Offers & Inventory (ProductOfferModel, InventoryModel)
- Cattle Listings (AnimalModel / AnimalListingModel)

Integrates with app.core.database.manager (DatabaseManager) and app.modules.media (MediaService).
"""

from app.modules.administration.infrastructure.models import UserModel

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator
from typing import Any
from uuid import UUID, uuid4
from fastapi import UploadFile
from sqlalchemy import select, delete, update, func
from sqlalchemy.ext.asyncio import AsyncSession

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
    AnimalListingModel,
    MarketplaceCategoryModel,
    MarketplaceOrderModel,
)


def _ensure_uuid(val: UUID | str | None) -> UUID | None:
    if val is None:
        return None
    if isinstance(val, UUID):
        return val
    try:
        return UUID(str(val))
    except (ValueError, TypeError, AttributeError):
        return None


class MarketplaceRepository:
    """Repository managing all Marketplace Database operations and Media file uploads."""

    def __init__(self, db: DatabaseManager | None = None, media_service: MediaService | None = None) -> None:
        self.database = db
        self.media_service = media_service

    @asynccontextmanager
    async def _get_session(self) -> AsyncIterator[tuple[AsyncSession, bool]]:
        if not self.database:
            raise RuntimeError("DatabaseManager is not configured.")
        try:
            session = self.database.session
            yield session, False
        except RuntimeError:
            async with self.database.session() as session:
                yield session, True

    async def _save_changes(self, session: AsyncSession, standalone: bool, instance: Any | None = None) -> None:
        if standalone:
            await session.commit()
            if instance:
                await session.refresh(instance)
        else:
            await session.flush()

    # =========================================================
    # Media Integration Helper
    # =========================================================
    async def process_image_upload(
        self,
        file: UploadFile,
        category: MediaCategory = MediaCategory.PRODUCT,
        entity_id: UUID | None = None,
    ) -> str | None:
        """Uploads image file via MediaService and returns public media URL with local disk fallback."""
        if not file or not getattr(file, "filename", None):
            return None
        if self.media_service:
            try:
                media = await self.media_service.upload_image(file=file, category=category, entity_id=entity_id)
                if media and media.storage_key:
                    return MediaUrlService.build(media.storage_key)
            except Exception:
                pass
        try:
            import os, uuid
            ext = os.path.splitext(file.filename)[1] or ".jpg"
            cat_name = category.value if hasattr(category, "value") else str(category)
            fn = f"{cat_name}_{uuid.uuid4().hex[:10]}{ext}"
            static_dir = os.path.join("app", "web", "static", "uploads", "marketplace")
            os.makedirs(static_dir, exist_ok=True)
            fp = os.path.join(static_dir, fn)
            content = await file.read()
            if content:
                with open(fp, "wb") as f:
                    f.write(content)
                return f"/static/uploads/marketplace/{fn}"
        except Exception:
            pass
        return None

    # =========================================================
    # HERO BANNERS Persistence
    # =========================================================
    async def get_banners(self) -> list[MarketplaceBannerModel]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceBannerModel).where(MarketplaceBannerModel.is_active == True).order_by(MarketplaceBannerModel.sort_order)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_banner_by_id(self, banner_id: UUID | str) -> MarketplaceBannerModel | None:
        if not self.database:
            return None
        bid = _ensure_uuid(banner_id)
        if not bid:
            return None
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceBannerModel).where(MarketplaceBannerModel.id == bid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_banner(self, banner_data: dict[str, Any], banner_id: UUID | str | None = None) -> MarketplaceBannerModel:
        bid = _ensure_uuid(banner_id)
        if "id" in banner_data:
            banner_data["id"] = _ensure_uuid(banner_data["id"])

        if not self.database:
            return MarketplaceBannerModel(**banner_data)

        async with self._get_session() as (session, standalone):
            target_id = bid or banner_data.get("id")
            if target_id:
                stmt = select(MarketplaceBannerModel).where(MarketplaceBannerModel.id == target_id)
                res = await session.execute(stmt)
                banner = res.scalar_one_or_none()
                if banner:
                    for k, v in banner_data.items():
                        if hasattr(banner, k) and k != "id":
                            if k == "image_url" and not v:
                                continue
                            setattr(banner, k, v)
                    await self._save_changes(session, standalone, banner)
                    return banner

            banner = MarketplaceBannerModel(**banner_data)
            session.add(banner)
            await self._save_changes(session, standalone, banner)
            return banner

    async def delete_banner(self, banner_id: UUID | str) -> bool:
        if not self.database:
            return True
        bid = _ensure_uuid(banner_id)
        if not bid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = delete(MarketplaceBannerModel).where(MarketplaceBannerModel.id == bid)
            await session.execute(stmt)
            await self._save_changes(session, standalone)
            return True

    # =========================================================
    # TRENDING TAGS Persistence
    # =========================================================
    async def get_trending_tags(self) -> list[MarketplaceTrendingTagModel]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceTrendingTagModel).where(MarketplaceTrendingTagModel.is_active == True).order_by(MarketplaceTrendingTagModel.sort_order)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_trending_tag_by_id(self, tag_id: UUID | str) -> MarketplaceTrendingTagModel | None:
        if not self.database:
            return None
        tid = _ensure_uuid(tag_id)
        if not tid:
            return None
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceTrendingTagModel).where(MarketplaceTrendingTagModel.id == tid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_trending_tag(self, data: dict[str, Any], tag_id: UUID | str | None = None) -> MarketplaceTrendingTagModel:
        tid = _ensure_uuid(tag_id)
        if "id" in data:
            data["id"] = _ensure_uuid(data["id"])

        if not self.database:
            return MarketplaceTrendingTagModel(**data)

        async with self._get_session() as (session, standalone):
            target_id = tid or data.get("id")
            if target_id:
                stmt = select(MarketplaceTrendingTagModel).where(MarketplaceTrendingTagModel.id == target_id)
                res = await session.execute(stmt)
                tag = res.scalar_one_or_none()
                if tag:
                    for k, v in data.items():
                        if hasattr(tag, k) and k != "id":
                            setattr(tag, k, v)
                    await self._save_changes(session, standalone, tag)
                    return tag

            tag = MarketplaceTrendingTagModel(**data)
            session.add(tag)
            await self._save_changes(session, standalone, tag)
            return tag

    async def delete_trending_tag(self, tag_id: UUID | str) -> bool:
        if not self.database:
            return True
        tid = _ensure_uuid(tag_id)
        if not tid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = delete(MarketplaceTrendingTagModel).where(MarketplaceTrendingTagModel.id == tid)
            await session.execute(stmt)
            await self._save_changes(session, standalone)
            return True

    # =========================================================
    # BROWSE CATEGORY CARDS Persistence
    # =========================================================
    async def get_browse_categories(self) -> list[MarketplaceBrowseCategoryModel]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceBrowseCategoryModel).where(MarketplaceBrowseCategoryModel.is_active == True).order_by(MarketplaceBrowseCategoryModel.sort_order)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_browse_category_by_id(self, cat_id: UUID | str) -> MarketplaceBrowseCategoryModel | None:
        if not self.database:
            return None
        cid = _ensure_uuid(cat_id)
        if not cid:
            return None
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceBrowseCategoryModel).where(MarketplaceBrowseCategoryModel.id == cid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_browse_category(self, data: dict[str, Any], cat_id: UUID | str | None = None) -> MarketplaceBrowseCategoryModel:
        cid = _ensure_uuid(cat_id)
        if "id" in data:
            data["id"] = _ensure_uuid(data["id"])

        if not self.database:
            return MarketplaceBrowseCategoryModel(**data)

        async with self._get_session() as (session, standalone):
            target_id = cid or data.get("id")
            if target_id:
                stmt = select(MarketplaceBrowseCategoryModel).where(MarketplaceBrowseCategoryModel.id == target_id)
                res = await session.execute(stmt)
                cat = res.scalar_one_or_none()
                if cat:
                    for k, v in data.items():
                        if hasattr(cat, k) and k != "id":
                            setattr(cat, k, v)
                    await self._save_changes(session, standalone, cat)
                    return cat

            cat = MarketplaceBrowseCategoryModel(**data)
            session.add(cat)
            await self._save_changes(session, standalone, cat)
            return cat

    async def delete_browse_category(self, cat_id: UUID | str) -> bool:
        if not self.database:
            return True
        cid = _ensure_uuid(cat_id)
        if not cid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = delete(MarketplaceBrowseCategoryModel).where(MarketplaceBrowseCategoryModel.id == cid)
            await session.execute(stmt)
            await self._save_changes(session, standalone)
            return True

    # =========================================================
    # PRODUCT CATEGORIES Persistence
    # =========================================================
    async def get_product_categories(self) -> list[ProductCategoryModel]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = select(ProductCategoryModel).where(ProductCategoryModel.is_active == True).order_by(ProductCategoryModel.sort_order)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def get_product_category_by_id(self, cat_id: UUID | str) -> ProductCategoryModel | None:
        if not self.database:
            return None
        cid = _ensure_uuid(cat_id)
        if not cid:
            return None
        async with self._get_session() as (session, _):
            stmt = select(ProductCategoryModel).where(ProductCategoryModel.id == cid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_product_category(self, data: dict[str, Any], cat_id: UUID | str | None = None) -> ProductCategoryModel:
        cid = _ensure_uuid(cat_id)
        if "id" in data:
            data["id"] = _ensure_uuid(data["id"])

        if not self.database:
            return ProductCategoryModel(**data)

        async with self._get_session() as (session, standalone):
            target_id = cid or data.get("id")
            if target_id:
                stmt = select(ProductCategoryModel).where(ProductCategoryModel.id == target_id)
                res = await session.execute(stmt)
                cat = res.scalar_one_or_none()
                if cat:
                    for k, v in data.items():
                        if hasattr(cat, k) and k != "id":
                            setattr(cat, k, v)
                    await self._save_changes(session, standalone, cat)
                    return cat

            cat = ProductCategoryModel(**data)
            session.add(cat)
            await self._save_changes(session, standalone, cat)
            return cat

    async def delete_product_category(self, cat_id: UUID | str) -> bool:
        if not self.database:
            return True
        cid = _ensure_uuid(cat_id)
        if not cid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = delete(ProductCategoryModel).where(ProductCategoryModel.id == cid)
            await session.execute(stmt)
            await self._save_changes(session, standalone)
            return True

    # Backwards compatibility alias
    get_categories = get_product_categories
    save_category = save_product_category
    delete_category = delete_product_category

    # =========================================================
    # ANIMAL TYPES Persistence
    # =========================================================
    async def get_animal_types(self) -> list[AnimalTypeModel]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = select(AnimalTypeModel).where(AnimalTypeModel.is_active == True)
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def save_animal_type(self, data: dict[str, Any], type_id: UUID | str | None = None) -> AnimalTypeModel:
        tid = _ensure_uuid(type_id)
        if "id" in data:
            data["id"] = _ensure_uuid(data["id"])

        if not self.database:
            return AnimalTypeModel(**data)

        async with self._get_session() as (session, standalone):
            target_id = tid or data.get("id")
            if target_id:
                stmt = select(AnimalTypeModel).where(AnimalTypeModel.id == target_id)
                res = await session.execute(stmt)
                item = res.scalar_one_or_none()
                if item:
                    for k, v in data.items():
                        if hasattr(item, k) and k != "id":
                            setattr(item, k, v)
                    await self._save_changes(session, standalone, item)
                    return item

            item = AnimalTypeModel(**data)
            session.add(item)
            await self._save_changes(session, standalone, item)
            return item

    # =========================================================
    # CATTLE ANIMALS Persistence
    # =========================================================
    async def get_animals(self) -> list[tuple[AnimalModel, UserModel | None, AnimalTypeModel | None]]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = (
                select(AnimalModel, UserModel, AnimalTypeModel)
                .outerjoin(UserModel, AnimalModel.seller_user_id == UserModel.id)
                .outerjoin(AnimalTypeModel, AnimalModel.animal_type_id == AnimalTypeModel.id)
                .where(AnimalModel.is_active == True)
            )
            result = await session.execute(stmt)
            return list(result.tuples().all())

    async def get_animal_by_id(self, animal_id: UUID | str) -> AnimalModel | None:
        if not self.database:
            return None
        aid = _ensure_uuid(animal_id)
        if not aid:
            return None
        async with self._get_session() as (session, _):
            stmt = select(AnimalModel).where(AnimalModel.id == aid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_animal(self, data: dict[str, Any], created_by: UUID | str | None = None, animal_id: UUID | str | None = None) -> AnimalModel:
        aid = _ensure_uuid(animal_id)
        if "id" in data:
            data["id"] = _ensure_uuid(data["id"])

        if not self.database:
            return AnimalModel(**data)

        async with self._get_session() as (session, standalone):
            # Ensure valid seller_user_id
            seller_id = _ensure_uuid(created_by) or _ensure_uuid(data.get("seller_user_id"))
            if not seller_id:
                stmt_u = select(UserModel.id).limit(1)
                res_u = await session.execute(stmt_u)
                seller_id = res_u.scalar_one_or_none()
                if not seller_id:
                    default_user = UserModel(
                        name="System Seller",
                        email="seller@vitco.com",
                        password_hash="system_default",
                    )
                    session.add(default_user)
                    await session.flush()
                    seller_id = default_user.id
            data["seller_user_id"] = seller_id

            # Ensure valid animal_type_id
            type_str = data.pop("animal_type", None) or data.pop("type", None)
            type_id = _ensure_uuid(data.get("animal_type_id"))
            if type_str:
                stmt_t = select(AnimalTypeModel).where(func.lower(AnimalTypeModel.name) == str(type_str).lower())
                res_t = await session.execute(stmt_t)
                existing_t = res_t.scalar_one_or_none()
                if existing_t:
                    type_id = existing_t.id
                else:
                    new_t = AnimalTypeModel(
                        name=str(type_str).capitalize(),
                        code=str(type_str).upper(),
                        description=f"{type_str} Master Type",
                        is_active=True,
                    )
                    session.add(new_t)
                    await session.flush()
                    type_id = new_t.id

            if not type_id:
                stmt_t = select(AnimalTypeModel.id).limit(1)
                res_t = await session.execute(stmt_t)
                type_id = res_t.scalar_one_or_none()
                if not type_id:
                    default_type = AnimalTypeModel(
                        name="Cow",
                        code="COW",
                        description="Cattle Livestock Master",
                        is_active=True,
                    )
                    session.add(default_type)
                    await session.flush()
                    type_id = default_type.id
            data["animal_type_id"] = type_id

            target_id = aid or data.get("id")
            if target_id:
                stmt = select(AnimalModel).where(AnimalModel.id == target_id)
                res = await session.execute(stmt)
                item = res.scalar_one_or_none()
                if item:
                    for k, v in data.items():
                        if hasattr(item, k) and k != "id":
                            setattr(item, k, v)
                    await self._save_changes(session, standalone, item)
                    return item

            item = AnimalModel(**data)
            session.add(item)
            await self._save_changes(session, standalone, item)
            return item

    async def delete_animal(self, animal_id: UUID | str) -> bool:
        if not self.database:
            return True
        aid = _ensure_uuid(animal_id)
        if not aid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = delete(AnimalModel).where(AnimalModel.id == aid)
            await session.execute(stmt)
            await self._save_changes(session, standalone)
            return True

    # Backwards compatibility alias
    save_animal_listing = save_animal
    delete_animal_listing = delete_animal

    # =========================================================
    # PRODUCTS Persistence
    # =========================================================
    async def get_products(self) -> list[tuple[MarketplaceProductModel, ProductCategoryModel | None]]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = (
                select(MarketplaceProductModel, ProductCategoryModel)
                .outerjoin(ProductCategoryModel, MarketplaceProductModel.category_id == ProductCategoryModel.id)
            )
            result = await session.execute(stmt)
            return list(result.tuples().all())

    async def get_product_by_id(self, product_id: UUID | str) -> MarketplaceProductModel | None:
        if not self.database:
            return None
        pid = _ensure_uuid(product_id)
        if not pid:
            return None
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceProductModel).where(MarketplaceProductModel.id == pid)
            result = await session.execute(stmt)
            return result.scalar_one_or_none()

    async def save_product(self, data: dict[str, Any], product_id: UUID | str | None = None) -> MarketplaceProductModel:
        pid = _ensure_uuid(product_id)
        if "id" in data:
            data["id"] = _ensure_uuid(data["id"])

        if not self.database:
            return MarketplaceProductModel(**data)

        async with self._get_session() as (session, standalone):
            # Ensure valid category_id
            cat_id = _ensure_uuid(data.get("category_id"))
            if not cat_id:
                stmt_c = select(ProductCategoryModel.id).limit(1)
                res_c = await session.execute(stmt_c)
                cat_id = res_c.scalar_one_or_none()
                if not cat_id:
                    default_cat = ProductCategoryModel(
                        name="Dairy & Feeds",
                        slug="dairy-feeds",
                        description="Animal Nutrition & Feeds",
                        is_active=True,
                    )
                    session.add(default_cat)
                    await session.flush()
                    cat_id = default_cat.id
            data["category_id"] = cat_id

            if "title" in data and not data.get("slug"):
                data["slug"] = f"{data['title'].lower().replace(' ', '-')}-{uuid4().hex[:6]}"

            target_id = pid or data.get("id")
            if target_id:
                stmt = select(MarketplaceProductModel).where(MarketplaceProductModel.id == target_id)
                res = await session.execute(stmt)
                item = res.scalar_one_or_none()
                if item:
                    for k, v in data.items():
                        if hasattr(item, k) and k != "id":
                            setattr(item, k, v)
                    await self._save_changes(session, standalone, item)
                    return item

            item = MarketplaceProductModel(**data)
            session.add(item)
            await self._save_changes(session, standalone, item)
            return item

    async def delete_product(self, product_id: UUID | str) -> bool:
        if not self.database:
            return True
        pid = _ensure_uuid(product_id)
        if not pid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = delete(MarketplaceProductModel).where(MarketplaceProductModel.id == pid)
            await session.execute(stmt)
            await self._save_changes(session, standalone)
            return True

    # =========================================================
    # ORDERS PERSISTENCE METHODS
    # =========================================================
    async def create_order(self, data: dict[str, Any]) -> MarketplaceOrderModel:
        if not self.database:
            return MarketplaceOrderModel(**data)
        async with self._get_session() as (session, standalone):
            order = MarketplaceOrderModel(**data)
            session.add(order)
            await self._save_changes(session, standalone, order)
            return order

    async def get_orders(self) -> list[MarketplaceOrderModel]:
        if not self.database:
            return []
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceOrderModel).order_by(MarketplaceOrderModel.created_at.desc())
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def get_orders_by_user_id(self, user_id: UUID | str) -> list[MarketplaceOrderModel]:
        if not self.database:
            return []
        uid = _ensure_uuid(user_id)
        if not uid:
            return []
        async with self._get_session() as (session, _):
            stmt = select(MarketplaceOrderModel).order_by(MarketplaceOrderModel.created_at.desc()).where(MarketplaceOrderModel.buyer_id == uid)
            res = await session.execute(stmt)
            return list(res.scalars().all())

    async def update_order_status(self, order_id: UUID | str, new_status: str) -> bool:
        if not self.database:
            return True
        oid = _ensure_uuid(order_id)
        if not oid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = select(MarketplaceOrderModel).where(MarketplaceOrderModel.id == oid)
            res = await session.execute(stmt)
            item = res.scalar_one_or_none()
            if item:
                item.status = new_status
                await self._save_changes(session, standalone, item)
                return True
            return False

    async def delete_order(self, order_id: UUID | str) -> bool:
        if not self.database:
            return True
        oid = _ensure_uuid(order_id)
        if not oid:
            return False
        async with self._get_session() as (session, standalone):
            stmt = delete(MarketplaceOrderModel).where(MarketplaceOrderModel.id == oid)
            await session.execute(stmt)
            await self._save_changes(session, standalone)
            return True
