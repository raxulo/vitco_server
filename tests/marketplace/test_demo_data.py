"""The demo seeder adds a usable store, runs safely twice, and removes only what it added."""

from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete, func, select

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalModel,
    MarketplaceBannerModel,
    MarketplaceCategoryModel,
    MarketplaceProductModel,
    MarketplaceSettingsModel,
    MarketplaceTrendingTagModel,
)
from app.modules.media.application.services import MediaService
from scripts import seed_marketplace_demo as demo
from tests.dataexchange.factories import create_user

HTML = {"accept": "text/html"}


@pytest.fixture
async def media(api):
    from app.main import app

    return app.state.application.container.resolve(MediaService)


@pytest.fixture
async def fresh_store(database, media):
    """Starter masters and blank settings, with no demo data left by another test."""
    await create_user(database, role=Role.SUPER_ADMIN)
    await demo.remove_demo(database, media)
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(store_name="My Own Store"))
    yield
    await demo.remove_demo(database, media)


async def _count(database, model, *where) -> int:
    async with database.transaction() as session:
        return await session.scalar(select(func.count()).select_from(model).where(*where))


async def test_store_shows_the_demo_listings(api, database, media, fresh_store):
    added = await demo.add_demo(database, media)
    assert added["products"] == len(demo.PRODUCTS) and added["animals"] == len(demo.ANIMALS)

    home = (await api.get("/marketplace", headers=HTML)).text
    assert "Pure Desi Cow Ghee" in home and "Gir cow, second lactation" in home
    assert "Milk you can trust" in home and "Murrah buffalo" in home

    detail = await api.get("/marketplace/products/demo-desi-cow-ghee", headers=HTML)
    assert detail.status_code == 200 and "₹389" in detail.text

    image_url = detail.text.split('data-gallery-track')[1].split('src="')[1].split('"')[0]
    picture = await api.get(image_url)
    assert picture.status_code == 200 and picture.headers["content-type"].startswith("image/")


async def test_running_twice_adds_nothing_new(database, media, fresh_store):
    await demo.add_demo(database, media)
    assert set((await demo.add_demo(database, media)).values()) == {0}


async def test_settings_already_set_are_kept(database, media, fresh_store):
    async with database.transaction() as session:
        row = await session.scalar(select(MarketplaceSettingsModel))
        row.support_phone = "9123456789"
        row.delivery_charge = Decimal("25")
        row.policies = {"terms": "My own terms"}

    await demo.add_demo(database, media)

    async with database.transaction() as session:
        row = await session.scalar(select(MarketplaceSettingsModel))
        assert (row.store_name, row.support_phone, row.delivery_charge) == ("My Own Store", "9123456789", Decimal("25.00"))
        assert row.policies["terms"] == "My own terms" and row.policies["returns"] == demo.POLICIES["returns"]
        assert row.free_delivery_above == Decimal("499.00")


async def test_remove_takes_out_only_demo_data(database, media, fresh_store):
    seller = await create_user(database, role=Role.SUPER_ADMIN)
    real_slug = f"real-{uuid4().hex}"
    async with database.transaction() as session:
        category = await session.scalar(select(MarketplaceCategoryModel.id).limit(1))
        session.add(MarketplaceProductModel(seller_user_id=seller, category_id=category, title="Real", slug=real_slug, status=ProductStatus.PUBLISHED))
        session.add(MarketplaceBannerModel(title="My real banner", image_url="/real.webp"))
        session.add(MarketplaceTrendingTagModel(label="My real link", url="/marketplace/products"))
        row = await session.scalar(select(MarketplaceSettingsModel))
        row.support_phone = "9123456789"

    await demo.add_demo(database, media)
    await demo.remove_demo(database, media)

    assert await _count(database, MarketplaceProductModel, MarketplaceProductModel.slug.like("demo-%")) == 0
    assert await _count(database, MarketplaceAnimalModel, MarketplaceAnimalModel.slug.like("demo-%")) == 0
    assert await _count(database, MarketplaceProductModel, MarketplaceProductModel.slug == real_slug) == 1
    assert await _count(database, MarketplaceBannerModel, MarketplaceBannerModel.title == "My real banner") == 1
    assert await _count(database, MarketplaceBannerModel, MarketplaceBannerModel.title == demo.BANNERS[0][0]) == 0
    assert await _count(database, MarketplaceTrendingTagModel, MarketplaceTrendingTagModel.label == "My real link") == 1
    async with database.transaction() as session:
        row = await session.scalar(select(MarketplaceSettingsModel))
        assert row.support_phone == "9123456789"  # the store's own value stays
        assert row.whatsapp_number is None and row.delivery_charge == Decimal("0.00") and not row.policies

    async with database.transaction() as session:
        await session.execute(delete(MarketplaceProductModel).where(MarketplaceProductModel.slug == real_slug))
        await session.execute(delete(MarketplaceBannerModel).where(MarketplaceBannerModel.title == "My real banner"))
        await session.execute(delete(MarketplaceTrendingTagModel).where(MarketplaceTrendingTagModel.label == "My real link"))


def test_refuses_to_run_in_production(monkeypatch):
    monkeypatch.setattr(demo.settings, "ENVIRONMENT", "production")
    monkeypatch.setattr("sys.argv", ["seed_marketplace_demo.py"])
    with pytest.raises(SystemExit, match="production"):
        demo.main()
