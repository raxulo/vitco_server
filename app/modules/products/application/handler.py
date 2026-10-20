from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID, uuid4

from fastapi.exceptions import ValidationException

from app.core.database.manager import DatabaseManager
from app.modules.products.domain.entities import Product, ProductImage
from app.modules.products.domain.exceptions import (
    ProductNotFoundException,
)
from app.modules.products.infrastructure.repository import ProductRepository
from app.modules.products.domain.dto import ProductDto, ProductListDto
from app.core.clock import now_naive_ist
from app.modules.products.application.command import (
    CreateProductCommand,
    UpdateProductCommand,
    DeleteProductCommand,
    AddProductImageCommand,
    GetProductQuery,
    ListProductsQuery,
)


class ProductHandler:

    __slots__ = (
        "_database",
        "_repository",
    )

    def __init__(
        self, 
        database: DatabaseManager,
        repository: ProductRepository,
    ) -> None:
        self._database = database
        self._repository = repository

    # =========================================================
    # CREATE
    # =========================================================

    async def create(
        self,
        command: CreateProductCommand,
    ) -> ProductDto:
        self._validate_pricing(command.price, command.discount_percent)

        product = Product(
            id=uuid4(),
            name=command.name.strip(),
            description=command.description,
            price=command.price,
            discount_percent=command.discount_percent,
            profile_image_id=command.profile_image_id,
            address_id=command.address_id,
            contact_name=command.contact_name,
            contact_number=command.contact_number,
            contact_email=command.contact_email,
            is_active=True,
            created_at=now_naive_ist(),
            updated_at=now_naive_ist(),
        )

        async with self._database.transaction():
            await self._repository.create(product)

        return self._to_dto(product)

    # =========================================================
    # UPDATE
    # =========================================================

    async def update(
        self,
        command: UpdateProductCommand,
    ) -> ProductDto:
        self._validate_pricing(command.price, command.discount_percent)

        async with self._database.transaction():
            product = await self._repository.get_by_id(command.id)
            if product is None:
                raise ProductNotFoundException()

            product.name = command.name.strip()
            product.description = command.description
            product.price = command.price
            product.discount_percent = command.discount_percent
            product.profile_image_id = command.profile_image_id
            product.address_id = command.address_id
            product.contact_name = command.contact_name
            product.contact_number = command.contact_number
            product.contact_email = command.contact_email
            product.is_active = command.is_active
            product.updated_at = now_naive_ist()

            await self._repository.update(product)

        return self._to_dto(product)

    # =========================================================
    # DELETE (SOFT DELETE)
    # =========================================================

    async def delete(
        self,
        command: DeleteProductCommand,
    ) -> None:
        async with self._database.transaction():
            product = await self._repository.get_by_id(command.id)
            if product is None:
                raise ProductNotFoundException()

            product.is_active = False
            product.updated_at = now_naive_ist()
            await self._repository.update(product)

    # =========================================================
    # ADD IMAGE
    # =========================================================

    async def add_image(
        self,
        command: AddProductImageCommand,
    ) -> None:
        async with self._database.transaction():
            product = await self._repository.get_by_id(command.product_id)
            if product is None:
                raise ProductNotFoundException()

            image = ProductImage(
                id=uuid4(),
                product_id=command.product_id,
                media_id=command.media_id,
                is_active=True,
            )
            await self._repository.add_image(image)

    # =========================================================
    # GET / LIST
    # =========================================================

    async def get(
        self,
        query: GetProductQuery,
    ) -> ProductDto:
        product = await self._repository.get_by_id(query.id)
        if product is None:
            raise ProductNotFoundException()

        return self._to_dto(product)

    async def list(
        self,
        query: ListProductsQuery,
    ) -> list[ProductListDto]:
        entities = await self._repository.list(
            offset=query.offset,
            limit=query.size,
        )
        return [
            self._to_list_dto(entity)
            for entity in entities
        ]

    # =========================================================
    # HELPERS & MAPPING
    # =========================================================

    def _to_list_dto(
        self,
        product: Product,
    ) -> ProductListDto:
        return ProductListDto(
            id=product.id,
            name=product.name,
            price=product.price,
            discount_percent=product.discount_percent,
            is_active=product.is_active,
        )

    def _validate_pricing(self, price, discount_percent):
        if price < 0:
            raise ValidationException("Price cannot be negative.")
        if discount_percent < 0 or discount_percent > 100:
            raise ValidationException("Discount percentage must be between 0 and 100.")

    def _to_dto(self, product: Product) -> ProductDto:
        return ProductDto(
            id=product.id,
            name=product.name,
            description=product.description,
            price=product.price,
            discount_percent=product.discount_percent,
            profile_image_id=product.profile_image_id,
            address_id=product.address_id,
            contact_name=product.contact_name,
            contact_number=product.contact_number,
            contact_email=product.contact_email,
            is_active=product.is_active,
        )