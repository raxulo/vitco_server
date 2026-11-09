"""
Starter data of a new store: masters and settings, never fake listings or banners.

Runs only until the settings row exists, so whatever the Super Admin later edits
or removes is not recreated on the next start.

Python 3.13+
"""

from __future__ import annotations

from sqlalchemy import select

from app.core.database.manager import DatabaseManager
from app.modules.marketplace.domain.enums import HomeSectionType
from app.modules.marketplace.domain.slug import slugify
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceHomeSectionModel,
    MarketplaceSettingsModel,
)

_ANIMAL_TYPES: dict[str, tuple[str, ...]] = {
    "Cow": ("Gir", "Sahiwal", "Red Sindhi", "Tharparkar", "HF Cross", "Jersey Cross"),
    "Buffalo": ("Murrah", "Mehsana", "Jaffarabadi", "Surti", "Nili-Ravi"),
    "Goat": ("Sirohi", "Jamunapari", "Barbari", "Beetal"),
    "Sheep": ("Nali", "Marwari", "Deccani"),
}

_CATEGORIES = ("Milk", "Ghee & Butter", "Curd & Paneer", "Coconut & Oils")

_HOME_SECTIONS = (
    (HomeSectionType.CATEGORIES, "Shop by category"),
    (HomeSectionType.TRENDING, "Trending now"),
    (HomeSectionType.FEATURED_ANIMALS, "Featured animals"),
    (HomeSectionType.MIDDLE_BANNERS, "Offers"),
    (HomeSectionType.FEATURED_PRODUCTS, "Featured products"),
)


class MarketplaceSeeder:

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    async def run(self) -> None:
        async with self._database.transaction() as session:
            if await session.scalar(select(MarketplaceSettingsModel.id)) is not None:
                return

            existing_types = {
                model.slug: model for model in await session.scalars(select(MarketplaceAnimalTypeModel))
            }
            for type_order, (type_name, breeds) in enumerate(_ANIMAL_TYPES.items()):
                slug = slugify(type_name)
                if slug in existing_types:
                    continue
                animal_type = MarketplaceAnimalTypeModel(name=type_name, slug=slug, sort_order=type_order)
                session.add(animal_type)
                await session.flush()
                session.add_all(
                    MarketplaceAnimalBreedModel(animal_type_id=animal_type.id, name=name, sort_order=order)
                    for order, name in enumerate(breeds)
                )

            existing_categories = set(await session.scalars(select(MarketplaceCategoryModel.slug)))
            for order, name in enumerate(_CATEGORIES):
                slug = slugify(name)
                if slug not in existing_categories:
                    session.add(MarketplaceCategoryModel(name=name, slug=slug, sort_order=order))

            session.add_all(
                MarketplaceHomeSectionModel(section_type=section_type, title=title, sort_order=order)
                for order, (section_type, title) in enumerate(_HOME_SECTIONS)
            )
            session.add(MarketplaceSettingsModel(store_name="Vitco Marketplace"))
