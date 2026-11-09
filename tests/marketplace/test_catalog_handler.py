"""Catalog use cases and listing images on a real database and real files."""

from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import update
from starlette.datastructures import Headers

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.command import (
    SaveAnimalBreedCommand,
    SaveAnimalCommand,
    SaveAnimalTypeCommand,
    SaveCategoryCommand,
    SaveProductCommand,
    VariantInput,
)
from app.modules.marketplace.application.handler import MAX_LISTING_IMAGES, MarketplaceCatalogHandler
from app.modules.marketplace.domain.enums import AnimalGender, AnimalStatus, ProductStatus
from app.modules.marketplace.domain.exceptions import (
    ListingValidationException,
    MasterInUseException,
    ProductNotFoundException,
    SellingNotAllowedException,
)
from app.modules.marketplace.domain.policy import SellerPolicy
from app.modules.marketplace.infrastructure.models import MarketplaceProductVariantModel
from app.modules.marketplace.infrastructure.repository import MarketplaceRepository
from app.modules.media.application.services import MediaService
from app.modules.media.domain.local_storage import LocalStorage
from app.modules.media.infrastructure.media_repository import MediaRepository
from app.modules.media.infrastructure.models import MediaModel
from tests.dataexchange.factories import create_user


class _InRequest:
    """Runs each call inside a transaction, as the web request middleware does."""

    def __init__(self, database, target) -> None:
        self._database = database
        self._target = target

    def __getattr__(self, name):
        method = getattr(self._target, name)

        async def call(*args, **kwargs):
            async with self._database.transaction():
                return await method(*args, **kwargs)

        return call


def _viewer(user_id: UUID, role: Role) -> CurrentUser:
    return CurrentUser(id=user_id, role=str(int(role)))


def _jpeg(size: tuple[int, int] = (64, 48), exif: bool = False) -> bytes:
    image = Image.new("RGB", size, (200, 120, 40))
    buffer = BytesIO()
    if exif:
        tags = Image.Exif()
        tags[0x010F] = "SecretCameraMaker"
        image.save(buffer, format="JPEG", exif=tags)
    else:
        image.save(buffer, format="JPEG")
    return buffer.getvalue()


def _upload(data: bytes | None = None, content_type: str = "image/jpeg", name: str = "a.jpg") -> UploadFile:
    return UploadFile(
        BytesIO(_jpeg() if data is None else data), filename=name, headers=Headers({"content-type": content_type})
    )


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(str(tmp_path))


@pytest.fixture
def media(database, storage) -> MediaService:
    return MediaService(repository=MediaRepository(database), storage=storage)


@pytest.fixture
def handler(database, media) -> MarketplaceCatalogHandler:
    target = MarketplaceCatalogHandler(database=database, repository=MarketplaceRepository(database), media_service=media)
    return _InRequest(database, target)


@pytest.fixture
async def root(database) -> CurrentUser:
    return _viewer(await create_user(database, role=Role.SUPER_ADMIN), Role.SUPER_ADMIN)


@pytest.fixture
async def category(handler, root):
    return await handler.save_category(SaveCategoryCommand(owner=root, name=f"Ghee {uuid4().hex}"))


@pytest.fixture
async def cow(handler, root):
    return await handler.save_animal_type(SaveAnimalTypeCommand(owner=root, name=f"Cow {uuid4().hex}"))


def _variant(**overrides) -> VariantInput:
    return VariantInput(**({"name": "1 L", "mrp": Decimal("600"), "price": Decimal("550"), "stock": 5} | overrides))


def _product_command(owner, category_id: UUID, **overrides) -> SaveProductCommand:
    values = {"owner": owner, "category_id": category_id, "title": "Desi Ghee", "variants": [_variant()]}
    return SaveProductCommand(**(values | overrides))


def _animal_command(owner, type_id: UUID, **overrides) -> SaveAnimalCommand:
    values = {
        "owner": owner, "animal_type_id": type_id, "title": "Gir cow", "price": Decimal("85000"),
        "lactation_number": 2, "milk_litres_per_day": Decimal("14.5"),
    }
    return SaveAnimalCommand(**(values | overrides))


# =========================================================
# IMAGES
# =========================================================


async def test_image_is_reencoded_resized_and_loses_exif(media):
    processed = await media.prepare_listing_image(_upload(_jpeg((3000, 2000), exif=True)))

    stored = Image.open(BytesIO(processed.data))
    assert stored.format == "WEBP"
    assert max(stored.size) == 1600
    assert len(processed.data) <= 300 * 1024
    assert b"SecretCameraMaker" not in processed.data


@pytest.mark.parametrize(
    ("upload", "message"),
    [
        (lambda: _upload(b"this is not an image"), "Invalid image file"),
        (lambda: _upload(b"", name="empty.jpg"), "empty"),
        (lambda: _upload(b"x" * (5 * 1024 * 1024 + 1)), "too large"),
        (lambda: _upload(content_type="application/pdf"), "JPG, PNG or WebP"),
    ],
    ids=["text renamed to jpg", "empty", "over 5 MB", "wrong type"],
)
async def test_bad_images_are_refused(media, upload, message):
    with pytest.raises(ValueError, match=message):
        await media.prepare_listing_image(upload())


async def test_bad_image_stops_the_save_and_stores_nothing(handler, root, category, storage):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_product(_product_command(root, category.id, new_images=[_upload(b"junk", name="junk.jpg")]))

    assert "junk.jpg" in error.value.errors["images"]
    assert not list(storage.root.rglob("*.webp"))


# =========================================================
# ACCESS
# =========================================================


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER])
async def test_non_sellers_are_refused_on_every_write(database, handler, root, category, cow, role):
    other = _viewer(await create_user(database, role=role), role)
    product = await handler.save_product(_product_command(root, category.id))

    for call in (
        lambda: handler.save_product(_product_command(other, category.id)),
        lambda: handler.delete_product(other, product.id),
        lambda: handler.get_product(other, product.id),
        lambda: handler.save_animal(_animal_command(other, cow.id)),
        lambda: handler.overview(other),
        lambda: handler.save_category(SaveCategoryCommand(owner=other, name="X")),
        lambda: handler.save_animal_type(SaveAnimalTypeCommand(owner=other, name="X")),
        lambda: handler.save_animal_breed(SaveAnimalBreedCommand(owner=other, animal_type_id=cow.id, name="X")),
        lambda: handler.delete_category(other, category.id),
    ):
        with pytest.raises(SellingNotAllowedException):
            await call()


async def test_guest_is_refused(handler, category):
    with pytest.raises(SellingNotAllowedException):
        await handler.save_product(_product_command(None, category.id))


async def test_enabling_admin_sellers_needs_only_the_policy(database, handler, root, category, monkeypatch):
    """The DECISION-016 seam: an Admin may sell after the policy change, and only sees their own listings."""
    monkeypatch.setattr(SellerPolicy, "SELLER_ROLES", frozenset({Role.SUPER_ADMIN, Role.ADMIN}))
    admin = _viewer(await create_user(database, role=Role.ADMIN), Role.ADMIN)

    own = await handler.save_product(_product_command(admin, category.id))
    foreign = await handler.save_product(_product_command(root, category.id))

    assert own.seller_user_id == admin.id
    assert (await handler.get_product(admin, own.id)).id == own.id
    with pytest.raises(ProductNotFoundException):
        await handler.get_product(admin, foreign.id)
    with pytest.raises(SellingNotAllowedException):  # masters stay with the Super Admin
        await handler.save_category(SaveCategoryCommand(owner=admin, name="X"))


# =========================================================
# PRODUCTS
# =========================================================


async def test_draft_can_be_saved_incomplete(handler, root, category):
    product = await handler.save_product(_product_command(root, category.id, variants=[]))
    assert product.status == ProductStatus.DRAFT
    assert (await handler.get_product(root, product.id)).variants == []


async def test_publishing_needs_a_size_and_an_image(handler, root, category):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_product(_product_command(root, category.id, status=ProductStatus.PUBLISHED, variants=[]))
    assert set(error.value.errors) == {"variants", "images"}

    inactive = [_variant(is_active=False)]
    with pytest.raises(ListingValidationException) as error:
        await handler.save_product(
            _product_command(root, category.id, status=ProductStatus.PUBLISHED, variants=inactive, new_images=[_upload()])
        )
    assert set(error.value.errors) == {"variants"}


async def test_complete_product_publishes_with_stored_image(handler, root, category, storage):
    product = await handler.save_product(
        _product_command(root, category.id, status=ProductStatus.PUBLISHED, new_images=[_upload()])
    )
    stored = await handler.get_product(root, product.id)

    assert stored.status == ProductStatus.PUBLISHED
    assert stored.images[0].url.startswith("/api/v1/media/product/")
    assert storage.exists(stored.images[0].url.removeprefix("/api/v1/media/"))


async def test_same_title_gets_different_slugs_and_slug_survives_rename(handler, root, category):
    title = f"Pure Ghee {uuid4().hex[:8]}"
    first = await handler.save_product(_product_command(root, category.id, title=title))
    second = await handler.save_product(_product_command(root, category.id, title=title))
    assert second.slug == f"{first.slug}-2"

    renamed = await handler.save_product(_product_command(root, category.id, id=first.id, title="New name"))
    assert renamed.slug == first.slug


@pytest.mark.parametrize(
    "bad",
    [
        {"price": Decimal("700"), "mrp": Decimal("600")},
        {"price": Decimal("-1"), "mrp": Decimal("10")},
        {"stock": -1},
        {"name": "  "},
    ],
    ids=["price above MRP", "negative price", "negative stock", "no name"],
)
async def test_bad_sizes_get_a_message_not_a_database_error(handler, root, category, bad):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_product(_product_command(root, category.id, variants=[_variant(**bad)]))
    assert "variants" in error.value.errors


async def test_duplicate_sku_is_refused_across_products_but_own_sku_is_fine(handler, root, category):
    sku = f"SKU-{uuid4().hex}"
    first = await handler.save_product(_product_command(root, category.id, variants=[_variant(sku=sku)]))

    with pytest.raises(ListingValidationException) as error:
        await handler.save_product(_product_command(root, category.id, variants=[_variant(sku=sku)]))
    assert sku in error.value.errors["variants"]

    same_id = first.variants[0].id
    updated = await handler.save_product(
        _product_command(root, category.id, id=first.id, variants=[_variant(id=same_id, sku=sku, stock=9)])
    )
    assert updated.variants[0].stock == 9


async def test_exactly_one_default_size(handler, root, category):
    none_chosen = await handler.save_product(
        _product_command(root, category.id, variants=[_variant(is_active=False, name="A"), _variant(name="B"), _variant(name="C")])
    )
    assert [v.name for v in none_chosen.variants if v.is_default] == ["B"]

    two_chosen = await handler.save_product(
        _product_command(root, category.id, variants=[_variant(name="A"), _variant(name="B", is_default=True), _variant(name="C", is_default=True)])
    )
    assert [v.name for v in two_chosen.variants if v.is_default] == ["B"]


async def test_variant_id_of_another_product_is_not_taken_over(handler, root, category):
    other = await handler.save_product(_product_command(root, category.id))
    other_variant_id = other.variants[0].id

    mine = await handler.save_product(_product_command(root, category.id))
    updated = await handler.save_product(
        _product_command(root, category.id, id=mine.id, variants=[_variant(id=other_variant_id, name="Stolen")])
    )

    assert updated.variants[0].id != other_variant_id
    assert (await handler.get_product(root, other.id)).variants[0].name == "1 L"


async def test_gallery_reorder_remove_and_add(database, handler, root, category, storage):
    product = await handler.save_product(
        _product_command(root, category.id, new_images=[_upload(name="one.jpg"), _upload(name="two.jpg"), _upload(name="three.jpg")])
    )
    one, two, three = product.images

    updated = await handler.save_product(
        _product_command(root, category.id, id=product.id, keep_image_ids=[three.id, one.id], new_images=[_upload(name="four.jpg")])
    )

    stored = await handler.get_product(root, updated.id)
    assert [image.id for image in stored.images[:2]] == [three.id, one.id]
    assert [image.sort_order for image in stored.images] == [0, 1, 2]
    assert stored.images[2].url and stored.images[2].id not in {one.id, two.id, three.id}

    # The removed image's row and file are both gone; the kept ones stay
    assert not storage.exists(two.url.removeprefix("/api/v1/media/"))
    assert storage.exists(one.url.removeprefix("/api/v1/media/"))
    async with database.transaction() as session:
        assert await session.get(MediaModel, two.media_id) is None


async def test_too_many_images_are_refused(handler, root, category):
    uploads = [_upload() for _ in range(MAX_LISTING_IMAGES + 1)]
    with pytest.raises(ListingValidationException) as error:
        await handler.save_product(_product_command(root, category.id, new_images=uploads))
    assert "images" in error.value.errors


async def test_delete_hides_the_product(handler, root, category):
    product = await handler.save_product(_product_command(root, category.id))
    await handler.delete_product(root, product.id)
    with pytest.raises(ProductNotFoundException):
        await handler.get_product(root, product.id)


# =========================================================
# ANIMALS
# =========================================================


async def test_publishing_female_needs_lactation_milk_and_image(handler, root, cow):
    command = _animal_command(root, cow.id, status=AnimalStatus.PUBLISHED, lactation_number=None, milk_litres_per_day=None)
    with pytest.raises(ListingValidationException) as error:
        await handler.save_animal(command)
    assert set(error.value.errors) == {"lactation_number", "milk_litres_per_day", "images"}


async def test_bull_publishes_without_milk_details(handler, root, cow):
    animal = await handler.save_animal(_animal_command(
        root, cow.id, status=AnimalStatus.PUBLISHED, gender=AnimalGender.MALE,
        lactation_number=None, milk_litres_per_day=None, new_images=[_upload()],
    ))
    assert animal.status == AnimalStatus.PUBLISHED


async def test_breed_must_belong_to_the_type(handler, root, cow):
    buffalo = await handler.save_animal_type(SaveAnimalTypeCommand(owner=root, name=f"Buffalo {uuid4().hex}"))
    murrah = await handler.save_animal_breed(SaveAnimalBreedCommand(owner=root, animal_type_id=buffalo.id, name="Murrah"))

    with pytest.raises(ListingValidationException) as error:
        await handler.save_animal(_animal_command(root, cow.id, breed_id=murrah.id))
    assert "breed_id" in error.value.errors

    animal = await handler.save_animal(_animal_command(root, buffalo.id, breed_id=murrah.id))
    assert animal.breed_id == murrah.id


async def test_animal_numbers_are_checked(handler, root, cow):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_animal(_animal_command(root, cow.id, fat_percent=Decimal("101"), age_months=-1))
    assert set(error.value.errors) == {"fat_percent", "age_months"}


# =========================================================
# MASTERS
# =========================================================


async def test_category_in_use_cannot_be_deleted_until_empty(handler, root, category):
    product = await handler.save_product(_product_command(root, category.id))

    with pytest.raises(MasterInUseException):
        await handler.delete_category(root, category.id)
    await handler.delete_product(root, product.id)
    with pytest.raises(MasterInUseException):  # the soft-deleted product still holds the link
        await handler.delete_category(root, category.id)


async def test_unused_category_is_deleted_with_its_image(handler, root, storage):
    category = await handler.save_category(SaveCategoryCommand(owner=root, name=f"Oils {uuid4().hex}", new_image=_upload()))
    key = category.image_url.removeprefix("/api/v1/media/")
    assert storage.exists(key)

    await handler.delete_category(root, category.id)

    assert category.id not in {c.id for c in await handler.list_categories(root)}
    assert not storage.exists(key)


async def test_category_cannot_sit_inside_itself(handler, root):
    parent = await handler.save_category(SaveCategoryCommand(owner=root, name=f"P {uuid4().hex}"))
    child = await handler.save_category(SaveCategoryCommand(owner=root, name=f"C {uuid4().hex}", parent_id=parent.id))

    for bad_parent in (parent.id, child.id):
        with pytest.raises(ListingValidationException) as error:
            await handler.save_category(
                SaveCategoryCommand(owner=root, id=parent.id, name=parent.name, parent_id=bad_parent)
            )
        assert "parent_id" in error.value.errors


async def test_duplicate_type_and_breed_names_are_refused_ignoring_case(handler, root, cow):
    with pytest.raises(ListingValidationException):
        await handler.save_animal_type(SaveAnimalTypeCommand(owner=root, name=cow.name.upper()))

    await handler.save_animal_breed(SaveAnimalBreedCommand(owner=root, animal_type_id=cow.id, name="Gir"))
    with pytest.raises(ListingValidationException):
        await handler.save_animal_breed(SaveAnimalBreedCommand(owner=root, animal_type_id=cow.id, name="GIR"))


async def test_type_with_breeds_and_breed_with_animals_cannot_be_deleted(handler, root, cow):
    breed = await handler.save_animal_breed(SaveAnimalBreedCommand(owner=root, animal_type_id=cow.id, name="Gir"))
    await handler.save_animal(_animal_command(root, cow.id, breed_id=breed.id))

    with pytest.raises(MasterInUseException):
        await handler.delete_animal_type(root, cow.id)
    with pytest.raises(MasterInUseException):
        await handler.delete_animal_breed(root, breed.id)


# =========================================================
# OVERVIEW
# =========================================================


async def test_overview_counts_only_what_it_says(database, handler, root, category, cow):
    # The low stock list is short and the test database is shared: restock what other tests left
    async with database.transaction() as session:
        await session.execute(update(MarketplaceProductVariantModel).values(stock=100))
    before, _ = await handler.overview(root)

    title = f"Low {uuid4().hex}"
    await handler.save_product(_product_command(root, category.id))  # draft: counted in total only
    published = await handler.save_product(_product_command(
        root, category.id, title=title, status=ProductStatus.PUBLISHED, new_images=[_upload()],
        variants=[_variant(stock=2, low_stock_threshold=5), _variant(name="5 L", stock=50, low_stock_threshold=5)],
    ))
    await handler.save_animal(_animal_command(root, cow.id, status=AnimalStatus.PUBLISHED, new_images=[_upload()]))

    after, low_stock = await handler.overview(root)
    assert after.products_total - before.products_total == 2
    assert after.products_published - before.products_published == 1
    assert after.animals_live - before.animals_live == 1
    assert after.low_stock_variants - before.low_stock_variants == 1
    assert (published.id, "1 L", 2) in {(i.product_id, i.variant_name, i.stock) for i in low_stock}
