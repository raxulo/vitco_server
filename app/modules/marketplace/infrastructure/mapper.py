"""
Entity <-> model mapping for the marketplace catalog.

Python 3.13+
"""

from __future__ import annotations

from app.modules.marketplace.domain.entities import (
    Animal,
    AnimalBreed,
    AnimalType,
    Category,
    ListingImage,
    Product,
    ProductVariant,
)
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalImageModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)

_CATEGORY_FIELDS = ("name", "slug", "parent_id", "description", "image_url", "sort_order", "is_active")
_ANIMAL_TYPE_FIELDS = ("name", "slug", "image_url", "sort_order", "is_active")
_ANIMAL_BREED_FIELDS = ("animal_type_id", "name", "sort_order", "is_active")
_IMAGE_FIELDS = ("url", "media_id", "alt_text", "sort_order")
_VARIANT_FIELDS = (
    "name", "sku", "mrp", "price", "stock", "low_stock_threshold", "is_default", "is_active", "sort_order",
)
_PRODUCT_FIELDS = (
    "category_id", "title", "slug", "brand", "short_description", "description", "specifications",
    "status", "is_featured", "is_trending", "sort_order", "updated_by",
)
_ANIMAL_FIELDS = (
    "animal_type_id", "breed_id", "title", "slug", "gender", "price", "is_negotiable", "age_months",
    "lactation_number", "milk_litres_per_day", "fat_percent", "pregnancy_status", "pregnancy_months",
    "calf_details", "health_notes", "vaccination_notes", "state", "district", "village", "description",
    "status", "is_featured", "is_trending", "sort_order", "updated_by",
)


def _copy(source, target, fields: tuple[str, ...]) -> None:
    for name in fields:
        setattr(target, name, getattr(source, name))


def _values(source, fields: tuple[str, ...]) -> dict:
    return {name: getattr(source, name) for name in fields}


def _sync_children(existing: list, entities: list, build, fields: tuple[str, ...]) -> None:
    """Update rows that stay, add new ones and drop the rest; keeps ids so order lines stay linked."""
    by_id = {child.id: child for child in existing}
    wanted = []
    for entity in entities:
        child = by_id.get(entity.id)
        if child is None:
            child = build(entity)
        else:
            _copy(entity, child, fields)
        wanted.append(child)
    existing[:] = wanted


class MarketplaceMapper:

    __slots__ = ()

    # ----- Masters -----

    @staticmethod
    def category_to_entity(model: MarketplaceCategoryModel) -> Category:
        return Category(id=model.id, created_by=model.created_by, **_values(model, _CATEGORY_FIELDS))

    @staticmethod
    def category_to_model(entity: Category) -> MarketplaceCategoryModel:
        return MarketplaceCategoryModel(id=entity.id, created_by=entity.created_by, **_values(entity, _CATEGORY_FIELDS))

    @staticmethod
    def apply_category(entity: Category, model: MarketplaceCategoryModel) -> None:
        _copy(entity, model, _CATEGORY_FIELDS)

    @staticmethod
    def animal_type_to_entity(model: MarketplaceAnimalTypeModel) -> AnimalType:
        return AnimalType(id=model.id, created_by=model.created_by, **_values(model, _ANIMAL_TYPE_FIELDS))

    @staticmethod
    def animal_type_to_model(entity: AnimalType) -> MarketplaceAnimalTypeModel:
        return MarketplaceAnimalTypeModel(id=entity.id, created_by=entity.created_by, **_values(entity, _ANIMAL_TYPE_FIELDS))

    @staticmethod
    def apply_animal_type(entity: AnimalType, model: MarketplaceAnimalTypeModel) -> None:
        _copy(entity, model, _ANIMAL_TYPE_FIELDS)

    @staticmethod
    def animal_breed_to_entity(model: MarketplaceAnimalBreedModel) -> AnimalBreed:
        return AnimalBreed(id=model.id, created_by=model.created_by, **_values(model, _ANIMAL_BREED_FIELDS))

    @staticmethod
    def animal_breed_to_model(entity: AnimalBreed) -> MarketplaceAnimalBreedModel:
        return MarketplaceAnimalBreedModel(id=entity.id, created_by=entity.created_by, **_values(entity, _ANIMAL_BREED_FIELDS))

    @staticmethod
    def apply_animal_breed(entity: AnimalBreed, model: MarketplaceAnimalBreedModel) -> None:
        _copy(entity, model, _ANIMAL_BREED_FIELDS)

    # ----- Products -----

    @staticmethod
    def product_to_entity(model: MarketplaceProductModel) -> Product:
        return Product(
            id=model.id,
            seller_user_id=model.seller_user_id,
            created_by=model.created_by,
            variants=[ProductVariant(id=v.id, **_values(v, _VARIANT_FIELDS)) for v in model.variants],
            images=[ListingImage(id=i.id, **_values(i, _IMAGE_FIELDS)) for i in model.images],
            **(_values(model, _PRODUCT_FIELDS) | {"specifications": list(model.specifications or [])}),
        )

    @staticmethod
    def product_to_model(entity: Product) -> MarketplaceProductModel:
        return MarketplaceProductModel(
            id=entity.id,
            seller_user_id=entity.seller_user_id,
            created_by=entity.created_by,
            variants=[MarketplaceMapper._variant_model(v) for v in entity.variants],
            images=[MarketplaceMapper._product_image_model(i) for i in entity.images],
            **_values(entity, _PRODUCT_FIELDS),
        )

    @staticmethod
    def apply_product(entity: Product, model: MarketplaceProductModel) -> None:
        _copy(entity, model, _PRODUCT_FIELDS)
        _sync_children(model.variants, entity.variants, MarketplaceMapper._variant_model, _VARIANT_FIELDS)
        _sync_children(model.images, entity.images, MarketplaceMapper._product_image_model, _IMAGE_FIELDS)

    @staticmethod
    def _variant_model(entity: ProductVariant) -> MarketplaceProductVariantModel:
        return MarketplaceProductVariantModel(id=entity.id, **_values(entity, _VARIANT_FIELDS))

    @staticmethod
    def _product_image_model(entity: ListingImage) -> MarketplaceProductImageModel:
        return MarketplaceProductImageModel(id=entity.id, **_values(entity, _IMAGE_FIELDS))

    # ----- Animals -----

    @staticmethod
    def animal_to_entity(model: MarketplaceAnimalModel) -> Animal:
        return Animal(
            id=model.id,
            seller_user_id=model.seller_user_id,
            created_by=model.created_by,
            images=[ListingImage(id=i.id, **_values(i, _IMAGE_FIELDS)) for i in model.images],
            **_values(model, _ANIMAL_FIELDS),
        )

    @staticmethod
    def animal_to_model(entity: Animal) -> MarketplaceAnimalModel:
        return MarketplaceAnimalModel(
            id=entity.id,
            seller_user_id=entity.seller_user_id,
            created_by=entity.created_by,
            images=[MarketplaceMapper._animal_image_model(i) for i in entity.images],
            **_values(entity, _ANIMAL_FIELDS),
        )

    @staticmethod
    def apply_animal(entity: Animal, model: MarketplaceAnimalModel) -> None:
        _copy(entity, model, _ANIMAL_FIELDS)
        _sync_children(model.images, entity.images, MarketplaceMapper._animal_image_model, _IMAGE_FIELDS)

    @staticmethod
    def _animal_image_model(entity: ListingImage) -> MarketplaceAnimalImageModel:
        return MarketplaceAnimalImageModel(id=entity.id, **_values(entity, _IMAGE_FIELDS))
