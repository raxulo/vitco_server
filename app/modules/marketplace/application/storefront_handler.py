"""
Customer-facing store. Public: no login. Only enquiries write anything.

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.marketplace.application.command import CreateEnquiryCommand
from app.modules.marketplace.domain.contact import normalize_indian_mobile
from app.modules.marketplace.domain.dto import (
    AnimalCard,
    AnimalDetail,
    AnimalFilters,
    BreedOption,
    HomeBlock,
    HomePage,
    ProductCard,
    ProductDetail,
    ProductFilters,
    SitemapListing,
    StoreFrame,
)
from app.modules.marketplace.domain.entities import Enquiry
from app.modules.marketplace.domain.enums import AnimalStatus, BannerPlacement, HomeSectionType
from app.modules.marketplace.domain.exceptions import (
    AnimalNotAvailableException,
    AnimalNotFoundException,
    ListingValidationException,
)
from app.modules.marketplace.domain.irepository import IMerchandisingRepository, IStorefrontRepository
from app.modules.marketplace.domain.merchandising import HomeSection, StoreSettings

DEFAULT_STORE_NAME = "Vitco Marketplace"
_RELATED_LIMIT = 4
_SITEMAP_LIMIT = 24_000  # a sitemap file may hold 50,000 URLs: both kinds and the fixed pages must fit


class StorefrontHandler:

    __slots__ = ("_database", "_store", "_content")

    def __init__(
        self,
        database: DatabaseManager,
        store: IStorefrontRepository,
        content: IMerchandisingRepository,
    ) -> None:
        self._database = database
        self._store = store
        self._content = content

    # =========================================================
    # FRAME & HOME
    # =========================================================

    async def frame(self) -> StoreFrame:
        return StoreFrame(
            settings=await self._content.get_settings() or StoreSettings(store_name=DEFAULT_STORE_NAME),
            trending_tags=await self._content.list_trending_tags(active_only=True),
            categories=await self._store.top_categories(),
            animal_types=await self._store.animal_types(),
        )

    async def home(self) -> HomePage:
        frame = await self.frame()
        now = now_naive_ist()
        blocks = []
        for section in await self._content.list_home_sections(visible_only=True):
            block = await self._block(section, frame, now)
            if block is not None:
                blocks.append(block)
        return HomePage(
            frame=frame,
            hero_banners=await self._content.live_banners(BannerPlacement.HOME_HERO, now),
            blocks=blocks,
        )

    async def _block(self, section: HomeSection, frame: StoreFrame, now) -> HomeBlock | None:
        """The section's content, or None when it has nothing to show."""
        block = HomeBlock(section_type=section.section_type, title=section.title, subtitle=section.subtitle)
        limit = section.item_limit

        match section.section_type:
            case HomeSectionType.CATEGORIES:
                block.categories = frame.categories[:limit]
            case HomeSectionType.FEATURED_ANIMALS:
                block.animals = await self._store.featured_animals(limit)
            case HomeSectionType.FEATURED_PRODUCTS:
                block.products = await self._store.featured_products(limit)
            case HomeSectionType.MIDDLE_BANNERS:
                block.banners = (await self._content.live_banners(BannerPlacement.HOME_MIDDLE, now))[:limit]
            case HomeSectionType.TRENDING:
                block.animals = await self._store.trending_animals(limit)
                block.products = await self._store.trending_products(max(limit - len(block.animals), 0))
            case HomeSectionType.CATEGORY_PRODUCTS:
                if section.category_id is not None:
                    block.category_slug = await self._store.category_slug(section.category_id)
                    block.products = await self._store.category_products(section.category_id, limit)

        return block if block.categories or block.animals or block.products or block.banners else None

    # =========================================================
    # LISTINGS
    # =========================================================

    async def category_ids(self, slug: str) -> tuple[str, set[UUID]] | None:
        """A category's name with its own id and every sub-category's, or None if it is not active."""
        rows = await self._store.all_categories()
        root = next((row for row in rows if row[3] == slug), None)
        if root is None:
            return None
        ids = {root[0]}
        grew = True
        while grew:
            found = {row[0] for row in rows if row[1] in ids}
            grew = not found <= ids
            ids |= found
        return root[2], ids

    async def list_products(self, filters: ProductFilters) -> tuple[list[ProductCard], int]:
        return await self._store.list_products(filters)

    async def list_animals(self, filters: AnimalFilters) -> tuple[list[AnimalCard], int]:
        return await self._store.list_animals(filters)

    async def animal_type_id(self, slug: str) -> UUID | None:
        return await self._store.animal_type_id(slug)

    async def breeds_of_type(self, animal_type_id: UUID) -> list[BreedOption]:
        return await self._store.breeds_of_type(animal_type_id)

    # =========================================================
    # DETAILS
    # =========================================================

    async def product_page(self, slug: str) -> tuple[ProductDetail, list[ProductCard]] | None:
        product = await self._store.product_detail(slug)
        if product is None:
            return None
        return product, await self._store.related_products(product.category_id, slug, _RELATED_LIMIT)

    async def animal_page(self, slug: str) -> tuple[AnimalDetail, list[AnimalCard]] | None:
        animal = await self._store.animal_detail(slug)
        if animal is None:
            return None
        return animal, await self._store.similar_animals(animal.animal_type_id, slug, _RELATED_LIMIT)

    # =========================================================
    # SEARCH ENGINES
    # =========================================================

    async def sitemap(self) -> tuple[list[SitemapListing], list[SitemapListing], list[str]]:
        """Live products, live animals (never sold ones) and every active category slug."""
        categories = await self._store.all_categories()
        return (
            await self._store.sitemap_products(_SITEMAP_LIMIT),
            await self._store.sitemap_animals(_SITEMAP_LIMIT),
            [row[3] for row in categories],
        )

    # =========================================================
    # ENQUIRIES
    # =========================================================

    async def create_enquiry(self, command: CreateEnquiryCommand) -> None:
        errors: dict[str, str] = {}
        name = command.buyer_name.strip()
        if len(name) < 2:
            errors["buyer_name"] = "Please enter your name."
        phone = normalize_indian_mobile(command.buyer_phone)
        if phone is None:
            errors["buyer_phone"] = "Please enter a 10 digit mobile number."
        if errors:
            raise ListingValidationException(errors)

        async with self._database.transaction():
            target = await self._store.enquiry_target(command.animal_slug)
            if target is None:
                raise AnimalNotFoundException()
            animal_id, seller_id, title, status = target
            if status == AnimalStatus.SOLD:
                raise AnimalNotAvailableException()
            # The same buyer asking again is not a new lead, and this limits form flooding
            if await self._store.open_enquiry_exists(animal_id, phone):
                return
            await self._store.add_enquiry(Enquiry(
                id=uuid4(),
                animal_id=animal_id,
                seller_user_id=seller_id,
                animal_title=title,
                buyer_name=name,
                buyer_phone=phone,
                location=(command.location or "").strip() or None,
                message=(command.message or "").strip() or None,
            ))
