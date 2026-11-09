"""Catalog repository and seller scope (DECISION-016), against a real SQLite database."""

from dataclasses import replace
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import event, select

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.entities import (
    Animal,
    AnimalType,
    Category,
    ListingImage,
    Product,
    ProductVariant,
)
from app.modules.marketplace.domain.enums import AnimalStatus, ProductStatus
from app.modules.marketplace.domain.exceptions import (
    AnimalNotFoundException,
    ProductNotFoundException,
)
from app.modules.marketplace.infrastructure.models import (
    MarketplaceOrderItemModel,
    MarketplaceOrderModel,
    MarketplaceProductVariantModel,
)
from app.modules.marketplace.infrastructure.repository import MarketplaceRepository
from tests.dataexchange.factories import create_user


def _viewer(user_id: UUID, role: Role) -> CurrentUser:
    return CurrentUser(id=user_id, role=str(int(role)))


@pytest.fixture
def repository(database) -> MarketplaceRepository:
    return MarketplaceRepository(database)


@pytest.fixture
async def category(database, repository) -> Category:
    entity = Category(id=uuid4(), name="Ghee", slug=f"ghee-{uuid4().hex}")
    async with database.transaction():
        await repository.save_category(entity)
    return entity


@pytest.fixture
async def animal_type(database, repository) -> AnimalType:
    entity = AnimalType(id=uuid4(), name=f"Cow {uuid4().hex}", slug=f"cow-{uuid4().hex}")
    async with database.transaction():
        await repository.save_animal_type(entity)
    return entity


@pytest.fixture
async def sellers(database) -> tuple[CurrentUser, CurrentUser, CurrentUser]:
    return (
        _viewer(await create_user(database, role=Role.SUPER_ADMIN), Role.SUPER_ADMIN),
        _viewer(await create_user(database, role=Role.ADMIN), Role.ADMIN),
        _viewer(await create_user(database, role=Role.SUB_ADMIN), Role.SUB_ADMIN),
    )


def _product(seller_id: UUID, category_id: UUID, title: str = "Desi Ghee") -> Product:
    return Product(
        id=uuid4(), seller_user_id=seller_id, category_id=category_id, title=title,
        slug=f"p-{uuid4().hex}", status=ProductStatus.PUBLISHED,
        specifications=[{"label": "Shelf life", "value": "6 months"}],
        variants=[
            ProductVariant(id=uuid4(), name="500 ml", mrp=Decimal("320"), price=Decimal("299"), stock=4, sort_order=0),
            ProductVariant(id=uuid4(), name="1 L", mrp=Decimal("600"), price=Decimal("550"), stock=7, sort_order=1),
        ],
        images=[ListingImage(id=uuid4(), url="/api/v1/media/product/a.jpg")],
    )


def _animal(seller_id: UUID, type_id: UUID) -> Animal:
    return Animal(
        id=uuid4(), seller_user_id=seller_id, animal_type_id=type_id, title="Gir cow", slug=f"a-{uuid4().hex}",
        price=Decimal("85000"), lactation_number=2, milk_litres_per_day=Decimal("14.50"),
        status=AnimalStatus.PUBLISHED, images=[ListingImage(id=uuid4(), url="/api/v1/media/animal/a.jpg")],
    )


async def _add_product(database, repository, product: Product) -> Product:
    async with database.transaction():
        await repository.create_product(product)
    return product


async def test_product_round_trip_keeps_every_detail(database, repository, category, sellers):
    root, _, _ = sellers
    product = await _add_product(database, repository, _product(root.id, category.id))

    async with database.transaction():
        stored = await repository.get_product(product.id, root)

    assert stored == product


async def test_animal_round_trip_keeps_milk_and_lactation(database, repository, animal_type, sellers):
    root, _, _ = sellers
    animal = _animal(root.id, animal_type.id)
    async with database.transaction():
        await repository.create_animal(animal)

    async with database.transaction():
        stored = await repository.get_animal(animal.id, root)

    assert stored.milk_litres_per_day == Decimal("14.50")
    assert stored.lactation_number == 2
    assert [image.url for image in stored.images] == ["/api/v1/media/animal/a.jpg"]


# =========================================================
# SELLER SCOPE
# =========================================================


async def test_super_admin_sees_every_seller(database, repository, category, sellers):
    root, admin, _ = sellers
    mark = f"scope-{uuid4().hex}"
    await _add_product(database, repository, _product(root.id, category.id, mark))
    await _add_product(database, repository, _product(admin.id, category.id, mark))

    async with database.transaction():
        items, total = await repository.list_products(root, mark, 0, 10)

    assert total == 2
    assert {item.seller_user_id for item in items} == {root.id, admin.id}


async def test_other_seller_sees_only_their_own(database, repository, category, sellers):
    root, admin, sub_admin = sellers
    mark = f"scope-{uuid4().hex}"
    await _add_product(database, repository, _product(root.id, category.id, mark))
    own = await _add_product(database, repository, _product(admin.id, category.id, mark))

    async with database.transaction():
        admin_items, admin_total = await repository.list_products(admin, mark, 0, 10)
        _, sub_total = await repository.list_products(sub_admin, mark, 0, 10)

    assert admin_total == 1 and [item.id for item in admin_items] == [own.id]
    assert sub_total == 0


async def test_other_sellers_product_reads_as_not_found(database, repository, category, sellers):
    root, admin, _ = sellers
    foreign = await _add_product(database, repository, _product(root.id, category.id))

    async with database.transaction():
        assert await repository.get_product(foreign.id, admin) is None
    with pytest.raises(ProductNotFoundException):
        async with database.transaction():
            await repository.update_product(replace(foreign, title="Hijacked"), admin)
    with pytest.raises(ProductNotFoundException):
        async with database.transaction():
            await repository.delete_product(foreign.id, admin)

    async with database.transaction():
        unchanged = await repository.get_product(foreign.id, root)
    assert unchanged.title == foreign.title


async def test_other_sellers_animal_reads_as_not_found(database, repository, animal_type, sellers):
    root, admin, _ = sellers
    foreign = _animal(root.id, animal_type.id)
    async with database.transaction():
        await repository.create_animal(foreign)

    async with database.transaction():
        assert await repository.get_animal(foreign.id, admin) is None
    with pytest.raises(AnimalNotFoundException):
        async with database.transaction():
            await repository.update_animal(replace(foreign, title="Hijacked"), admin)
    with pytest.raises(AnimalNotFoundException):
        async with database.transaction():
            await repository.delete_animal(foreign.id, admin)


async def test_admin_can_manage_own_listing_so_the_seam_works(database, repository, category, sellers):
    _, admin, _ = sellers
    own = await _add_product(database, repository, _product(admin.id, category.id))

    async with database.transaction():
        await repository.update_product(replace(own, title="Renamed"), admin)
    async with database.transaction():
        assert (await repository.get_product(own.id, admin)).title == "Renamed"


async def test_no_viewer_gets_nothing(database, repository, category, sellers):
    root, _, _ = sellers
    product = await _add_product(database, repository, _product(root.id, category.id))
    async with database.transaction():
        assert await repository.get_product(product.id, None) is None


# =========================================================
# SOFT DELETE, UPDATE, QUERY COUNT
# =========================================================


async def test_soft_deleted_listing_leaves_lists_and_records_who(database, repository, category, sellers):
    root, _, _ = sellers
    mark = f"del-{uuid4().hex}"
    product = await _add_product(database, repository, _product(root.id, category.id, mark))

    async with database.transaction():
        await repository.delete_product(product.id, root)

    async with database.transaction():
        assert await repository.get_product(product.id, root) is None
        assert await repository.list_products(root, mark, 0, 10) == ([], 0)
    with pytest.raises(ProductNotFoundException):
        async with database.transaction():
            await repository.delete_product(product.id, root)


async def test_update_keeps_variant_ids_so_order_lines_stay_linked(database, repository, category, sellers):
    root, _, _ = sellers
    product = await _add_product(database, repository, _product(root.id, category.id))
    kept, dropped = product.variants
    added = ProductVariant(id=uuid4(), name="5 L", mrp=Decimal("2800"), price=Decimal("2600"), stock=2, sort_order=2)

    order_id, line_id = uuid4(), uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceOrderModel(
            id=order_id, order_ref=f"T{order_id.hex[:12]}", buyer_name="Asha", buyer_phone="9000000000",
            address_line="Village", pincode="302001", subtotal=Decimal("299"), total=Decimal("299"),
        ))
        await session.flush()
        session.add(MarketplaceOrderItemModel(
            id=line_id, order_id=order_id, product_id=product.id, variant_id=kept.id, product_title=product.title,
            variant_name=kept.name, mrp=kept.mrp, unit_price=kept.price, quantity=1, line_total=kept.price,
        ))

    updated = replace(product, variants=[replace(kept, stock=99), added])
    async with database.transaction():
        await repository.update_product(updated, root)

    async with database.transaction() as session:
        stored = await repository.get_product(product.id, root)
        line_variant = await session.scalar(
            select(MarketplaceOrderItemModel.variant_id).where(MarketplaceOrderItemModel.id == line_id)
        )
        dropped_row = await session.get(MarketplaceProductVariantModel, dropped.id)

    assert {variant.name: variant.stock for variant in stored.variants} == {"500 ml": 99, "5 L": 2}
    assert line_variant == kept.id
    assert dropped_row is None


async def test_list_query_count_does_not_grow_with_items(database, repository, category, sellers):
    root, _, _ = sellers
    mark = f"count-{uuid4().hex}"
    for _ in range(20):
        await _add_product(database, repository, _product(root.id, category.id, mark))

    async def queries_for(limit: int) -> tuple[int, int]:
        statements = 0

        def count(*_args):
            nonlocal statements
            statements += 1

        async with database.transaction() as session:
            engine = session.get_bind()
            event.listen(engine, "before_cursor_execute", count)
            try:
                items, _ = await repository.list_products(root, mark, 0, limit)
            finally:
                event.remove(engine, "before_cursor_execute", count)
        return statements, len(items)

    small, small_items = await queries_for(2)
    large, large_items = await queries_for(20)
    assert (small_items, large_items) == (2, 20)
    assert large == small
