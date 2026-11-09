"""Filters, details and enquiries on a real database. Each test marks its own listings with a unique word."""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.command import CreateEnquiryCommand, UpdateEnquiryCommand
from app.modules.marketplace.application.handler import MarketplaceCatalogHandler
from app.modules.marketplace.application.storefront_handler import StorefrontHandler
from app.modules.marketplace.domain.contact import normalize_indian_mobile
from app.modules.marketplace.domain.dto import AnimalFilters, ProductFilters
from app.modules.marketplace.domain.enums import AnimalStatus, EnquiryStatus, ProductStatus
from app.modules.marketplace.domain.exceptions import (
    AnimalNotAvailableException,
    AnimalNotFoundException,
    EnquiryNotFoundException,
    ListingValidationException,
    SellingNotAllowedException,
)
from app.modules.marketplace.domain.policy import SellerPolicy
from app.modules.marketplace.infrastructure.merchandising_repository import MerchandisingRepository
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalImageModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceEnquiryModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)
from app.modules.marketplace.infrastructure.repository import MarketplaceRepository
from app.modules.marketplace.infrastructure.storefront_repository import StorefrontRepository
from app.modules.media.application.services import MediaService
from app.modules.media.infrastructure.media_repository import MediaRepository
from tests.dataexchange.factories import create_user


class _InRequest:
    def __init__(self, database, target) -> None:
        self._database = database
        self._target = target

    def __getattr__(self, name):
        method = getattr(self._target, name)

        async def call(*args, **kwargs):
            async with self._database.transaction():
                return await method(*args, **kwargs)

        return call


@pytest.fixture
def store(database) -> StorefrontHandler:
    return _InRequest(database, StorefrontHandler(database, StorefrontRepository(database), MerchandisingRepository(database)))


@pytest.fixture
def catalog(database) -> MarketplaceCatalogHandler:
    media = MediaService(repository=MediaRepository(database), storage=None)
    return _InRequest(database, MarketplaceCatalogHandler(database, MarketplaceRepository(database), media))


@pytest.fixture
async def seller(database) -> UUID:
    return await create_user(database, role=Role.SUPER_ADMIN)


@pytest.fixture
def mark() -> str:
    return uuid4().hex[:12]


async def _category(database, parent: UUID | None = None, active: bool = True) -> tuple[UUID, str]:
    row_id = uuid4()
    slug = f"c-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=row_id, name=f"Cat {row_id.hex[:6]}", slug=slug, parent_id=parent, is_active=active))
    return row_id, slug


async def _type(database) -> UUID:
    row_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceAnimalTypeModel(id=row_id, name=f"Type {row_id.hex}", slug=f"t-{row_id.hex}"))
    return row_id


async def _breed(database, type_id: UUID, name: str = "Gir") -> UUID:
    row_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceAnimalBreedModel(id=row_id, animal_type_id=type_id, name=name))
    return row_id


async def _product(database, seller: UUID, category: UUID, title: str, sizes=(("1 L", "600", "500", 5, True),), **fields) -> str:
    row_id = uuid4()
    slug = f"p-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceProductModel(**({
            "id": row_id, "seller_user_id": seller, "category_id": category, "title": title, "slug": slug,
            "status": ProductStatus.PUBLISHED,
        } | fields)))
        await session.flush()
        for order, (name, mrp, price, stock, default) in enumerate(sizes):
            session.add(MarketplaceProductVariantModel(
                product_id=row_id, name=name, mrp=Decimal(mrp), price=Decimal(price), stock=stock,
                is_default=default, sort_order=order, low_stock_threshold=5,
            ))
        session.add(MarketplaceProductImageModel(product_id=row_id, url=f"/media/{row_id.hex}.webp", alt_text="Alt"))
    return slug


async def _animal(database, seller: UUID, type_id: UUID, title: str, price: str = "85000", **fields) -> str:
    row_id = uuid4()
    slug = f"a-{row_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceAnimalModel(**({
            "id": row_id, "seller_user_id": seller, "animal_type_id": type_id, "title": title, "slug": slug,
            "price": Decimal(price), "status": AnimalStatus.PUBLISHED,
        } | fields)))
        await session.flush()
        session.add(MarketplaceAnimalImageModel(animal_id=row_id, url=f"/media/{row_id.hex}.webp"))
    return slug


def _slugs(result) -> list[str]:
    return [card.slug for card in result[0]]


# =========================================================
# PRODUCT LISTING
# =========================================================


async def test_product_search_covers_title_brand_and_short_description(database, store, seller, mark):
    category, _ = await _category(database)
    by_title = await _product(database, seller, category, f"Ghee {mark}")
    by_brand = await _product(database, seller, category, "Other", brand=f"Brand {mark.upper()}")
    by_short = await _product(database, seller, category, "Another", short_description=f"Made with {mark}")
    await _product(database, seller, category, "Unrelated")

    result = await store.list_products(ProductFilters(search=mark))

    assert set(_slugs(result)) == {by_title, by_brand, by_short}
    assert result[1] == 3


@pytest.mark.parametrize("wildcard", ["%", "_", "%%"])
async def test_search_treats_wildcards_as_text(database, store, seller, mark, wildcard):
    category, _ = await _category(database)
    await _product(database, seller, category, f"Plain {mark}")
    result = await store.list_products(ProductFilters(search=f"{mark}{wildcard}"))
    assert result == ([], 0)


async def test_category_filter_includes_sub_categories_only_of_that_branch(database, store, seller, mark):
    parent, parent_slug = await _category(database)
    child, _ = await _category(database, parent=parent)
    grandchild, _ = await _category(database, parent=child)
    other, _ = await _category(database)
    wanted = {
        await _product(database, seller, parent, f"A {mark}"),
        await _product(database, seller, child, f"B {mark}"),
        await _product(database, seller, grandchild, f"C {mark}"),
    }
    await _product(database, seller, other, f"D {mark}")

    name, ids = await store.category_ids(parent_slug)
    result = await store.list_products(ProductFilters(search=mark, category_ids=ids))

    assert name.startswith("Cat ")
    assert set(_slugs(result)) == wanted


async def test_unknown_or_inactive_category_is_none(database, store):
    _, inactive = await _category(database, active=False)
    assert await store.category_ids("nope") is None
    assert await store.category_ids(inactive) is None


async def test_price_filter_and_sort_use_the_price_on_the_card(database, store, seller, mark):
    category, _ = await _category(database)
    # Shown price is 500 (the default size), although a cheaper size exists
    default_500 = await _product(database, seller, category, f"A {mark}", sizes=(("Small", "100", "100", 5, False), ("Big", "600", "500", 5, True)))
    shown_200 = await _product(database, seller, category, f"B {mark}", sizes=(("One", "250", "200", 5, True),))
    no_default_300 = await _product(database, seller, category, f"C {mark}", sizes=(("X", "400", "300", 5, False), ("Y", "900", "800", 5, False)))

    assert _slugs(await store.list_products(ProductFilters(search=mark, sort="price_asc"))) == [shown_200, no_default_300, default_500]
    assert _slugs(await store.list_products(ProductFilters(search=mark, sort="price_desc"))) == [default_500, no_default_300, shown_200]
    assert set(_slugs(await store.list_products(ProductFilters(search=mark, max_price=Decimal("250"))))) == {shown_200}
    assert set(_slugs(await store.list_products(ProductFilters(search=mark, min_price=Decimal("300"), max_price=Decimal("500"))))) == {default_500, no_default_300}


async def test_in_stock_filter(database, store, seller, mark):
    category, _ = await _category(database)
    available = await _product(database, seller, category, f"A {mark}", sizes=(("X", "10", "10", 0, True), ("Y", "10", "10", 1, False)))
    await _product(database, seller, category, f"B {mark}", sizes=(("X", "10", "10", 0, True),))

    assert _slugs(await store.list_products(ProductFilters(search=mark, in_stock_only=True))) == [available]


async def test_pagination_keeps_the_total(database, store, seller, mark):
    category, _ = await _category(database)
    for number in range(5):
        await _product(database, seller, category, f"{number} {mark}", sort_order=number)

    first, total = await store.list_products(ProductFilters(search=mark, limit=2))
    third, _ = await store.list_products(ProductFilters(search=mark, limit=2, offset=4))

    assert total == 5
    assert [card.title[0] for card in first] == ["0", "1"]
    assert [card.title[0] for card in third] == ["4"]


async def test_hidden_products_stay_out_of_every_filter(database, store, seller, mark):
    category, _ = await _category(database)
    await _product(database, seller, category, f"Draft {mark}", status=ProductStatus.DRAFT)
    await _product(database, seller, category, f"Gone {mark}", is_deleted=True)
    assert await store.list_products(ProductFilters(search=mark)) == ([], 0)


# =========================================================
# ANIMAL LISTING
# =========================================================


async def test_animal_filters(database, store, seller, mark):
    cow, buffalo = await _type(database), await _type(database)
    gir = await _breed(database, cow)
    best = await _animal(database, seller, cow, f"Best {mark}", breed_id=gir, milk_litres_per_day=Decimal("16"), lactation_number=2, district="Jaipur", price="90000")
    fresh = await _animal(database, seller, cow, f"Fresh {mark}", milk_litres_per_day=Decimal("8"), lactation_number=1, state="Punjab", price="50000")
    old = await _animal(database, seller, buffalo, f"Old {mark}", milk_litres_per_day=Decimal("12"), lactation_number=6, village="Ramgarh", price="120000")
    none = await _animal(database, seller, buffalo, f"None {mark}", price="10000")

    async def found(**filters) -> set[str]:
        return set(_slugs(await store.list_animals(AnimalFilters(search=mark, **filters))))

    assert await found(animal_type_id=cow) == {best, fresh}
    assert await found(breed_id=gir) == {best}
    assert await found(min_price=Decimal("60000"), max_price=Decimal("100000")) == {best}
    assert await found(min_milk=Decimal("12")) == {best, old}
    assert await found(lactation=1) == {fresh}
    assert await found(lactation=4) == {old}  # "fourth or later"
    assert await found(location="JAIPUR") == {best}
    assert await found(location="punjab") == {fresh}
    assert await found(location="ramgarh") == {old}
    assert await found() == {best, fresh, old, none}


async def test_animal_search_by_breed_and_type(database, store, seller, mark):
    cow = await _type(database)
    breed = await _breed(database, cow, f"Breed{mark}")
    slug = await _animal(database, seller, cow, "Plain title", breed_id=breed)
    assert _slugs(await store.list_animals(AnimalFilters(search=f"breed{mark}"))) == [slug]


async def test_milk_sort_puts_unknown_last(database, store, seller, mark):
    cow = await _type(database)
    unknown = await _animal(database, seller, cow, f"A {mark}")
    low = await _animal(database, seller, cow, f"B {mark}", milk_litres_per_day=Decimal("5"))
    high = await _animal(database, seller, cow, f"C {mark}", milk_litres_per_day=Decimal("15"))

    assert _slugs(await store.list_animals(AnimalFilters(search=mark, sort="milk_desc"))) == [high, low, unknown]


async def test_sold_animals_are_not_listed_but_open_by_link(database, store, seller, mark):
    cow = await _type(database)
    sold = await _animal(database, seller, cow, f"Sold {mark}", status=AnimalStatus.SOLD)

    assert await store.list_animals(AnimalFilters(search=mark)) == ([], 0)
    animal, _ = await store.animal_page(sold)
    assert animal.is_sold is True


@pytest.mark.parametrize("status", [AnimalStatus.DRAFT, AnimalStatus.ARCHIVED])
async def test_unpublished_animal_does_not_open(database, store, seller, mark, status):
    slug = await _animal(database, seller, await _type(database), mark, status=status)
    assert await store.animal_page(slug) is None


async def test_deleted_listing_does_not_open(database, store, seller, mark):
    cow, (category, _) = await _type(database), await _category(database)
    assert await store.animal_page(await _animal(database, seller, cow, mark, is_deleted=True)) is None
    assert await store.product_page(await _product(database, seller, category, mark, is_deleted=True)) is None


# =========================================================
# DETAILS
# =========================================================


async def test_product_page_shows_sizes_without_exact_stock_when_plenty(database, store, seller, mark):
    category, _ = await _category(database)
    slug = await _product(database, seller, category, mark, specifications=[{"label": "Life", "value": "6 months"}], sizes=(
        ("Small", "100", "80", 3, False),
        ("Big", "600", "500", 40, True),
        ("Huge", "900", "800", 0, False),
    ))
    await _product(database, seller, category, f"Other {mark}")

    product, related = await store.product_page(slug)

    small, big, huge = product.sizes
    assert product.default_size is big
    assert (small.few_left, small.discount_percent) == (3, 20)
    assert big.few_left is None
    assert huge.in_stock is False and huge.few_left is None
    assert not hasattr(big, "stock")
    assert product.specifications == [{"label": "Life", "value": "6 months"}]
    assert slug not in [card.slug for card in related] and len(related) == 1


async def test_animal_page_has_every_public_detail_and_no_seller(database, store, seller, mark):
    cow = await _type(database)
    breed = await _breed(database, cow)
    slug = await _animal(
        database, seller, cow, mark, breed_id=breed, milk_litres_per_day=Decimal("14.5"), lactation_number=2,
        fat_percent=Decimal("4.2"), calf_details="Female calf", health_notes="Healthy", vaccination_notes="FMD done",
        village="Ramgarh", district="Jaipur", state="Rajasthan", description="Calm",
    )
    await _animal(database, seller, cow, "Similar")

    animal, similar = await store.animal_page(slug)

    assert animal.breed_name == "Gir"
    assert animal.location == "Ramgarh, Jaipur, Rajasthan"
    assert (animal.calf_details, animal.health_notes, animal.vaccination_notes, animal.description) == ("Female calf", "Healthy", "FMD done", "Calm")
    assert not hasattr(animal, "seller_user_id")
    assert slug not in [card.slug for card in similar] and similar


# =========================================================
# ENQUIRIES
# =========================================================


@pytest.mark.parametrize(
    ("typed", "expected"),
    [
        ("9876543210", "9876543210"), ("+91 98765 43210", "9876543210"), ("919876543210", "9876543210"),
        ("09876543210", "9876543210"), ("98765-43210", "9876543210"),
        ("12345", None), ("1234567890", None), ("abcdefghij", None), ("", None), ("98765432101", None),
    ],
)
def test_indian_mobile(typed, expected):
    assert normalize_indian_mobile(typed) == expected


async def _enquiries(database, slug: str) -> list[MarketplaceEnquiryModel]:
    async with database.transaction() as session:
        animal_id = await session.scalar(select(MarketplaceAnimalModel.id).where(MarketplaceAnimalModel.slug == slug))
        return list(await session.scalars(select(MarketplaceEnquiryModel).where(MarketplaceEnquiryModel.animal_id == animal_id)))


def _enquiry(slug: str, **overrides) -> CreateEnquiryCommand:
    return CreateEnquiryCommand(**({"animal_slug": slug, "buyer_name": "Asha", "buyer_phone": "+91 98765 43210"} | overrides))


async def test_enquiry_is_saved_with_snapshot_seller_and_clean_phone(database, store, seller, mark):
    slug = await _animal(database, seller, await _type(database), f"Gir {mark}")

    await store.create_enquiry(_enquiry(slug, location=" Jaipur ", message=" Is she healthy? "))

    saved = (await _enquiries(database, slug))[0]
    assert (saved.buyer_phone, saved.seller_user_id, saved.animal_title) == ("9876543210", seller, f"Gir {mark}")
    assert (saved.location, saved.message, saved.status) == ("Jaipur", "Is she healthy?", EnquiryStatus.NEW)


async def test_repeat_enquiry_adds_nothing_until_the_first_is_closed(database, store, catalog, seller, mark):
    slug = await _animal(database, seller, await _type(database), mark)
    root = CurrentUser(id=seller, role=str(int(Role.SUPER_ADMIN)))

    await store.create_enquiry(_enquiry(slug))
    await store.create_enquiry(_enquiry(slug, buyer_phone="9876543210", buyer_name="Same buyer"))
    assert len(await _enquiries(database, slug)) == 1

    first = (await _enquiries(database, slug))[0]
    await catalog.update_enquiry(UpdateEnquiryCommand(owner=root, id=first.id, status=EnquiryStatus.CLOSED))
    await store.create_enquiry(_enquiry(slug))
    assert len(await _enquiries(database, slug)) == 2


async def test_different_buyers_are_separate_leads(database, store, seller, mark):
    slug = await _animal(database, seller, await _type(database), mark)
    await store.create_enquiry(_enquiry(slug))
    await store.create_enquiry(_enquiry(slug, buyer_phone="9123456789"))
    assert len(await _enquiries(database, slug)) == 2


@pytest.mark.parametrize(
    ("bad", "field"), [({"buyer_name": " "}, "buyer_name"), ({"buyer_phone": "12345"}, "buyer_phone")]
)
async def test_invalid_enquiry_is_refused(database, store, seller, mark, bad, field):
    slug = await _animal(database, seller, await _type(database), mark)
    with pytest.raises(ListingValidationException) as error:
        await store.create_enquiry(_enquiry(slug, **bad))
    assert field in error.value.errors
    assert await _enquiries(database, slug) == []


async def test_sold_animal_refuses_and_reserved_accepts(database, store, seller, mark):
    cow = await _type(database)
    sold = await _animal(database, seller, cow, mark, status=AnimalStatus.SOLD)
    reserved = await _animal(database, seller, cow, mark, status=AnimalStatus.RESERVED)

    with pytest.raises(AnimalNotAvailableException):
        await store.create_enquiry(_enquiry(sold))
    await store.create_enquiry(_enquiry(reserved))
    assert len(await _enquiries(database, reserved)) == 1


@pytest.mark.parametrize("status", [AnimalStatus.DRAFT, AnimalStatus.ARCHIVED])
async def test_enquiry_for_a_hidden_animal_reads_as_not_found(database, store, seller, mark, status):
    slug = await _animal(database, seller, await _type(database), mark, status=status)
    with pytest.raises(AnimalNotFoundException):
        await store.create_enquiry(_enquiry(slug))
    with pytest.raises(AnimalNotFoundException):
        await store.create_enquiry(_enquiry("no-such-animal"))


# =========================================================
# SELLER INBOX
# =========================================================


async def test_inbox_filter_search_and_update(database, store, catalog, seller, mark):
    root = CurrentUser(id=seller, role=str(int(Role.SUPER_ADMIN)))
    slug = await _animal(database, seller, await _type(database), f"Gir {mark}")
    await store.create_enquiry(_enquiry(slug))

    items, total = await catalog.list_enquiries(root, mark, EnquiryStatus.NEW, 0, 10)
    assert total == 1

    await catalog.update_enquiry(UpdateEnquiryCommand(owner=root, id=items[0].id, status=EnquiryStatus.CONTACTED, admin_notes=" Called "))

    assert (await catalog.list_enquiries(root, mark, EnquiryStatus.NEW, 0, 10))[1] == 0
    updated = (await catalog.list_enquiries(root, mark, EnquiryStatus.CONTACTED, 0, 10))[0][0]
    assert updated.admin_notes == "Called"


async def test_seller_only_reaches_their_own_enquiries(database, store, catalog, seller, mark, monkeypatch):
    monkeypatch.setattr(SellerPolicy, "SELLER_ROLES", frozenset({Role.SUPER_ADMIN, Role.ADMIN}))
    other_id = await create_user(database, role=Role.ADMIN)
    other = CurrentUser(id=other_id, role=str(int(Role.ADMIN)))
    root = CurrentUser(id=seller, role=str(int(Role.SUPER_ADMIN)))
    slug = await _animal(database, seller, await _type(database), f"Gir {mark}")
    await store.create_enquiry(_enquiry(slug))
    enquiry_id = (await _enquiries(database, slug))[0].id

    assert (await catalog.list_enquiries(other, mark, None, 0, 10))[1] == 0
    with pytest.raises(EnquiryNotFoundException):
        await catalog.update_enquiry(UpdateEnquiryCommand(owner=other, id=enquiry_id, status=EnquiryStatus.CLOSED))
    assert (await catalog.list_enquiries(root, mark, None, 0, 10))[1] == 1


@pytest.mark.parametrize("role", [Role.ADMIN, Role.VLCC, Role.FARMER])
async def test_non_sellers_have_no_inbox(database, catalog, role):
    other = CurrentUser(id=await create_user(database, role=role), role=str(int(role)))
    with pytest.raises(SellingNotAllowedException):
        await catalog.list_enquiries(other, None, None, 0, 10)
    with pytest.raises(SellingNotAllowedException):
        await catalog.update_enquiry(UpdateEnquiryCommand(owner=other, id=uuid4(), status=EnquiryStatus.CLOSED))


async def test_counting_overview_sees_new_enquiries(database, store, catalog, seller, mark):
    root = CurrentUser(id=seller, role=str(int(Role.SUPER_ADMIN)))
    before, _ = await catalog.overview(root)
    await store.create_enquiry(_enquiry(await _animal(database, seller, await _type(database), mark)))
    after, _ = await catalog.overview(root)
    assert after.new_enquiries - before.new_enquiries == 1
