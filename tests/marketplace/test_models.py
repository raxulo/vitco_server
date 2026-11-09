"""Marketplace schema: the database itself protects prices, stock and links (real SQLite)."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import delete, func, inspect, select
from sqlalchemy.exc import IntegrityError

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.marketplace.domain.enums import ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceCategoryModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
)
from tests.dataexchange.factories import create_user

MKT_TABLES = {
    "mkt_categories",
    "mkt_animal_types",
    "mkt_animal_breeds",
    "mkt_products",
    "mkt_product_variants",
    "mkt_product_images",
    "mkt_animals",
    "mkt_animal_images",
    "mkt_banners",
    "mkt_home_sections",
    "mkt_trending_tags",
    "mkt_settings",
    "mkt_orders",
    "mkt_order_items",
    "mkt_enquiries",
}


async def _product(database, seller_id: UUID) -> UUID:
    category_id, product_id = uuid4(), uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=category_id, name="Ghee", slug=f"ghee-{category_id.hex}"))
        await session.flush()
        session.add(MarketplaceProductModel(
            id=product_id, seller_user_id=seller_id, category_id=category_id, title="Desi Ghee",
            slug=f"desi-ghee-{product_id.hex}", status=ProductStatus.PUBLISHED,
        ))
    return product_id


def _variant(product_id: UUID, **overrides) -> MarketplaceProductVariantModel:
    values = {"id": uuid4(), "product_id": product_id, "name": "1 L", "mrp": Decimal("600"), "price": Decimal("550"), "stock": 5}
    return MarketplaceProductVariantModel(**(values | overrides))


async def _count(database, model, *where) -> int:
    async with database.transaction() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_all_tables_exist(database):
    async with database.transaction() as session:
        names = await session.run_sync(lambda sync: inspect(sync.connection()).get_table_names())
    assert MKT_TABLES <= set(names)


@pytest.mark.parametrize(
    "bad_values",
    [
        {"stock": -1},
        {"price": Decimal("-1"), "mrp": Decimal("10")},
        {"price": Decimal("700"), "mrp": Decimal("600")},
    ],
    ids=["negative stock", "negative price", "price above MRP"],
)
async def test_database_refuses_bad_variants(database, bad_values):
    seller = await create_user(database, role=Role.SUPER_ADMIN)
    product_id = await _product(database, seller)
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            session.add(_variant(product_id, **bad_values))
    assert await _count(database, MarketplaceProductVariantModel, MarketplaceProductVariantModel.product_id == product_id) == 0


async def test_price_equal_to_mrp_is_allowed(database):
    seller = await create_user(database, role=Role.SUPER_ADMIN)
    product_id = await _product(database, seller)
    async with database.transaction() as session:
        session.add(_variant(product_id, price=Decimal("600")))
    assert await _count(database, MarketplaceProductVariantModel, MarketplaceProductVariantModel.product_id == product_id) == 1


async def test_deleting_a_product_removes_variants_and_images(database):
    seller = await create_user(database, role=Role.SUPER_ADMIN)
    product_id = await _product(database, seller)
    async with database.transaction() as session:
        session.add(_variant(product_id))
        session.add(MarketplaceProductImageModel(id=uuid4(), product_id=product_id, url="/api/v1/media/product/a.jpg"))

    async with database.transaction() as session:
        await session.execute(delete(MarketplaceProductModel).where(MarketplaceProductModel.id == product_id))

    assert await _count(database, MarketplaceProductVariantModel, MarketplaceProductVariantModel.product_id == product_id) == 0
    assert await _count(database, MarketplaceProductImageModel, MarketplaceProductImageModel.product_id == product_id) == 0


async def test_duplicate_slug_is_refused(database):
    seller = await create_user(database, role=Role.SUPER_ADMIN)
    product_id = await _product(database, seller)
    async with database.transaction() as session:
        product = await session.get(MarketplaceProductModel, product_id)
        category_id, slug = product.category_id, product.slug

    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            session.add(MarketplaceProductModel(id=uuid4(), seller_user_id=seller, category_id=category_id, title="Copy", slug=slug))


async def test_user_who_owns_a_product_cannot_be_deleted(database):
    seller = await create_user(database, role=Role.ADMIN)
    await _product(database, seller)
    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            await session.execute(delete(UserModel).where(UserModel.id == seller))
    assert await _count(database, UserModel, UserModel.id == seller) == 1


async def test_settings_can_only_have_one_row(database):
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(id=uuid4(), store_name="First"))

    with pytest.raises(IntegrityError):
        async with database.transaction() as session:
            session.add(MarketplaceSettingsModel(id=uuid4(), store_name="Second"))

    assert await _count(database, MarketplaceSettingsModel) == 1
