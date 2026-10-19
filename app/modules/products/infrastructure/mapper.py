from __future__ import annotations

from app.modules.products.domain.entities import Product, ProductImage
from app.modules.products.infrastructure.models import ProductModel, ProductImageModel


class ProductMapper:

    @staticmethod
    def to_product_entity(model: ProductModel) -> Product:
        return Product(
            id=model.id,
            name=model.name,
            description=model.description,
            price=model.price,
            discount_percent=model.discount_percent,
            profile_image_id=model.profile_image_id,
            address_id=model.address_id,
            contact_name=model.contact_name,
            contact_number=model.contact_number,
            contact_email=model.contact_email,
            is_active=model.is_active,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_product_model(entity: Product) -> ProductModel:
        return ProductModel(
            id=entity.id,
            name=entity.name,
            description=entity.description,
            price=entity.price,
            discount_percent=entity.discount_percent,
            profile_image_id=entity.profile_image_id,
            address_id=entity.address_id,
            contact_name=entity.contact_name,
            contact_number=entity.contact_number,
            contact_email=entity.contact_email,
            is_active=entity.is_active,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_image_entity(model: ProductImageModel) -> ProductImage:
        return ProductImage(
            id=model.id,
            product_id=model.product_id,
            media_id=model.media_id,
            is_active=model.is_active,
        )

    @staticmethod
    def to_image_model(entity: ProductImage) -> ProductImageModel:
        return ProductImageModel(
            id=entity.id,
            product_id=entity.product_id,
            media_id=entity.media_id,
            is_active=entity.is_active,
        )