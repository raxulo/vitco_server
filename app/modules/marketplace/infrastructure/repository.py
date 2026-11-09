"""
Marketplace catalog repository.

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import delete, false, func, or_, select, true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.dto import CatalogOverview, LowStockItem
from app.modules.marketplace.domain.entities import (
    Animal,
    AnimalBreed,
    AnimalType,
    Category,
    Enquiry,
    ListingViewer,
    Product,
)
from app.modules.marketplace.domain.enums import (
    AnimalStatus,
    EnquiryStatus,
    OrderStatus,
    ProductStatus,
)
from app.modules.marketplace.domain.exceptions import (
    AnimalNotFoundException,
    EnquiryNotFoundException,
    ProductNotFoundException,
)
from app.modules.marketplace.domain.irepository import IMarketplaceRepository
from app.modules.marketplace.infrastructure.mapper import MarketplaceMapper
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceEnquiryModel,
    MarketplaceOrderItemModel,
    MarketplaceOrderModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)


class MarketplaceAccessScope:
    """Super Admin reaches every listing, another seller only their own, nobody else anything."""

    __slots__ = ()

    @staticmethod
    def condition(viewer: ListingViewer | None, seller_column):
        if viewer is None:
            return false()
        if viewer.role_type == Role.SUPER_ADMIN:
            return true()
        return seller_column == viewer.id


class MarketplaceRepository(IMarketplaceRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # MASTERS
    # =========================================================

    async def save_category(self, category: Category) -> None:
        model = await self._session.get(MarketplaceCategoryModel, category.id)
        if model is None:
            self._session.add(MarketplaceMapper.category_to_model(category))
        else:
            MarketplaceMapper.apply_category(category, model)

    async def get_category(self, category_id: UUID) -> Category | None:
        model = await self._session.get(MarketplaceCategoryModel, category_id)
        return None if model is None else MarketplaceMapper.category_to_entity(model)

    async def list_categories(self, active_only: bool = False) -> list[Category]:
        stmt = select(MarketplaceCategoryModel).order_by(
            MarketplaceCategoryModel.sort_order, MarketplaceCategoryModel.name
        )
        if active_only:
            stmt = stmt.where(MarketplaceCategoryModel.is_active.is_(True))
        return [MarketplaceMapper.category_to_entity(m) for m in await self._session.scalars(stmt)]

    async def category_slug_taken(self, slug: str) -> bool:
        return await self._exists(select(MarketplaceCategoryModel.id).where(MarketplaceCategoryModel.slug == slug))

    async def category_usage(self, category_id: UUID) -> int:
        products = await self._count(select(MarketplaceProductModel.id).where(MarketplaceProductModel.category_id == category_id))
        children = await self._count(select(MarketplaceCategoryModel.id).where(MarketplaceCategoryModel.parent_id == category_id))
        return products + children

    async def delete_category(self, category_id: UUID) -> None:
        await self._session.execute(delete(MarketplaceCategoryModel).where(MarketplaceCategoryModel.id == category_id))

    async def get_animal_type(self, animal_type_id: UUID) -> AnimalType | None:
        model = await self._session.get(MarketplaceAnimalTypeModel, animal_type_id)
        return None if model is None else MarketplaceMapper.animal_type_to_entity(model)

    async def animal_type_name_taken(self, name: str, exclude_id: UUID | None = None) -> bool:
        stmt = select(MarketplaceAnimalTypeModel.id).where(func.lower(MarketplaceAnimalTypeModel.name) == name.lower())
        if exclude_id is not None:
            stmt = stmt.where(MarketplaceAnimalTypeModel.id != exclude_id)
        return await self._exists(stmt)

    async def animal_type_usage(self, animal_type_id: UUID) -> int:
        animals = await self._count(select(MarketplaceAnimalModel.id).where(MarketplaceAnimalModel.animal_type_id == animal_type_id))
        breeds = await self._count(select(MarketplaceAnimalBreedModel.id).where(MarketplaceAnimalBreedModel.animal_type_id == animal_type_id))
        return animals + breeds

    async def delete_animal_type(self, animal_type_id: UUID) -> None:
        await self._session.execute(delete(MarketplaceAnimalTypeModel).where(MarketplaceAnimalTypeModel.id == animal_type_id))

    async def get_animal_breed(self, breed_id: UUID) -> AnimalBreed | None:
        model = await self._session.get(MarketplaceAnimalBreedModel, breed_id)
        return None if model is None else MarketplaceMapper.animal_breed_to_entity(model)

    async def breed_name_taken(self, animal_type_id: UUID, name: str, exclude_id: UUID | None = None) -> bool:
        stmt = select(MarketplaceAnimalBreedModel.id).where(
            MarketplaceAnimalBreedModel.animal_type_id == animal_type_id,
            func.lower(MarketplaceAnimalBreedModel.name) == name.lower(),
        )
        if exclude_id is not None:
            stmt = stmt.where(MarketplaceAnimalBreedModel.id != exclude_id)
        return await self._exists(stmt)

    async def animal_breed_usage(self, breed_id: UUID) -> int:
        return await self._count(select(MarketplaceAnimalModel.id).where(MarketplaceAnimalModel.breed_id == breed_id))

    async def delete_animal_breed(self, breed_id: UUID) -> None:
        await self._session.execute(delete(MarketplaceAnimalBreedModel).where(MarketplaceAnimalBreedModel.id == breed_id))

    async def _exists(self, stmt) -> bool:
        return await self._session.scalar(stmt.limit(1)) is not None

    async def _count(self, stmt) -> int:
        return await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0

    # =========================================================
    # ENQUIRIES
    # =========================================================

    async def list_enquiries(
        self, viewer: ListingViewer, keyword: str | None, status: EnquiryStatus | None, offset: int, limit: int
    ) -> tuple[list[Enquiry], int]:
        stmt = select(MarketplaceEnquiryModel).where(
            MarketplaceAccessScope.condition(viewer, MarketplaceEnquiryModel.seller_user_id)
        )
        if status is not None:
            stmt = stmt.where(MarketplaceEnquiryModel.status == status)
        if keyword and keyword.strip():
            term = keyword.strip()
            stmt = stmt.where(or_(
                MarketplaceEnquiryModel.buyer_name.icontains(term, autoescape=True),
                MarketplaceEnquiryModel.buyer_phone.icontains(term, autoescape=True),
                MarketplaceEnquiryModel.animal_title.icontains(term, autoescape=True),
            ))
        total = await self._count(stmt)
        page = stmt.order_by(MarketplaceEnquiryModel.created_at.desc()).offset(offset).limit(limit)
        return [
            Enquiry(
                id=model.id, animal_id=model.animal_id, seller_user_id=model.seller_user_id,
                animal_title=model.animal_title, buyer_name=model.buyer_name, buyer_phone=model.buyer_phone,
                location=model.location, message=model.message, status=model.status,
                admin_notes=model.admin_notes, created_at=model.created_at,
            )
            for model in await self._session.scalars(page)
        ], total

    async def update_enquiry(
        self, enquiry_id: UUID, viewer: ListingViewer, status: EnquiryStatus, notes: str | None
    ) -> None:
        model = await self._session.scalar(
            select(MarketplaceEnquiryModel).where(
                MarketplaceEnquiryModel.id == enquiry_id,
                MarketplaceAccessScope.condition(viewer, MarketplaceEnquiryModel.seller_user_id),
            )
        )
        if model is None:
            raise EnquiryNotFoundException()
        model.status = status
        model.admin_notes = notes
        model.updated_by = viewer.id

    # =========================================================
    # OVERVIEW
    # =========================================================

    async def overview(self, viewer: ListingViewer) -> CatalogOverview:
        return CatalogOverview(
            products_total=await self._count(self._products(viewer)),
            products_published=await self._count(
                self._products(viewer).where(MarketplaceProductModel.status == ProductStatus.PUBLISHED)
            ),
            animals_total=await self._count(self._animals(viewer)),
            animals_live=await self._count(
                self._animals(viewer).where(MarketplaceAnimalModel.status == AnimalStatus.PUBLISHED)
            ),
            low_stock_variants=await self._count(self._low_stock(viewer)),
            new_orders=await self._count(
                select(MarketplaceOrderModel.id).where(
                    MarketplaceOrderModel.status == OrderStatus.PLACED,
                    MarketplaceOrderModel.id.in_(
                        select(MarketplaceOrderItemModel.order_id).where(
                            MarketplaceAccessScope.condition(viewer, MarketplaceOrderItemModel.seller_user_id)
                        )
                    ),
                )
            ),
            new_enquiries=await self._count(
                select(MarketplaceEnquiryModel.id).where(
                    MarketplaceEnquiryModel.status == EnquiryStatus.NEW,
                    MarketplaceAccessScope.condition(viewer, MarketplaceEnquiryModel.seller_user_id),
                )
            ),
        )

    async def low_stock(self, viewer: ListingViewer, limit: int) -> list[LowStockItem]:
        rows = await self._session.execute(
            self._low_stock(viewer).order_by(MarketplaceProductVariantModel.stock).limit(limit)
        )
        return [
            LowStockItem(
                product_id=row.product_id,
                product_title=row.product_title,
                variant_name=row.variant_name,
                stock=row.stock,
                low_stock_threshold=row.low_stock_threshold,
            )
            for row in rows
        ]

    @staticmethod
    def _low_stock(viewer: ListingViewer):
        """Active sizes of published products at or below their threshold."""
        return (
            select(
                MarketplaceProductModel.id.label("product_id"),
                MarketplaceProductModel.title.label("product_title"),
                MarketplaceProductVariantModel.name.label("variant_name"),
                MarketplaceProductVariantModel.stock,
                MarketplaceProductVariantModel.low_stock_threshold,
            )
            .join(MarketplaceProductModel, MarketplaceProductModel.id == MarketplaceProductVariantModel.product_id)
            .where(
                MarketplaceProductModel.is_deleted.is_(False),
                MarketplaceProductModel.status == ProductStatus.PUBLISHED,
                MarketplaceProductVariantModel.is_active.is_(True),
                MarketplaceProductVariantModel.stock <= MarketplaceProductVariantModel.low_stock_threshold,
                MarketplaceAccessScope.condition(viewer, MarketplaceProductModel.seller_user_id),
            )
        )

    # =========================================================
    # ANIMAL TYPES & BREEDS
    # =========================================================

    async def save_animal_type(self, animal_type: AnimalType) -> None:
        model = await self._session.get(MarketplaceAnimalTypeModel, animal_type.id)
        if model is None:
            self._session.add(MarketplaceMapper.animal_type_to_model(animal_type))
        else:
            MarketplaceMapper.apply_animal_type(animal_type, model)

    async def list_animal_types(self, active_only: bool = False) -> list[AnimalType]:
        stmt = select(MarketplaceAnimalTypeModel).order_by(
            MarketplaceAnimalTypeModel.sort_order, MarketplaceAnimalTypeModel.name
        )
        if active_only:
            stmt = stmt.where(MarketplaceAnimalTypeModel.is_active.is_(True))
        return [MarketplaceMapper.animal_type_to_entity(m) for m in await self._session.scalars(stmt)]

    async def save_animal_breed(self, breed: AnimalBreed) -> None:
        model = await self._session.get(MarketplaceAnimalBreedModel, breed.id)
        if model is None:
            self._session.add(MarketplaceMapper.animal_breed_to_model(breed))
        else:
            MarketplaceMapper.apply_animal_breed(breed, model)

    async def list_animal_breeds(
        self, animal_type_id: UUID | None = None, active_only: bool = False
    ) -> list[AnimalBreed]:
        stmt = select(MarketplaceAnimalBreedModel).order_by(
            MarketplaceAnimalBreedModel.sort_order, MarketplaceAnimalBreedModel.name
        )
        if animal_type_id is not None:
            stmt = stmt.where(MarketplaceAnimalBreedModel.animal_type_id == animal_type_id)
        if active_only:
            stmt = stmt.where(MarketplaceAnimalBreedModel.is_active.is_(True))
        return [MarketplaceMapper.animal_breed_to_entity(m) for m in await self._session.scalars(stmt)]

    # =========================================================
    # PRODUCTS
    # =========================================================

    @staticmethod
    def _products(viewer: ListingViewer | None):
        return select(MarketplaceProductModel).where(
            MarketplaceProductModel.is_deleted.is_(False),
            MarketplaceAccessScope.condition(viewer, MarketplaceProductModel.seller_user_id),
        )

    @staticmethod
    def _with_product_children(stmt):
        return stmt.options(
            selectinload(MarketplaceProductModel.variants),
            selectinload(MarketplaceProductModel.images),
        )

    async def _product_model(self, product_id: UUID, viewer: ListingViewer) -> MarketplaceProductModel | None:
        stmt = self._with_product_children(self._products(viewer).where(MarketplaceProductModel.id == product_id))
        return await self._session.scalar(stmt)

    async def create_product(self, product: Product) -> None:
        self._session.add(MarketplaceMapper.product_to_model(product))

    async def update_product(self, product: Product, viewer: ListingViewer) -> None:
        model = await self._product_model(product.id, viewer)
        if model is None:
            raise ProductNotFoundException()
        MarketplaceMapper.apply_product(product, model)

    async def get_product(self, product_id: UUID, viewer: ListingViewer) -> Product | None:
        model = await self._product_model(product_id, viewer)
        return None if model is None else MarketplaceMapper.product_to_entity(model)

    async def product_slug_taken(self, slug: str) -> bool:
        return await self._exists(select(MarketplaceProductModel.id).where(MarketplaceProductModel.slug == slug))

    async def sku_taken(self, sku: str, exclude_variant_ids: set[UUID]) -> bool:
        stmt = select(MarketplaceProductVariantModel.id).where(MarketplaceProductVariantModel.sku == sku)
        if exclude_variant_ids:
            stmt = stmt.where(MarketplaceProductVariantModel.id.not_in(exclude_variant_ids))
        return await self._exists(stmt)

    async def list_products(
        self, viewer: ListingViewer, keyword: str | None, offset: int, limit: int, status: ProductStatus | None = None
    ) -> tuple[list[Product], int]:
        stmt = self._products(viewer)
        if status is not None:
            stmt = stmt.where(MarketplaceProductModel.status == status)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(MarketplaceProductModel.title.ilike(pattern), MarketplaceProductModel.brand.ilike(pattern))
            )
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        page = self._with_product_children(stmt).order_by(
            MarketplaceProductModel.sort_order, MarketplaceProductModel.created_at.desc()
        ).offset(offset).limit(limit)
        return [MarketplaceMapper.product_to_entity(m) for m in await self._session.scalars(page)], total

    async def delete_product(self, product_id: UUID, viewer: ListingViewer) -> None:
        model = await self._session.scalar(self._products(viewer).where(MarketplaceProductModel.id == product_id))
        if model is None:
            raise ProductNotFoundException()
        model.is_deleted = True
        model.deleted_at = now_naive_ist()
        model.deleted_by = viewer.id

    # =========================================================
    # ANIMALS
    # =========================================================

    @staticmethod
    def _animals(viewer: ListingViewer | None):
        return select(MarketplaceAnimalModel).where(
            MarketplaceAnimalModel.is_deleted.is_(False),
            MarketplaceAccessScope.condition(viewer, MarketplaceAnimalModel.seller_user_id),
        )

    async def _animal_model(self, animal_id: UUID, viewer: ListingViewer) -> MarketplaceAnimalModel | None:
        stmt = (
            self._animals(viewer)
            .where(MarketplaceAnimalModel.id == animal_id)
            .options(selectinload(MarketplaceAnimalModel.images))
        )
        return await self._session.scalar(stmt)

    async def create_animal(self, animal: Animal) -> None:
        self._session.add(MarketplaceMapper.animal_to_model(animal))

    async def update_animal(self, animal: Animal, viewer: ListingViewer) -> None:
        model = await self._animal_model(animal.id, viewer)
        if model is None:
            raise AnimalNotFoundException()
        MarketplaceMapper.apply_animal(animal, model)

    async def get_animal(self, animal_id: UUID, viewer: ListingViewer) -> Animal | None:
        model = await self._animal_model(animal_id, viewer)
        return None if model is None else MarketplaceMapper.animal_to_entity(model)

    async def animal_slug_taken(self, slug: str) -> bool:
        return await self._exists(select(MarketplaceAnimalModel.id).where(MarketplaceAnimalModel.slug == slug))

    async def list_animals(
        self, viewer: ListingViewer, keyword: str | None, offset: int, limit: int, status: AnimalStatus | None = None
    ) -> tuple[list[Animal], int]:
        stmt = self._animals(viewer)
        if status is not None:
            stmt = stmt.where(MarketplaceAnimalModel.status == status)
        if keyword and keyword.strip():
            pattern = f"%{keyword.strip()}%"
            stmt = stmt.where(
                or_(MarketplaceAnimalModel.title.ilike(pattern), MarketplaceAnimalModel.district.ilike(pattern))
            )
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        page = stmt.options(selectinload(MarketplaceAnimalModel.images)).order_by(
            MarketplaceAnimalModel.sort_order, MarketplaceAnimalModel.created_at.desc()
        ).offset(offset).limit(limit)
        return [MarketplaceMapper.animal_to_entity(m) for m in await self._session.scalars(page)], total

    async def delete_animal(self, animal_id: UUID, viewer: ListingViewer) -> None:
        model = await self._session.scalar(self._animals(viewer).where(MarketplaceAnimalModel.id == animal_id))
        if model is None:
            raise AnimalNotFoundException()
        model.is_deleted = True
        model.deleted_at = now_naive_ist()
        model.deleted_by = viewer.id
