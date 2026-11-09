"""
Marketplace catalog use cases, used by the Control Center.

Selling rights are checked here so they hold for every caller (DECISION-016). Masters
(categories, animal types, breeds) are shared by all sellers, so only Super Admin edits them.

Images are decoded before the first write of a save, because decoding takes far longer
than the write-lock budget (DECISION-010).

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any
from uuid import UUID, uuid4

from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.command import (
    SaveAnimalBreedCommand,
    SaveAnimalCommand,
    SaveAnimalTypeCommand,
    SaveCategoryCommand,
    SaveProductCommand,
    UpdateEnquiryCommand,
    VariantInput,
)
from app.modules.marketplace.domain.dto import CatalogOverview, LowStockItem
from app.modules.marketplace.domain.entities import (
    Animal,
    AnimalBreed,
    AnimalType,
    Category,
    Enquiry,
    ListingImage,
    ListingViewer,
    Product,
    ProductVariant,
)
from app.modules.marketplace.domain.enums import AnimalStatus, EnquiryStatus, ProductStatus
from app.modules.marketplace.domain.exceptions import (
    AnimalBreedNotFoundException,
    AnimalNotFoundException,
    AnimalTypeNotFoundException,
    CategoryNotFoundException,
    ListingValidationException,
    MasterInUseException,
    ProductNotFoundException,
    SellingNotAllowedException,
)
from app.modules.marketplace.domain.irepository import IMarketplaceRepository
from app.modules.marketplace.domain.policy import SellerPolicy
from app.modules.marketplace.domain.slug import slugify
from app.modules.media.application.services import MediaService, MediaUrlService
from app.modules.media.domain.enums import MediaCategory

MAX_LISTING_IMAGES = 8
_LOW_STOCK_LIST_SIZE = 8
_LIVE_ANIMAL_STATUSES = frozenset({AnimalStatus.PUBLISHED, AnimalStatus.RESERVED, AnimalStatus.SOLD})


class MarketplaceCatalogHandler:

    __slots__ = ("_database", "_repository", "_media")

    def __init__(
        self,
        database: DatabaseManager,
        repository: IMarketplaceRepository,
        media_service: MediaService,
    ) -> None:
        self._database = database
        self._repository = repository
        self._media = media_service

    # =========================================================
    # OVERVIEW
    # =========================================================

    async def overview(self, owner: ListingViewer | None) -> tuple[CatalogOverview, list[LowStockItem]]:
        seller = self._seller(owner)
        return (
            await self._repository.overview(seller),
            await self._repository.low_stock(seller, _LOW_STOCK_LIST_SIZE),
        )

    async def waiting_counts(self, owner: ListingViewer | None) -> tuple[int, int]:
        """New orders and new enquiries, shown on the Control Center tabs."""
        seller = self._seller(owner)
        return (
            await self._repository.count_new_orders(seller),
            await self._repository.count_new_enquiries(seller),
        )

    # =========================================================
    # CATEGORIES
    # =========================================================

    async def list_categories(self, owner: ListingViewer | None) -> list[Category]:
        self._seller(owner)
        return await self._repository.list_categories()

    async def save_category(self, command: SaveCategoryCommand) -> Category:
        owner = self._super_admin(command.owner)
        name = command.name.strip()
        errors = {"name": "Enter a category name."} if not name else {}
        image = await self._prepare_one(command.new_image, errors)
        if errors:
            raise ListingValidationException(errors)

        async with self._database.transaction():
            current = await self._category_or_none(command.id)
            await self._ensure_valid_parent(command.id, command.parent_id)
            image_url = await self._replace_image(
                current.image_url if current else None, image, command, MediaCategory.CATEGORY, owner, name
            )
            category = Category(
                id=current.id if current else uuid4(),
                name=name,
                slug=current.slug if current else await self._unique_slug(name, self._repository.category_slug_taken),
                parent_id=command.parent_id,
                description=self._clean(command.description),
                image_url=image_url,
                sort_order=command.sort_order,
                is_active=command.is_active,
                created_by=current.created_by if current else owner.id,
            )
            await self._repository.save_category(category)
        return category

    async def delete_category(self, owner: ListingViewer | None, category_id: UUID) -> None:
        self._super_admin(owner)
        async with self._database.transaction():
            category = await self._repository.get_category(category_id)
            if category is None:
                raise CategoryNotFoundException()
            if await self._repository.category_usage(category_id):
                raise MasterInUseException("This category has products or sub-categories. Deactivate it instead.")
            await self._repository.delete_category(category_id)
            await self._media.delete_image_by_url(category.image_url)

    async def _category_or_none(self, category_id: UUID | None) -> Category | None:
        if category_id is None:
            return None
        category = await self._repository.get_category(category_id)
        if category is None:
            raise CategoryNotFoundException()
        return category

    async def _ensure_valid_parent(self, category_id: UUID | None, parent_id: UUID | None) -> None:
        """Walking up from the new parent must never reach the category itself."""
        seen: set[UUID] = set()
        current = parent_id
        while current is not None and current not in seen:
            if current == category_id:
                raise ListingValidationException({"parent_id": "A category cannot sit inside itself."})
            seen.add(current)
            parent = await self._repository.get_category(current)
            if parent is None:
                raise ListingValidationException({"parent_id": "Choose an existing category."})
            current = parent.parent_id

    # =========================================================
    # ANIMAL TYPES & BREEDS
    # =========================================================

    async def list_animal_types(self, owner: ListingViewer | None) -> list[AnimalType]:
        self._seller(owner)
        return await self._repository.list_animal_types()

    async def list_animal_breeds(self, owner: ListingViewer | None) -> list[AnimalBreed]:
        self._seller(owner)
        return await self._repository.list_animal_breeds()

    async def save_animal_type(self, command: SaveAnimalTypeCommand) -> AnimalType:
        owner = self._super_admin(command.owner)
        name = command.name.strip()
        errors = {"name": "Enter a name."} if not name else {}
        image = await self._prepare_one(command.new_image, errors)
        if errors:
            raise ListingValidationException(errors)

        async with self._database.transaction():
            current = None
            if command.id is not None:
                current = await self._repository.get_animal_type(command.id)
                if current is None:
                    raise AnimalTypeNotFoundException()
            if await self._repository.animal_type_name_taken(name, command.id):
                raise ListingValidationException({"name": "This animal type already exists."})
            image_url = await self._replace_image(
                current.image_url if current else None, image, command, MediaCategory.CATEGORY, owner, name
            )
            animal_type = AnimalType(
                id=current.id if current else uuid4(),
                name=name,
                slug=current.slug if current else await self._unique_type_slug(name),
                image_url=image_url,
                sort_order=command.sort_order,
                is_active=command.is_active,
                created_by=current.created_by if current else owner.id,
            )
            await self._repository.save_animal_type(animal_type)
        return animal_type

    async def _unique_type_slug(self, name: str) -> str:
        taken = {animal_type.slug for animal_type in await self._repository.list_animal_types()}

        async def is_taken(slug: str) -> bool:
            return slug in taken

        return await self._unique_slug(name, is_taken)

    async def delete_animal_type(self, owner: ListingViewer | None, animal_type_id: UUID) -> None:
        self._super_admin(owner)
        async with self._database.transaction():
            animal_type = await self._repository.get_animal_type(animal_type_id)
            if animal_type is None:
                raise AnimalTypeNotFoundException()
            if await self._repository.animal_type_usage(animal_type_id):
                raise MasterInUseException("This type has animals or breeds. Deactivate it instead.")
            await self._repository.delete_animal_type(animal_type_id)
            await self._media.delete_image_by_url(animal_type.image_url)

    async def save_animal_breed(self, command: SaveAnimalBreedCommand) -> AnimalBreed:
        owner = self._super_admin(command.owner)
        name = command.name.strip()
        if not name:
            raise ListingValidationException({"name": "Enter a breed name."})

        async with self._database.transaction():
            if await self._repository.get_animal_type(command.animal_type_id) is None:
                raise AnimalTypeNotFoundException()
            current = None
            if command.id is not None:
                current = await self._repository.get_animal_breed(command.id)
                if current is None:
                    raise AnimalBreedNotFoundException()
            if await self._repository.breed_name_taken(command.animal_type_id, name, command.id):
                raise ListingValidationException({"name": "This breed already exists for this animal type."})
            breed = AnimalBreed(
                id=current.id if current else uuid4(),
                animal_type_id=command.animal_type_id,
                name=name,
                sort_order=command.sort_order,
                is_active=command.is_active,
                created_by=current.created_by if current else owner.id,
            )
            await self._repository.save_animal_breed(breed)
        return breed

    async def delete_animal_breed(self, owner: ListingViewer | None, breed_id: UUID) -> None:
        self._super_admin(owner)
        async with self._database.transaction():
            if await self._repository.get_animal_breed(breed_id) is None:
                raise AnimalBreedNotFoundException()
            if await self._repository.animal_breed_usage(breed_id):
                raise MasterInUseException("Animals use this breed. Deactivate it instead.")
            await self._repository.delete_animal_breed(breed_id)

    # =========================================================
    # PRODUCTS
    # =========================================================

    async def list_products(
        self, owner: ListingViewer | None, keyword: str | None, status: ProductStatus | None, offset: int, limit: int
    ) -> tuple[list[Product], int]:
        return await self._repository.list_products(self._seller(owner), keyword, offset, limit, status)

    async def get_product(self, owner: ListingViewer | None, product_id: UUID) -> Product:
        product = await self._repository.get_product(product_id, self._seller(owner))
        if product is None:
            raise ProductNotFoundException()
        return product

    async def save_product(self, command: SaveProductCommand) -> Product:
        owner = self._seller(command.owner)
        errors: dict[str, str] = {}
        prepared = await self._prepare_many(command.new_images, errors)

        async with self._database.transaction():
            current = None
            if command.id is not None:
                current = await self._repository.get_product(command.id, owner)
                if current is None:
                    raise ProductNotFoundException()

            if await self._repository.get_category(command.category_id) is None:
                errors["category_id"] = "Choose a category."

            current_images = current.images if current else []
            images = self._arrange_images(current_images, command.keep_image_ids, prepared, errors)
            variants = self._build_variants(command.variants, current.variants if current else [])
            product = Product(
                id=current.id if current else uuid4(),
                seller_user_id=current.seller_user_id if current else owner.id,
                category_id=command.category_id,
                title=command.title.strip(),
                slug=current.slug if current else "",
                brand=self._clean(command.brand),
                short_description=self._clean(command.short_description),
                description=self._clean(command.description),
                specifications=command.specifications,
                status=command.status,
                is_featured=command.is_featured,
                is_trending=command.is_trending,
                sort_order=command.sort_order,
                variants=variants,
                images=images,
                created_by=current.created_by if current else owner.id,
                updated_by=owner.id,
            )

            errors = {**product.problems(), **errors}
            if product.status == ProductStatus.PUBLISHED:
                errors = {**product.publish_problems(), **errors}
            kept_variant_ids = {variant.id for variant in current.variants} if current else set()
            for variant in variants:
                if variant.sku and await self._repository.sku_taken(variant.sku, kept_variant_ids):
                    errors["variants"] = f"SKU {variant.sku} is already used by another product."
            if errors:
                raise ListingValidationException(errors)

            await self._store_images(images, prepared, MediaCategory.PRODUCT, owner, product.title)
            if current is None:
                product.slug = await self._unique_slug(product.title, self._repository.product_slug_taken)
                await self._repository.create_product(product)
            else:
                await self._repository.update_product(product, owner)
            await self._delete_removed_images(current_images, images)
        return product

    async def delete_product(self, owner: ListingViewer | None, product_id: UUID) -> None:
        seller = self._seller(owner)
        async with self._database.transaction():
            await self._repository.delete_product(product_id, seller)

    @staticmethod
    def _build_variants(inputs: list[VariantInput], current: list[ProductVariant]) -> list[ProductVariant]:
        """Only this product's own variant ids are kept; anything else becomes a new row."""
        own_ids = {variant.id for variant in current}
        variants = [
            ProductVariant(
                id=item.id if item.id in own_ids else uuid4(),
                name=item.name.strip(),
                sku=(item.sku or "").strip() or None,
                mrp=item.mrp,
                price=item.price,
                stock=item.stock,
                low_stock_threshold=item.low_stock_threshold,
                is_active=item.is_active,
                is_default=item.is_default,
                sort_order=order,
            )
            for order, item in enumerate(inputs)
        ]
        # Exactly one default: the first one asked for, else the first active size
        default = next((v for v in variants if v.is_default and v.is_active), None)
        default = default or next((v for v in variants if v.is_active), None)
        for variant in variants:
            variant.is_default = variant is default
        return variants

    # =========================================================
    # ANIMALS
    # =========================================================

    async def list_animals(
        self, owner: ListingViewer | None, keyword: str | None, status: AnimalStatus | None, offset: int, limit: int
    ) -> tuple[list[Animal], int]:
        return await self._repository.list_animals(self._seller(owner), keyword, offset, limit, status)

    async def get_animal(self, owner: ListingViewer | None, animal_id: UUID) -> Animal:
        animal = await self._repository.get_animal(animal_id, self._seller(owner))
        if animal is None:
            raise AnimalNotFoundException()
        return animal

    async def save_animal(self, command: SaveAnimalCommand) -> Animal:
        owner = self._seller(command.owner)
        errors: dict[str, str] = {}
        prepared = await self._prepare_many(command.new_images, errors)

        async with self._database.transaction():
            current = None
            if command.id is not None:
                current = await self._repository.get_animal(command.id, owner)
                if current is None:
                    raise AnimalNotFoundException()

            if await self._repository.get_animal_type(command.animal_type_id) is None:
                errors["animal_type_id"] = "Choose an animal type."
            if command.breed_id is not None:
                breed = await self._repository.get_animal_breed(command.breed_id)
                if breed is None or breed.animal_type_id != command.animal_type_id:
                    errors["breed_id"] = "Choose a breed of this animal type."

            current_images = current.images if current else []
            images = self._arrange_images(current_images, command.keep_image_ids, prepared, errors)
            animal = Animal(
                id=current.id if current else uuid4(),
                seller_user_id=current.seller_user_id if current else owner.id,
                animal_type_id=command.animal_type_id,
                breed_id=command.breed_id,
                title=command.title.strip(),
                slug=current.slug if current else "",
                gender=command.gender,
                price=command.price,
                is_negotiable=command.is_negotiable,
                age_months=command.age_months,
                lactation_number=command.lactation_number,
                milk_litres_per_day=command.milk_litres_per_day,
                fat_percent=command.fat_percent,
                pregnancy_status=command.pregnancy_status,
                pregnancy_months=command.pregnancy_months,
                calf_details=self._clean(command.calf_details),
                health_notes=self._clean(command.health_notes),
                vaccination_notes=self._clean(command.vaccination_notes),
                state=self._clean(command.state),
                district=self._clean(command.district),
                village=self._clean(command.village),
                description=self._clean(command.description),
                status=command.status,
                is_featured=command.is_featured,
                is_trending=command.is_trending,
                sort_order=command.sort_order,
                images=images,
                created_by=current.created_by if current else owner.id,
                updated_by=owner.id,
            )

            errors = {**animal.problems(), **errors}
            if animal.status in _LIVE_ANIMAL_STATUSES:
                errors = {**animal.publish_problems(), **errors}
            if errors:
                raise ListingValidationException(errors)

            await self._store_images(images, prepared, MediaCategory.ANIMAL, owner, animal.title)
            if current is None:
                animal.slug = await self._unique_slug(animal.title, self._repository.animal_slug_taken)
                await self._repository.create_animal(animal)
            else:
                await self._repository.update_animal(animal, owner)
            await self._delete_removed_images(current_images, images)
        return animal

    async def delete_animal(self, owner: ListingViewer | None, animal_id: UUID) -> None:
        seller = self._seller(owner)
        async with self._database.transaction():
            await self._repository.delete_animal(animal_id, seller)

    # =========================================================
    # ENQUIRIES
    # =========================================================

    async def list_enquiries(
        self, owner: ListingViewer | None, keyword: str | None, status: EnquiryStatus | None, offset: int, limit: int
    ) -> tuple[list[Enquiry], int]:
        return await self._repository.list_enquiries(self._seller(owner), keyword, status, offset, limit)

    async def update_enquiry(self, command: UpdateEnquiryCommand) -> None:
        seller = self._seller(command.owner)
        async with self._database.transaction():
            await self._repository.update_enquiry(command.id, seller, command.status, self._clean(command.admin_notes))

    # =========================================================
    # ACCESS
    # =========================================================

    @staticmethod
    def _seller(owner: ListingViewer | None) -> ListingViewer:
        if owner is None:
            raise SellingNotAllowedException()
        SellerPolicy.ensure_can_sell(owner.role_type)
        return owner

    @staticmethod
    def _super_admin(owner: ListingViewer | None) -> ListingViewer:
        if owner is None or owner.role_type != Role.SUPER_ADMIN:
            raise SellingNotAllowedException("Only the Super Admin can change categories and animal types.")
        return owner

    # =========================================================
    # IMAGES
    # =========================================================

    async def _prepare_one(self, file: Any | None, errors: dict[str, str]) -> Any | None:
        if file is None:
            return None
        try:
            return await self._media.prepare_listing_image(file)
        except ValueError as error:
            errors["image"] = str(error)
            return None

    async def _prepare_many(self, files: list[Any], errors: dict[str, str]) -> list[tuple[Any, Any]]:
        prepared = []
        for file in files:
            try:
                prepared.append((file, await self._media.prepare_listing_image(file)))
            except ValueError as error:
                errors["images"] = f"{getattr(file, 'filename', 'Image')}: {error}"
        return prepared

    @staticmethod
    def _arrange_images(
        current: list[ListingImage],
        keep_ids: list[UUID],
        prepared: list[tuple[Any, Any]],
        errors: dict[str, str],
    ) -> list[ListingImage]:
        """Kept images in the requested order, then new ones; URLs of new ones are filled when stored."""
        by_id = {image.id: image for image in current}
        kept = [by_id[image_id] for image_id in dict.fromkeys(keep_ids) if image_id in by_id]
        images = [replace(image, sort_order=order) for order, image in enumerate(kept)]
        images += [
            ListingImage(id=uuid4(), url="", sort_order=len(kept) + order)
            for order in range(len(prepared))
        ]
        if len(images) > MAX_LISTING_IMAGES:
            errors["images"] = f"A listing can have at most {MAX_LISTING_IMAGES} images."
        return images

    async def _store_images(
        self,
        images: list[ListingImage],
        prepared: list[tuple[Any, Any]],
        category: MediaCategory,
        owner: ListingViewer,
        title: str,
    ) -> None:
        pending = [image for image in images if not image.url]
        for image, (file, processed) in zip(pending, prepared, strict=True):
            media = await self._media.store_listing_image(
                processed, category, owner.id, getattr(file, "filename", None) or title
            )
            image.media_id = media.id
            image.url = MediaUrlService.build(media.storage_key)
            image.alt_text = title

    async def _delete_removed_images(self, before: list[ListingImage], after: list[ListingImage]) -> None:
        kept = {image.id for image in after}
        await self._media.delete_images(
            image.media_id for image in before if image.id not in kept and image.media_id is not None
        )

    async def _replace_image(
        self,
        current_url: str | None,
        prepared: Any | None,
        command: SaveCategoryCommand | SaveAnimalTypeCommand,
        category: MediaCategory,
        owner: ListingViewer,
        name: str,
    ) -> str | None:
        if prepared is None and not command.remove_image:
            return current_url
        await self._media.delete_image_by_url(current_url)
        if prepared is None:
            return None
        media = await self._media.store_listing_image(prepared, category, owner.id, name)
        return MediaUrlService.build(media.storage_key)

    # =========================================================
    # HELPERS
    # =========================================================

    @staticmethod
    def _clean(value: str | None) -> str | None:
        return (value or "").strip() or None

    @staticmethod
    async def _unique_slug(title: str, is_taken: Callable[[str], Awaitable[bool]]) -> str:
        base = slugify(title)
        slug = base
        suffix = 2
        while await is_taken(slug):
            slug = f"{base}-{suffix}"
            suffix += 1
        return slug
