"""Starter data: added once, never fake listings, and removed masters stay removed."""

import pytest
from sqlalchemy import delete, func, select

from app.modules.marketplace.domain.enums import HomeSectionType
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceBannerModel,
    MarketplaceCategoryModel,
    MarketplaceHomeSectionModel,
    MarketplaceProductModel,
    MarketplaceSettingsModel,
)
from app.modules.marketplace.infrastructure.seed import MarketplaceSeeder

SEED_TYPE_SLUGS = ("cow", "buffalo", "goat", "sheep")
SEED_CATEGORY_SLUGS = ("milk", "ghee-butter", "curd-paneer", "coconut-oils")


@pytest.fixture
async def unseeded(database) -> MarketplaceSeeder:
    """Removes seeded rows from the shared test database; other tests use their own random slugs."""
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        await session.execute(delete(MarketplaceHomeSectionModel))
        await session.execute(delete(MarketplaceCategoryModel).where(MarketplaceCategoryModel.slug.in_(SEED_CATEGORY_SLUGS)))
        types = select(MarketplaceAnimalTypeModel.id).where(MarketplaceAnimalTypeModel.slug.in_(SEED_TYPE_SLUGS))
        await session.execute(delete(MarketplaceAnimalBreedModel).where(MarketplaceAnimalBreedModel.animal_type_id.in_(types)))
        await session.execute(delete(MarketplaceAnimalTypeModel).where(MarketplaceAnimalTypeModel.slug.in_(SEED_TYPE_SLUGS)))
    return MarketplaceSeeder(database)


async def _count(database, model, *where) -> int:
    async with database.transaction() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_first_run_adds_masters_and_settings(database, unseeded):
    await unseeded.run()

    assert await _count(database, MarketplaceAnimalTypeModel, MarketplaceAnimalTypeModel.slug.in_(SEED_TYPE_SLUGS)) == 4
    assert await _count(database, MarketplaceCategoryModel, MarketplaceCategoryModel.slug.in_(SEED_CATEGORY_SLUGS)) == 4
    async with database.transaction() as session:
        settings = (await session.scalars(select(MarketplaceSettingsModel))).all()
        sections = (await session.scalars(select(MarketplaceHomeSectionModel))).all()
        buffalo_breeds = set(await session.scalars(
            select(MarketplaceAnimalBreedModel.name)
            .join(MarketplaceAnimalTypeModel, MarketplaceAnimalTypeModel.id == MarketplaceAnimalBreedModel.animal_type_id)
            .where(MarketplaceAnimalTypeModel.slug == "buffalo")
        ))
    assert len(settings) == 1 and settings[0].cod_enabled is True
    assert "Murrah" in buffalo_breeds
    assert sections[0].section_type == HomeSectionType.CATEGORIES


async def test_never_adds_fake_listings_or_banners(database, unseeded):
    before = [
        await _count(database, model)
        for model in (MarketplaceProductModel, MarketplaceAnimalModel, MarketplaceBannerModel)
    ]
    await unseeded.run()
    after = [
        await _count(database, model)
        for model in (MarketplaceProductModel, MarketplaceAnimalModel, MarketplaceBannerModel)
    ]
    assert after == before


async def test_second_run_adds_nothing(database, unseeded):
    await unseeded.run()
    await unseeded.run()
    assert await _count(database, MarketplaceSettingsModel) == 1
    assert await _count(database, MarketplaceHomeSectionModel) == 5
    assert await _count(database, MarketplaceCategoryModel, MarketplaceCategoryModel.slug.in_(SEED_CATEGORY_SLUGS)) == 4


async def test_removed_masters_stay_removed_even_when_all_are_gone(database, unseeded):
    await unseeded.run()
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceCategoryModel).where(MarketplaceCategoryModel.slug.in_(SEED_CATEGORY_SLUGS)))

    await unseeded.run()

    assert await _count(database, MarketplaceCategoryModel, MarketplaceCategoryModel.slug.in_(SEED_CATEGORY_SLUGS)) == 0
