"""Banners, home sections, trending links and settings on a real database and real files."""

from datetime import datetime, timedelta
from decimal import Decimal
from io import BytesIO
from uuid import UUID, uuid4

import pytest
from fastapi import UploadFile
from PIL import Image
from sqlalchemy import delete
from starlette.datastructures import Headers

from app.core.clock import now_naive_ist
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.application.command import (
    SaveBannerCommand,
    SaveHomeSectionCommand,
    SaveSettingsCommand,
    SaveTrendingTagCommand,
)
from app.modules.marketplace.application.merchandising_handler import MarketplaceMerchandisingHandler
from app.modules.marketplace.domain.enums import BannerPlacement, BannerState, HomeSectionType
from app.modules.marketplace.domain.exceptions import (
    HomeSectionNotFoundException,
    ListingValidationException,
    SellingNotAllowedException,
)
from app.modules.marketplace.domain.links import is_safe_link
from app.modules.marketplace.domain.merchandising import Banner, StoreSettings
from app.modules.marketplace.infrastructure.merchandising_repository import MerchandisingRepository
from app.modules.marketplace.infrastructure.models import (
    MarketplaceCategoryModel,
    MarketplaceHomeSectionModel,
)
from app.modules.media.application.services import MediaService
from app.modules.media.domain.local_storage import LocalStorage
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


def _viewer(user_id: UUID, role: Role) -> CurrentUser:
    return CurrentUser(id=user_id, role=str(int(role)))


def _upload(name: str = "a.jpg", data: bytes | None = None) -> UploadFile:
    if data is None:
        buffer = BytesIO()
        Image.new("RGB", (64, 48), (10, 120, 40)).save(buffer, format="JPEG")
        data = buffer.getvalue()
    return UploadFile(BytesIO(data), filename=name, headers=Headers({"content-type": "image/jpeg"}))


@pytest.fixture
def storage(tmp_path) -> LocalStorage:
    return LocalStorage(str(tmp_path))


@pytest.fixture
def handler(database, storage) -> MarketplaceMerchandisingHandler:
    media = MediaService(repository=MediaRepository(database), storage=storage)
    return _InRequest(database, MarketplaceMerchandisingHandler(database, MerchandisingRepository(database), media))


@pytest.fixture
def repository(database) -> _InRequest:
    return _InRequest(database, MerchandisingRepository(database))


@pytest.fixture
async def root(database) -> CurrentUser:
    return _viewer(await create_user(database, role=Role.SUPER_ADMIN), Role.SUPER_ADMIN)


@pytest.fixture
async def empty_sections(database) -> None:
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceHomeSectionModel))
        for order, kind in enumerate((HomeSectionType.CATEGORIES, HomeSectionType.TRENDING, HomeSectionType.FEATURED_ANIMALS)):
            session.add(MarketplaceHomeSectionModel(section_type=kind, title=kind.value, sort_order=order))


async def _category(database) -> UUID:
    row_id = uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=row_id, name="Ghee", slug=f"ghee-{row_id.hex}"))
    return row_id


# =========================================================
# LINKS
# =========================================================


@pytest.mark.parametrize(
    "url", ["/marketplace/products", "/marketplace/products?category=ghee", "https://example.com/a", "http://example.com"]
)
def test_safe_links(url):
    assert is_safe_link(url)


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)", "JaVaScRiPt:alert(1)", "data:text/html,x", "//evil.example", "/\\evil.example",
        "\tjavascript:alert(1)", "java\nscript:alert(1)", "ftp://example.com", "marketplace", "https://", "",
        "/path with space",
    ],
)
def test_unsafe_links(url):
    assert not is_safe_link(url)


# =========================================================
# ACCESS
# =========================================================


@pytest.mark.parametrize("role", [Role.ADMIN, Role.SUB_ADMIN, Role.VLCC, Role.FARMER])
async def test_only_super_admin_changes_the_store(database, handler, role):
    other = _viewer(await create_user(database, role=role), role)
    for call in (
        lambda: handler.list_banners(other),
        lambda: handler.save_banner(SaveBannerCommand(owner=other, title="X", new_image=_upload())),
        lambda: handler.delete_banner(other, uuid4()),
        lambda: handler.save_home_section(SaveHomeSectionCommand(owner=other, title="X")),
        lambda: handler.move_home_section(other, uuid4(), 1),
        lambda: handler.save_trending_tag(SaveTrendingTagCommand(owner=other, label="X", url="/x")),
        lambda: handler.get_settings(other),
        lambda: handler.save_settings(SaveSettingsCommand(owner=other, store_name="X")),
    ):
        with pytest.raises(SellingNotAllowedException):
            await call()


# =========================================================
# BANNERS
# =========================================================


def _banner(**overrides) -> Banner:
    return Banner(**({"id": uuid4(), "title": "T", "image_url": "/x.webp"} | overrides))


@pytest.mark.parametrize(
    ("banner", "expected"),
    [
        ({}, BannerState.LIVE),
        ({"is_active": False}, BannerState.OFF),
        ({"starts_at": datetime(2026, 2, 1)}, BannerState.SCHEDULED),
        ({"ends_at": datetime(2026, 1, 1)}, BannerState.EXPIRED),
        ({"ends_at": datetime(2026, 1, 15)}, BannerState.EXPIRED),  # the end moment itself is over
        ({"starts_at": datetime(2026, 1, 15), "ends_at": datetime(2026, 1, 16)}, BannerState.LIVE),
    ],
)
def test_banner_state(banner, expected):
    assert _banner(**banner).state(datetime(2026, 1, 15)) == expected


async def test_banner_needs_an_image_title_and_safe_link(handler, root):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_banner(SaveBannerCommand(owner=root, title=" ", cta_url="javascript:alert(1)"))
    assert set(error.value.errors) == {"title", "cta_url", "image"}


async def test_banner_window_must_run_forwards(handler, root):
    now = now_naive_ist()
    with pytest.raises(ListingValidationException) as error:
        await handler.save_banner(
            SaveBannerCommand(owner=root, title="T", new_image=_upload(), starts_at=now, ends_at=now)
        )
    assert "ends_at" in error.value.errors


async def test_only_live_banners_of_the_placement_are_served(handler, repository, root):
    now = now_naive_ist()
    mark = uuid4().hex
    live = await handler.save_banner(SaveBannerCommand(owner=root, title=f"live {mark}", new_image=_upload()))
    await handler.save_banner(SaveBannerCommand(owner=root, title=f"off {mark}", new_image=_upload(), is_active=False))
    await handler.save_banner(SaveBannerCommand(owner=root, title=f"later {mark}", new_image=_upload(), starts_at=now + timedelta(days=1)))
    await handler.save_banner(SaveBannerCommand(owner=root, title=f"over {mark}", new_image=_upload(), ends_at=now - timedelta(days=1)))
    await handler.save_banner(SaveBannerCommand(owner=root, title=f"middle {mark}", new_image=_upload(), placement=BannerPlacement.HOME_MIDDLE))

    served = await repository.live_banners(BannerPlacement.HOME_HERO, now)

    assert [banner.id for banner in served if mark in banner.title] == [live.id]


async def test_replacing_and_deleting_a_banner_removes_old_files(handler, root, storage):
    banner = await handler.save_banner(SaveBannerCommand(owner=root, title="T", new_image=_upload(), new_mobile_image=_upload()))
    first_key = banner.image_url.removeprefix("/api/v1/media/")
    mobile_key = banner.mobile_image_url.removeprefix("/api/v1/media/")
    assert storage.exists(first_key) and storage.exists(mobile_key)

    updated = await handler.save_banner(SaveBannerCommand(owner=root, id=banner.id, title="T2", new_image=_upload(), remove_mobile_image=True))
    assert not storage.exists(first_key)
    assert not storage.exists(mobile_key)
    assert updated.mobile_image_url is None

    new_key = updated.image_url.removeprefix("/api/v1/media/")
    assert storage.exists(new_key)
    await handler.delete_banner(root, banner.id)
    assert not storage.exists(new_key)


async def test_editing_a_banner_without_a_new_image_keeps_it(handler, root):
    banner = await handler.save_banner(SaveBannerCommand(owner=root, title="T", new_image=_upload()))
    updated = await handler.save_banner(SaveBannerCommand(owner=root, id=banner.id, title="New"))
    assert updated.image_url == banner.image_url and updated.title == "New"


async def test_broken_image_is_a_field_error_and_stores_nothing(handler, root, storage):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_banner(SaveBannerCommand(owner=root, title="T", new_image=_upload(data=b"junk")))
    assert "image" in error.value.errors
    assert not list(storage.root.rglob("*.webp"))


# =========================================================
# HOME SECTIONS
# =========================================================


async def test_moving_a_section_swaps_neighbours_and_stops_at_the_ends(handler, root, empty_sections):
    sections = await handler.list_home_sections(root)
    first, second, third = [section.id for section in sections]

    await handler.move_home_section(root, second, -1)
    assert [s.id for s in await handler.list_home_sections(root)] == [second, first, third]

    await handler.move_home_section(root, second, -1)  # already first: nothing changes
    await handler.move_home_section(root, third, 1)  # already last: nothing changes
    after = await handler.list_home_sections(root)
    assert [s.id for s in after] == [second, first, third]
    assert [s.sort_order for s in after] == [0, 1, 2]


async def test_category_section_needs_a_category_and_can_be_deleted(database, handler, root, empty_sections):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_home_section(SaveHomeSectionCommand(owner=root, title="Ghee picks"))
    assert "category_id" in error.value.errors

    section = await handler.save_home_section(
        SaveHomeSectionCommand(owner=root, title="Ghee picks", category_id=await _category(database))
    )
    assert section.section_type == HomeSectionType.CATEGORY_PRODUCTS
    assert section.sort_order == 3

    await handler.delete_home_section(root, section.id)
    assert section.id not in {s.id for s in await handler.list_home_sections(root)}


async def test_built_in_section_can_be_hidden_but_not_deleted(handler, root, empty_sections):
    built_in = (await handler.list_home_sections(root))[0]

    with pytest.raises(ListingValidationException):
        await handler.delete_home_section(root, built_in.id)

    hidden = await handler.save_home_section(SaveHomeSectionCommand(owner=root, id=built_in.id, title="Browse", is_visible=False))
    assert hidden.section_type == built_in.section_type  # the kind cannot be changed
    assert hidden.is_visible is False


async def test_section_limit_and_unknown_section(handler, root, empty_sections):
    built_in = (await handler.list_home_sections(root))[0]
    with pytest.raises(ListingValidationException) as error:
        await handler.save_home_section(SaveHomeSectionCommand(owner=root, id=built_in.id, title="X", item_limit=25))
    assert "item_limit" in error.value.errors
    with pytest.raises(HomeSectionNotFoundException):
        await handler.move_home_section(root, uuid4(), 1)


# =========================================================
# TRENDING
# =========================================================


async def test_trending_tag_round_trip_and_unsafe_link(handler, root):
    with pytest.raises(ListingValidationException) as error:
        await handler.save_trending_tag(SaveTrendingTagCommand(owner=root, label="X", url="javascript:alert(1)"))
    assert "url" in error.value.errors

    label = f"Ghee {uuid4().hex}"
    tag = await handler.save_trending_tag(SaveTrendingTagCommand(owner=root, label=label, url="/marketplace/products"))
    assert label in {item.label for item in await handler.list_trending_tags(root)}

    await handler.delete_trending_tag(root, tag.id)
    assert label not in {item.label for item in await handler.list_trending_tags(root)}


# =========================================================
# SETTINGS
# =========================================================


async def test_settings_round_trip(handler, root):
    await handler.save_settings(SaveSettingsCommand(
        owner=root, store_name="  My Dairy ", support_phone="9876543210", whatsapp_number="919876543210",
        support_email="a@b.in", delivery_charge=Decimal("40"), free_delivery_above=Decimal("500"),
        min_order_amount=Decimal("100"), cod_enabled=True, is_store_open=True,
        serviceable_pincodes=["302001", "302001", "302002"], policies={"returns": " 7 days ", "shipping": "  ", "hack": "x"},
        new_logo=_upload(),
    ))

    saved = await handler.get_settings(root)
    assert saved.store_name == "My Dairy"
    assert saved.delivery_charge == Decimal("40.00")
    assert saved.serviceable_pincodes == ["302001", "302002"]
    assert saved.policies == {"returns": "7 days"}
    assert saved.logo_url.startswith("/api/v1/media/banner/")


async def test_saving_settings_without_a_new_logo_keeps_it_and_remove_clears_it(handler, root, storage):
    first = await handler.save_settings(SaveSettingsCommand(owner=root, store_name="A", new_logo=_upload()))
    second = await handler.save_settings(SaveSettingsCommand(owner=root, store_name="B"))
    assert second.logo_url == first.logo_url

    third = await handler.save_settings(SaveSettingsCommand(owner=root, store_name="C", remove_logo=True))
    assert third.logo_url is None
    assert not storage.exists(first.logo_url.removeprefix("/api/v1/media/"))


@pytest.mark.parametrize(
    ("bad", "field"),
    [
        ({"store_name": " "}, "store_name"),
        ({"support_phone": "12345"}, "support_phone"),
        ({"whatsapp_number": "abc"}, "whatsapp_number"),
        ({"support_email": "nope"}, "support_email"),
        ({"delivery_charge": Decimal("-1")}, "delivery_charge"),
        ({"serviceable_pincodes": ["302001", "12"]}, "serviceable_pincodes"),
    ],
)
async def test_bad_settings_are_refused(handler, root, bad, field):
    command = {"owner": root, "store_name": "Store"} | bad
    with pytest.raises(ListingValidationException) as error:
        await handler.save_settings(SaveSettingsCommand(**command))
    assert field in error.value.errors


def test_pincode_rule():
    assert StoreSettings(store_name="S").serves("110001")  # empty list serves everyone
    limited = StoreSettings(store_name="S", serviceable_pincodes=["302001"])
    assert limited.serves("302001")
    assert not limited.serves("110001")
