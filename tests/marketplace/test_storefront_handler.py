"""What customers can see, on a real database. Each test isolates its own home sections and listings by flags."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, event, update

from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.storefront_handler import StorefrontHandler
from app.modules.marketplace.domain.enums import AnimalStatus, BannerPlacement, HomeSectionType, ProductStatus
from app.modules.marketplace.infrastructure.merchandising_repository import MerchandisingRepository
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalImageModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceBannerModel,
    MarketplaceCategoryModel,
    MarketplaceHomeSectionModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)
from app.modules.marketplace.infrastructure.storefront_repository import StorefrontRepository
from tests.dataexchange.factories import create_user


class _InRequest:
    def __init__(self, database, target) -> None:
        self._database = database
        self._target = target

    def __getattr__(self, name):
        method = getattr(self._target, name)

        async def call(*args, **kwargs):
            async with self._database.transaction():
                return await method(*args, **kwargs)

        return call


@pytest.fixture
def handler(database) -> StorefrontHandler:
    return _InRequest(database, StorefrontHandler(database, StorefrontRepository(database), MerchandisingRepository(database)))


@pytest.fixture
def store(database) -> StorefrontRepository:
    return _InRequest(database, StorefrontRepository(database))


@pytest.fixture
async def clean_store(database) -> UUID:
    """A store with no listings to show, whatever other tests left; returns a seller id."""
    async with database.transaction() as session:
        await session.execute(update(MarketplaceProductModel).values(is_featured=False, is_trending=False))
        await session.execute(update(MarketplaceAnimalModel).values(is_featured=False, is_trending=False))
        await session.execute(delete(MarketplaceBannerModel))
        await session.execute(delete(MarketplaceHomeSectionModel))
    return await create_user(database, role=Role.SUPER_ADMIN)


async def _category(database, active: bool = True, parent: UUID | None = None) -> UUID:
    row_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=row_id, name=f"Cat {row_id.hex[:6]}", slug=f"c-{row_id.hex}", is_active=active, parent_id=parent))
    return row_id


async def _animal_type(database, active: bool = True) -> UUID:
    row_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceAnimalTypeModel(id=row_id, name=f"Cow {row_id.hex}", slug=f"t-{row_id.hex}", is_active=active))
    return row_id


async def _product(database, seller: UUID, category: UUID, *, status=ProductStatus.PUBLISHED, featured=True, trending=False,
                   deleted=False, sizes=(("1 L", "600", "550", 5, True, True),), image=True) -> str:
    row_id = uuid4()
    slug = f"p-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceProductModel(
            id=row_id, seller_user_id=seller, category_id=category, title=f"Product {row_id.hex[:6]}", slug=slug,
            status=status, is_featured=featured, is_trending=trending, is_deleted=deleted,
        ))
        await session.flush()
        for order, (name, mrp, price, stock, default, active) in enumerate(sizes):
            session.add(MarketplaceProductVariantModel(
                product_id=row_id, name=name, mrp=Decimal(mrp), price=Decimal(price), stock=stock,
                is_default=default, is_active=active, sort_order=order,
            ))
        if image:
            session.add(MarketplaceProductImageModel(product_id=row_id, url=f"/api/v1/media/product/{row_id.hex}.webp"))
    return slug


async def _animal(database, seller: UUID, type_id: UUID, *, status=AnimalStatus.PUBLISHED, featured=True, deleted=False, **extra) -> str:
    row_id = uuid4()
    slug = f"a-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceAnimalModel(
            id=row_id, seller_user_id=seller, animal_type_id=type_id, title=f"Animal {row_id.hex[:6]}", slug=slug,
            price=Decimal("85000"), status=status, is_featured=featured, is_deleted=deleted, **extra,
        ))
        await session.flush()
        session.add(MarketplaceAnimalImageModel(animal_id=row_id, url=f"/api/v1/media/animal/{row_id.hex}.webp"))
    return slug


async def _section(database, kind: HomeSectionType, order: int, *, visible=True, category: UUID | None = None, limit=8, title=None) -> None:
    async with database.transaction() as session:
        session.add(MarketplaceHomeSectionModel(
            section_type=kind, title=title or kind.value, sort_order=order, is_visible=visible, category_id=category, item_limit=limit,
        ))


# =========================================================
# WHAT IS HIDDEN
# =========================================================


async def test_only_published_products_with_an_active_size_in_an_active_category(database, store, clean_store):
    seller, live_category = clean_store, await _category(database)
    off_category = await _category(database, active=False)

    live = await _product(database, seller, live_category)
    hidden = [
        await _product(database, seller, live_category, status=ProductStatus.DRAFT),
        await _product(database, seller, live_category, status=ProductStatus.ARCHIVED),
        await _product(database, seller, live_category, deleted=True),
        await _product(database, seller, off_category),
        await _product(database, seller, live_category, sizes=(("1 L", "600", "550", 5, True, False),)),
        await _product(database, seller, live_category, sizes=()),
    ]

    slugs = [card.slug for card in await store.featured_products(50)]

    assert live in slugs
    assert not set(hidden) & set(slugs)


async def test_only_published_or_reserved_animals_of_an_active_type(database, store, clean_store):
    seller, cow = clean_store, await _animal_type(database)
    off_type = await _animal_type(database, active=False)

    shown = {
        await _animal(database, seller, cow),
        await _animal(database, seller, cow, status=AnimalStatus.RESERVED),
    }
    hidden = {
        await _animal(database, seller, cow, status=AnimalStatus.DRAFT),
        await _animal(database, seller, cow, status=AnimalStatus.SOLD),
        await _animal(database, seller, cow, status=AnimalStatus.ARCHIVED),
        await _animal(database, seller, cow, deleted=True),
        await _animal(database, seller, off_type),
    }

    slugs = {card.slug for card in await store.featured_animals(50)}

    assert shown <= slugs
    assert not hidden & slugs


async def test_cards_carry_no_seller_or_internal_fields(database, store, clean_store):
    await _product(database, clean_store, await _category(database))
    await _animal(database, clean_store, await _animal_type(database), health_notes="internal")
    product = (await store.featured_products(1))[0]
    animal = (await store.featured_animals(1))[0]

    for card in (product, animal):
        assert not hasattr(card, "seller_user_id")
        assert not hasattr(card, "id")
    assert not hasattr(animal, "health_notes")


# =========================================================
# CARD NUMBERS
# =========================================================


async def test_product_card_shows_the_default_active_size(database, store, clean_store):
    category = await _category(database)
    slug = await _product(database, clean_store, category, sizes=(
        ("500 ml", "320", "299", 0, False, True),
        ("1 L", "600", "450", 3, True, True),
        ("5 L", "2800", "2600", 9, False, False),
    ))

    card = next(c for c in await store.featured_products(50) if c.slug == slug)

    assert (card.size, card.price, card.mrp) == ("1 L", Decimal("450.00"), Decimal("600.00"))
    assert card.discount_percent == 25
    assert card.other_sizes == 1  # the inactive size is not counted
    assert card.in_stock is True


async def test_out_of_stock_and_no_discount(database, store, clean_store):
    slug = await _product(database, clean_store, await _category(database), sizes=(("1 L", "600", "600", 0, True, True),))
    card = next(c for c in await store.featured_products(50) if c.slug == slug)
    assert card.in_stock is False
    assert card.discount_percent == 0


async def test_animal_card_carries_what_buyers_compare(database, store, clean_store):
    cow = await _animal_type(database)
    breed_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceAnimalBreedModel(id=breed_id, animal_type_id=cow, name="Gir"))
    slug = await _animal(
        database, clean_store, cow, breed_id=breed_id, lactation_number=2, milk_litres_per_day=Decimal("14.5"),
        age_months=48, district="Jaipur", state="Rajasthan", is_negotiable=True,
    )

    card = next(c for c in await store.featured_animals(50) if c.slug == slug)

    assert card.breed_name == "Gir"
    assert (card.lactation_number, card.milk_litres_per_day, card.age_months) == (2, Decimal("14.50"), 48)
    assert card.location == "Jaipur, Rajasthan"
    assert card.is_negotiable is True


# =========================================================
# HOME SECTIONS
# =========================================================


async def test_home_follows_order_and_drops_hidden_and_empty_sections(database, handler, clean_store):
    await _product(database, clean_store, await _category(database))
    await _section(database, HomeSectionType.FEATURED_PRODUCTS, 2)
    await _section(database, HomeSectionType.CATEGORIES, 1)
    await _section(database, HomeSectionType.FEATURED_ANIMALS, 0)  # empty: no featured animals
    await _section(database, HomeSectionType.TRENDING, 3, visible=False)
    await _section(database, HomeSectionType.MIDDLE_BANNERS, 4)  # empty: no banners

    home = await handler.home()

    assert [block.section_type for block in home.blocks] == [HomeSectionType.CATEGORIES, HomeSectionType.FEATURED_PRODUCTS]


async def test_item_limit_is_respected(database, handler, clean_store):
    category = await _category(database)
    for _ in range(3):
        await _product(database, clean_store, category)
    await _section(database, HomeSectionType.FEATURED_PRODUCTS, 0, limit=2)

    assert len((await handler.home()).blocks[0].products) == 2


async def test_category_section_shows_only_that_category(database, handler, clean_store):
    wanted, other = await _category(database), await _category(database)
    slug = await _product(database, clean_store, wanted, featured=False)
    await _product(database, clean_store, other, featured=False)
    await _section(database, HomeSectionType.CATEGORY_PRODUCTS, 0, category=wanted)

    block = (await handler.home()).blocks[0]

    assert [card.slug for card in block.products] == [slug]
    assert block.category_slug is not None


async def test_trending_mixes_animals_and_products_within_the_limit(database, handler, clean_store):
    category, cow = await _category(database), await _animal_type(database)
    for _ in range(2):
        await _product(database, clean_store, category, featured=False, trending=True)
    async with database.transaction() as session:
        session.add(MarketplaceAnimalModel(
            seller_user_id=clean_store, animal_type_id=cow, title="Gir", slug=f"gir-{uuid4().hex}", price=Decimal("1"),
            status=AnimalStatus.PUBLISHED, is_trending=True,
        ))
    await _section(database, HomeSectionType.TRENDING, 0, limit=2)

    block = (await handler.home()).blocks[0]

    assert (len(block.animals), len(block.products)) == (1, 1)


async def test_hero_only_has_live_top_banners(database, handler, clean_store):
    now = now_naive_ist()
    mark = uuid4().hex
    async with database.transaction() as session:
        session.add(MarketplaceBannerModel(title=f"live {mark}", image_url="/a.webp"))
        session.add(MarketplaceBannerModel(title=f"off {mark}", image_url="/a.webp", is_active=False))
        session.add(MarketplaceBannerModel(title=f"later {mark}", image_url="/a.webp", starts_at=now.replace(year=now.year + 1)))
        session.add(MarketplaceBannerModel(title=f"middle {mark}", image_url="/a.webp", placement=BannerPlacement.HOME_MIDDLE))

    home = await handler.home()

    assert [banner.title for banner in home.hero_banners] == [f"live {mark}"]


async def test_inactive_and_child_categories_are_not_top_level(database, store, clean_store):
    parent = await _category(database)
    child = await _category(database, parent=parent)
    off = await _category(database, active=False)

    tiles = {tile.slug for tile in await store.top_categories()}

    assert f"c-{parent.hex}" in tiles
    assert f"c-{child.hex}" not in tiles
    assert f"c-{off.hex}" not in tiles


async def test_home_query_count_does_not_grow_with_cards(database, handler, clean_store):
    category = await _category(database)
    await _section(database, HomeSectionType.FEATURED_PRODUCTS, 0, limit=24)

    async def count_queries() -> int:
        statements = 0

        def count(*_args):
            nonlocal statements
            statements += 1

        async with database.transaction() as session:
            engine = session.get_bind()
            event.listen(engine, "before_cursor_execute", count)
        try:
            await handler.home()
        finally:
            event.remove(engine, "before_cursor_execute", count)
        return statements

    await _product(database, clean_store, category)
    few = await count_queries()
    for _ in range(12):
        await _product(database, clean_store, category)
    many = await count_queries()

    assert many == few
