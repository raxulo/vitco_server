"""
Public read side of the store. Every query here returns live listings only.

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import exists, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, selectinload

from app.core.database.manager import DatabaseManager
from app.modules.marketplace.domain.dto import (
    AnimalCard,
    AnimalDetail,
    AnimalFilters,
    AnimalTypeTile,
    BreedOption,
    CategoryTile,
    GalleryImage,
    ProductCard,
    ProductDetail,
    ProductFilters,
    SitemapListing,
    SizeOption,
)
from app.modules.marketplace.domain.entities import Enquiry
from app.modules.marketplace.domain.enums import AnimalStatus, EnquiryStatus, ProductStatus
from app.modules.marketplace.domain.irepository import IStorefrontRepository
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceEnquiryModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)

VISIBLE_ANIMAL_STATUSES = (AnimalStatus.PUBLISHED, AnimalStatus.RESERVED)
OPENABLE_ANIMAL_STATUSES = (*VISIBLE_ANIMAL_STATUSES, AnimalStatus.SOLD)


def product_card(model: MarketplaceProductModel) -> ProductCard | None:
    active = [variant for variant in model.variants if variant.is_active]
    if not active:
        return None
    shown = next((variant for variant in active if variant.is_default), active[0])
    image = model.images[0] if model.images else None
    return ProductCard(
        slug=model.slug,
        title=model.title,
        brand=model.brand,
        short_description=model.short_description,
        price=shown.price,
        mrp=shown.mrp,
        size=shown.name,
        other_sizes=len(active) - 1,
        in_stock=any(variant.stock > 0 for variant in active),
        image_url=image.url if image else None,
        image_alt=(image.alt_text or model.title) if image else None,
    )


def animal_card(model: MarketplaceAnimalModel, type_name: str, breed_name: str | None) -> AnimalCard:
    image = model.images[0] if model.images else None
    return AnimalCard(
        slug=model.slug,
        title=model.title,
        price=model.price,
        type_name=type_name,
        breed_name=breed_name,
        status=model.status,
        is_negotiable=model.is_negotiable,
        milk_litres_per_day=model.milk_litres_per_day,
        lactation_number=model.lactation_number,
        age_months=model.age_months,
        district=model.district,
        state=model.state,
        image_url=image.url if image else None,
        image_alt=(image.alt_text or model.title) if image else None,
    )


class StorefrontRepository(IStorefrontRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # MASTERS
    # =========================================================

    async def top_categories(self) -> list[CategoryTile]:
        stmt = (
            select(MarketplaceCategoryModel)
            .where(MarketplaceCategoryModel.is_active.is_(True), MarketplaceCategoryModel.parent_id.is_(None))
            .order_by(MarketplaceCategoryModel.sort_order, MarketplaceCategoryModel.name)
        )
        return [
            CategoryTile(name=model.name, slug=model.slug, image_url=model.image_url)
            for model in await self._session.scalars(stmt)
        ]

    async def animal_types(self) -> list[AnimalTypeTile]:
        stmt = (
            select(MarketplaceAnimalTypeModel)
            .where(MarketplaceAnimalTypeModel.is_active.is_(True))
            .order_by(MarketplaceAnimalTypeModel.sort_order, MarketplaceAnimalTypeModel.name)
        )
        return [
            AnimalTypeTile(name=model.name, slug=model.slug, image_url=model.image_url)
            for model in await self._session.scalars(stmt)
        ]

    async def category_slug(self, category_id: UUID) -> str | None:
        return await self._session.scalar(
            select(MarketplaceCategoryModel.slug).where(
                MarketplaceCategoryModel.id == category_id, MarketplaceCategoryModel.is_active.is_(True)
            )
        )

    # =========================================================
    # PRODUCTS
    # =========================================================

    @staticmethod
    def _live_products():
        has_active_size = exists().where(
            MarketplaceProductVariantModel.product_id == MarketplaceProductModel.id,
            MarketplaceProductVariantModel.is_active.is_(True),
        )
        return (
            select(MarketplaceProductModel)
            .join(MarketplaceCategoryModel, MarketplaceCategoryModel.id == MarketplaceProductModel.category_id)
            .where(
                MarketplaceProductModel.is_deleted.is_(False),
                MarketplaceProductModel.status == ProductStatus.PUBLISHED,
                MarketplaceCategoryModel.is_active.is_(True),
                has_active_size,
            )
        )

    async def _product_cards(self, stmt, limit: int) -> list[ProductCard]:
        page = (
            stmt.options(
                selectinload(MarketplaceProductModel.variants),
                selectinload(MarketplaceProductModel.images),
            )
            .order_by(MarketplaceProductModel.sort_order, MarketplaceProductModel.created_at.desc())
            .limit(limit)
        )
        cards = [product_card(model) for model in await self._session.scalars(page)]
        return [card for card in cards if card is not None]

    async def featured_products(self, limit: int) -> list[ProductCard]:
        return await self._product_cards(
            self._live_products().where(MarketplaceProductModel.is_featured.is_(True)), limit
        )

    async def trending_products(self, limit: int) -> list[ProductCard]:
        return await self._product_cards(
            self._live_products().where(MarketplaceProductModel.is_trending.is_(True)), limit
        )

    async def category_products(self, category_id: UUID, limit: int) -> list[ProductCard]:
        return await self._product_cards(
            self._live_products().where(MarketplaceProductModel.category_id == category_id), limit
        )

    # =========================================================
    # ANIMALS
    # =========================================================

    @staticmethod
    def _live_animals():
        return (
            select(MarketplaceAnimalModel, MarketplaceAnimalTypeModel.name, MarketplaceAnimalBreedModel.name)
            .join(MarketplaceAnimalTypeModel, MarketplaceAnimalTypeModel.id == MarketplaceAnimalModel.animal_type_id)
            .outerjoin(MarketplaceAnimalBreedModel, MarketplaceAnimalBreedModel.id == MarketplaceAnimalModel.breed_id)
            .where(
                MarketplaceAnimalModel.is_deleted.is_(False),
                MarketplaceAnimalModel.status.in_(VISIBLE_ANIMAL_STATUSES),
                MarketplaceAnimalTypeModel.is_active.is_(True),
            )
        )

    async def sitemap_products(self, limit: int) -> list[SitemapListing]:
        stmt = (
            self._live_products()
            .with_only_columns(MarketplaceProductModel.slug, MarketplaceProductModel.updated_at)
            .order_by(MarketplaceProductModel.updated_at.desc())
            .limit(limit)
        )
        return [SitemapListing(slug=slug, updated_at=updated_at) for slug, updated_at in await self._session.execute(stmt)]

    async def sitemap_animals(self, limit: int) -> list[SitemapListing]:
        stmt = (
            self._live_animals()
            .with_only_columns(MarketplaceAnimalModel.slug, MarketplaceAnimalModel.updated_at)
            .order_by(MarketplaceAnimalModel.updated_at.desc())
            .limit(limit)
        )
        return [SitemapListing(slug=slug, updated_at=updated_at) for slug, updated_at in await self._session.execute(stmt)]

    async def _animal_cards(self, stmt, limit: int) -> list[AnimalCard]:
        page = (
            stmt.options(selectinload(MarketplaceAnimalModel.images))
            .order_by(MarketplaceAnimalModel.sort_order, MarketplaceAnimalModel.created_at.desc())
            .limit(limit)
        )
        rows = await self._session.execute(page)
        return [animal_card(model, type_name, breed_name) for model, type_name, breed_name in rows]

    async def featured_animals(self, limit: int) -> list[AnimalCard]:
        return await self._animal_cards(
            self._live_animals().where(MarketplaceAnimalModel.is_featured.is_(True)), limit
        )

    async def trending_animals(self, limit: int) -> list[AnimalCard]:
        return await self._animal_cards(
            self._live_animals().where(MarketplaceAnimalModel.is_trending.is_(True)), limit
        )

    # =========================================================
    # LISTINGS
    # =========================================================

    async def all_categories(self) -> list[tuple[UUID, UUID | None, str, str]]:
        rows = await self._session.execute(
            select(
                MarketplaceCategoryModel.id, MarketplaceCategoryModel.parent_id,
                MarketplaceCategoryModel.name, MarketplaceCategoryModel.slug,
            )
            .where(MarketplaceCategoryModel.is_active.is_(True))
            .order_by(MarketplaceCategoryModel.sort_order, MarketplaceCategoryModel.name)
        )
        return [tuple(row) for row in rows]

    async def animal_type_id(self, slug: str) -> UUID | None:
        return await self._session.scalar(
            select(MarketplaceAnimalTypeModel.id).where(
                MarketplaceAnimalTypeModel.slug == slug, MarketplaceAnimalTypeModel.is_active.is_(True)
            )
        )

    async def breeds_of_type(self, animal_type_id: UUID) -> list[BreedOption]:
        rows = await self._session.execute(
            select(MarketplaceAnimalBreedModel.id, MarketplaceAnimalBreedModel.name)
            .where(
                MarketplaceAnimalBreedModel.animal_type_id == animal_type_id,
                MarketplaceAnimalBreedModel.is_active.is_(True),
            )
            .order_by(MarketplaceAnimalBreedModel.sort_order, MarketplaceAnimalBreedModel.name)
        )
        return [BreedOption(id=row.id, name=row.name) for row in rows]

    @staticmethod
    def _shown_price():
        """The price on the card: the default active size, else the lowest active price."""
        variant = aliased(MarketplaceProductVariantModel)
        default_price = (
            select(variant.price)
            .where(variant.product_id == MarketplaceProductModel.id, variant.is_active.is_(True), variant.is_default.is_(True))
            .limit(1)
            .scalar_subquery()
        )
        lowest_price = (
            select(func.min(variant.price))
            .where(variant.product_id == MarketplaceProductModel.id, variant.is_active.is_(True))
            .scalar_subquery()
        )
        return func.coalesce(default_price, lowest_price)

    async def list_products(self, filters: ProductFilters) -> tuple[list[ProductCard], int]:
        price = self._shown_price()
        stmt = self._live_products()
        if filters.search:
            stmt = stmt.where(or_(
                MarketplaceProductModel.title.icontains(filters.search, autoescape=True),
                MarketplaceProductModel.brand.icontains(filters.search, autoescape=True),
                MarketplaceProductModel.short_description.icontains(filters.search, autoescape=True),
            ))
        if filters.category_ids is not None:
            stmt = stmt.where(MarketplaceProductModel.category_id.in_(filters.category_ids))
        if filters.min_price is not None:
            stmt = stmt.where(price >= filters.min_price)
        if filters.max_price is not None:
            stmt = stmt.where(price <= filters.max_price)
        if filters.in_stock_only:
            stmt = stmt.where(exists().where(
                MarketplaceProductVariantModel.product_id == MarketplaceProductModel.id,
                MarketplaceProductVariantModel.is_active.is_(True),
                MarketplaceProductVariantModel.stock > 0,
            ))

        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order = {
            "price_asc": (price.asc(), MarketplaceProductModel.title),
            "price_desc": (price.desc(), MarketplaceProductModel.title),
        }.get(filters.sort, (MarketplaceProductModel.sort_order, MarketplaceProductModel.created_at.desc()))
        page = (
            stmt.options(
                selectinload(MarketplaceProductModel.variants),
                selectinload(MarketplaceProductModel.images),
            )
            .order_by(*order)
            .offset(filters.offset)
            .limit(filters.limit)
        )
        cards = [product_card(model) for model in await self._session.scalars(page)]
        return [card for card in cards if card is not None], total

    async def list_animals(self, filters: AnimalFilters) -> tuple[list[AnimalCard], int]:
        model = MarketplaceAnimalModel
        stmt = self._live_animals()
        if filters.search:
            stmt = stmt.where(or_(
                model.title.icontains(filters.search, autoescape=True),
                MarketplaceAnimalBreedModel.name.icontains(filters.search, autoescape=True),
                MarketplaceAnimalTypeModel.name.icontains(filters.search, autoescape=True),
                model.district.icontains(filters.search, autoescape=True),
            ))
        if filters.animal_type_id is not None:
            stmt = stmt.where(model.animal_type_id == filters.animal_type_id)
        if filters.breed_id is not None:
            stmt = stmt.where(model.breed_id == filters.breed_id)
        if filters.min_price is not None:
            stmt = stmt.where(model.price >= filters.min_price)
        if filters.max_price is not None:
            stmt = stmt.where(model.price <= filters.max_price)
        if filters.min_milk is not None:
            stmt = stmt.where(model.milk_litres_per_day >= filters.min_milk)
        if filters.lactation is not None:
            # 4 stands for "fourth or later"
            stmt = stmt.where(
                model.lactation_number >= 4 if filters.lactation >= 4 else model.lactation_number == filters.lactation
            )
        if filters.location:
            stmt = stmt.where(or_(
                model.village.icontains(filters.location, autoescape=True),
                model.district.icontains(filters.location, autoescape=True),
                model.state.icontains(filters.location, autoescape=True),
            ))

        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        order = {
            "price_asc": (model.price.asc(), model.title),
            "price_desc": (model.price.desc(), model.title),
            # Portable "NULLS LAST"
            "milk_desc": (model.milk_litres_per_day.is_(None), model.milk_litres_per_day.desc(), model.title),
        }.get(filters.sort, (model.sort_order, model.created_at.desc()))
        page = (
            stmt.options(selectinload(model.images))
            .order_by(*order)
            .offset(filters.offset)
            .limit(filters.limit)
        )
        rows = await self._session.execute(page)
        return [animal_card(item, type_name, breed_name) for item, type_name, breed_name in rows], total

    # =========================================================
    # DETAILS
    # =========================================================

    async def product_detail(self, slug: str) -> ProductDetail | None:
        row = (await self._session.execute(
            self._live_products()
            .add_columns(MarketplaceCategoryModel.name, MarketplaceCategoryModel.slug)
            .where(MarketplaceProductModel.slug == slug)
            .options(
                selectinload(MarketplaceProductModel.variants),
                selectinload(MarketplaceProductModel.images),
            )
        )).first()
        if row is None:
            return None
        model, category_name, category_slug = row
        sizes = [
            SizeOption(
                variant_id=variant.id,
                name=variant.name,
                price=variant.price,
                mrp=variant.mrp,
                in_stock=variant.stock > 0,
                is_default=variant.is_default,
                few_left=variant.stock if 0 < variant.stock <= variant.low_stock_threshold else None,
            )
            for variant in model.variants
            if variant.is_active
        ]
        return ProductDetail(
            slug=model.slug,
            title=model.title,
            brand=model.brand,
            short_description=model.short_description,
            description=model.description,
            specifications=list(model.specifications or []),
            category_id=model.category_id,
            category_name=category_name,
            category_slug=category_slug,
            sizes=sizes,
            images=[GalleryImage(url=image.url, alt=image.alt_text or model.title) for image in model.images],
        )

    async def animal_detail(self, slug: str) -> AnimalDetail | None:
        """Sold animals still open, because shared links should not break; they are left out of lists."""
        row = (await self._session.execute(
            select(
                MarketplaceAnimalModel, MarketplaceAnimalTypeModel.name, MarketplaceAnimalTypeModel.slug,
                MarketplaceAnimalBreedModel.name,
            )
            .join(MarketplaceAnimalTypeModel, MarketplaceAnimalTypeModel.id == MarketplaceAnimalModel.animal_type_id)
            .outerjoin(MarketplaceAnimalBreedModel, MarketplaceAnimalBreedModel.id == MarketplaceAnimalModel.breed_id)
            .where(
                MarketplaceAnimalModel.slug == slug,
                MarketplaceAnimalModel.is_deleted.is_(False),
                MarketplaceAnimalModel.status.in_(OPENABLE_ANIMAL_STATUSES),
                MarketplaceAnimalTypeModel.is_active.is_(True),
            )
            .options(selectinload(MarketplaceAnimalModel.images))
        )).first()
        if row is None:
            return None
        model, type_name, type_slug, breed_name = row
        return AnimalDetail(
            slug=model.slug, title=model.title, price=model.price, type_name=type_name, type_slug=type_slug,
            animal_type_id=model.animal_type_id, breed_name=breed_name, status=model.status, gender=model.gender,
            is_negotiable=model.is_negotiable, age_months=model.age_months, lactation_number=model.lactation_number,
            milk_litres_per_day=model.milk_litres_per_day, fat_percent=model.fat_percent,
            pregnancy_status=model.pregnancy_status, pregnancy_months=model.pregnancy_months,
            calf_details=model.calf_details, health_notes=model.health_notes,
            vaccination_notes=model.vaccination_notes, district=model.district, state=model.state,
            village=model.village, description=model.description,
            images=[GalleryImage(url=image.url, alt=image.alt_text or model.title) for image in model.images],
        )

    async def related_products(self, category_id: UUID, exclude_slug: str, limit: int) -> list[ProductCard]:
        return await self._product_cards(
            self._live_products().where(
                MarketplaceProductModel.category_id == category_id, MarketplaceProductModel.slug != exclude_slug
            ),
            limit,
        )

    async def similar_animals(self, animal_type_id: UUID, exclude_slug: str, limit: int) -> list[AnimalCard]:
        return await self._animal_cards(
            self._live_animals().where(
                MarketplaceAnimalModel.animal_type_id == animal_type_id, MarketplaceAnimalModel.slug != exclude_slug
            ),
            limit,
        )

    # =========================================================
    # ENQUIRIES
    # =========================================================

    async def enquiry_target(self, slug: str) -> tuple[UUID, UUID, str, AnimalStatus] | None:
        row = (await self._session.execute(
            select(
                MarketplaceAnimalModel.id, MarketplaceAnimalModel.seller_user_id,
                MarketplaceAnimalModel.title, MarketplaceAnimalModel.status,
            )
            .join(MarketplaceAnimalTypeModel, MarketplaceAnimalTypeModel.id == MarketplaceAnimalModel.animal_type_id)
            .where(
                MarketplaceAnimalModel.slug == slug,
                MarketplaceAnimalModel.is_deleted.is_(False),
                MarketplaceAnimalModel.status.in_(OPENABLE_ANIMAL_STATUSES),
                MarketplaceAnimalTypeModel.is_active.is_(True),
            )
        )).first()
        return None if row is None else tuple(row)

    async def open_enquiry_exists(self, animal_id: UUID, phone: str) -> bool:
        found = await self._session.scalar(
            select(MarketplaceEnquiryModel.id)
            .where(
                MarketplaceEnquiryModel.animal_id == animal_id,
                MarketplaceEnquiryModel.buyer_phone == phone,
                MarketplaceEnquiryModel.status != EnquiryStatus.CLOSED,
            )
            .limit(1)
        )
        return found is not None

    async def add_enquiry(self, enquiry: Enquiry) -> None:
        self._session.add(MarketplaceEnquiryModel(
            id=enquiry.id,
            animal_id=enquiry.animal_id,
            seller_user_id=enquiry.seller_user_id,
            animal_title=enquiry.animal_title,
            buyer_name=enquiry.buyer_name,
            buyer_phone=enquiry.buyer_phone,
            location=enquiry.location,
            message=enquiry.message,
            status=enquiry.status,
        ))
