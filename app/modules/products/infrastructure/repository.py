from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.manager import DatabaseManager
from app.modules.products.domain.entities import Product, ProductImage
from app.modules.products.domain.irepository import IProductRepository
from app.modules.products.infrastructure.mapper import ProductMapper
from app.modules.products.infrastructure.models import (
    ProductModel,
    ProductImageModel,
)


class ProductRepository(IProductRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    async def create(
        self,
        entity: Product,
    ) -> None:
        model = ProductMapper.to_product_model(entity)
        self._session.add(model)

    async def update(
        self,
        entity: Product,
    ) -> None:
        model = await self._session.get(ProductModel, entity.id)
        if model is None:
            return

        model.name = entity.name
        model.description = entity.description
        model.price = entity.price
        model.discount_percent = entity.discount_percent
        model.profile_image_id = entity.profile_image_id
        model.address_id = entity.address_id
        model.contact_name = entity.contact_name
        model.contact_number = entity.contact_number
        model.contact_email = entity.contact_email
        model.is_active = entity.is_active
        model.updated_at = entity.updated_at

    async def get_by_id(
        self,
        id: UUID,
    ) -> Product | None:
        stmt = select(ProductModel).where(
            ProductModel.id == id,
            ProductModel.is_active == True,
        )
        model = await self._session.scalar(stmt)
        if model is None:
            return None
        return ProductMapper.to_product_entity(model)

    async def list(
        self,
        offset: int,
        limit: int,
    ) -> list[Product]:
        stmt = (
            select(ProductModel)
            .where(ProductModel.is_active == True)
            .order_by(ProductModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        result = await self._session.scalars(stmt)
        return [ProductMapper.to_product_entity(model) for model in result]

    async def count(self) -> int:
        from sqlalchemy import func
        stmt = select(func.count(ProductModel.id)).where(
            ProductModel.is_active == True
        )
        return await self._session.scalar(stmt) or 0

    async def add_image(
        self,
        entity: ProductImage,
    ) -> None:
        model = ProductMapper.to_image_model(entity)
        self._session.add(model)

    async def get_images(
        self,
        product_id: UUID,
    ) -> list[ProductImage]:
        stmt = select(ProductImageModel).where(
            ProductImageModel.product_id == product_id,
            ProductImageModel.is_active == True,
        )
        result = await self._session.scalars(stmt)
        return [ProductMapper.to_image_entity(model) for model in result]