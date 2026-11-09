"""The public store through the real app."""

import re
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import AnimalStatus, HomeSectionType, ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceBannerModel,
    MarketplaceCategoryModel,
    MarketplaceHomeSectionModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
)
from app.web.framework.formatting import age_label, quantity
from tests.dataexchange.factories import create_user

HTML = {"accept": "text/html"}
# url_for gives absolute URLs on the app's own host, which is "test" here
EXTERNAL = re.compile(r"""(?:src|href)=["'](https?:)?//(?!wa\.me|test/)""")


@pytest.fixture
async def stocked(database) -> dict[str, str]:
    """One live product, animal and banner, with sections showing them."""
    seller = await create_user(database, role=Role.SUPER_ADMIN)
    mark = uuid4().hex[:8]
    category_id, type_id, product_id = uuid4(), uuid4(), uuid4()
    names = {"product": f"Ghee {mark}", "animal": f"Gir {mark}", "banner": f"Offer {mark}", "category": f"Dairy {mark}"}
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceHomeSectionModel))
        await session.execute(delete(MarketplaceBannerModel))
        session.add(MarketplaceCategoryModel(id=category_id, name=names["category"], slug=f"d-{mark}", sort_order=-1))
        session.add(MarketplaceAnimalTypeModel(id=type_id, name=f"Cow {mark}", slug=f"cow-{mark}"))
        session.add(MarketplaceBannerModel(title=names["banner"], image_url="/hero.webp", cta_label="Shop now", cta_url="/marketplace/products"))
        await session.flush()
        session.add(MarketplaceProductModel(id=product_id, seller_user_id=seller, category_id=category_id, title=names["product"],
                                            slug=f"ghee-{mark}", status=ProductStatus.PUBLISHED, is_featured=True))
        session.add(MarketplaceAnimalModel(seller_user_id=seller, animal_type_id=type_id, title=names["animal"], slug=f"gir-{mark}",
                                           price=Decimal("125000"), status=AnimalStatus.PUBLISHED, is_featured=True,
                                           lactation_number=2, milk_litres_per_day=Decimal("14.50"), age_months=48))
        await session.flush()
        session.add(MarketplaceProductVariantModel(product_id=product_id, name="1 L", mrp=Decimal("800"), price=Decimal("600"), stock=4, is_default=True))
        for order, kind in enumerate((HomeSectionType.CATEGORIES, HomeSectionType.FEATURED_ANIMALS, HomeSectionType.FEATURED_PRODUCTS)):
            session.add(MarketplaceHomeSectionModel(section_type=kind, title=f"Section {kind.value}", sort_order=order))
    return names


async def test_guest_can_open_the_store_and_is_sent_there_from_root(api, stocked):
    root = await api.get("/", headers=HTML, follow_redirects=False)
    assert (root.status_code, root.headers["location"]) == (302, "/marketplace")

    for url in ("/marketplace", "/marketplace/"):
        assert (await api.get(url, headers=HTML)).status_code == 200


async def test_home_shows_live_content_in_the_store_layout(api, stocked):
    page = (await api.get("/marketplace", headers=HTML)).text

    for name in stocked.values():
        assert name in page
    assert "₹1,25,000" in page and "14.5 L" in page and "4 yrs" in page
    assert "₹600" in page and "25% off" in page
    assert "css/store.css" in page
    assert "sidebar" not in page and "app.min.css" not in page  # no dashboard shell
    assert page.count("<h1") == 1


async def test_sections_render_in_their_set_order(api, stocked):
    page = (await api.get("/marketplace", headers=HTML)).text
    positions = [page.index(f"Section {kind.value}") for kind in (HomeSectionType.CATEGORIES, HomeSectionType.FEATURED_ANIMALS, HomeSectionType.FEATURED_PRODUCTS)]
    assert positions == sorted(positions)


async def test_page_uses_no_outside_assets(api, stocked):
    page = (await api.get("/marketplace", headers=HTML)).text
    assert not EXTERNAL.search(page)


async def test_store_is_usable_with_nothing_to_show(api, database):
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceHomeSectionModel))
        await session.execute(delete(MarketplaceBannerModel))
        await session.execute(delete(MarketplaceSettingsModel))

    response = await api.get("/marketplace", headers=HTML)

    assert response.status_code == 200
    assert "The store is getting ready" in response.text
    assert "Vitco Marketplace" in response.text  # falls back to a store name


async def test_closed_store_shows_its_message(api, database):
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(store_name="Shop", is_store_open=False, closed_message="Back on Monday"))

    page = (await api.get("/marketplace", headers=HTML)).text

    assert "Back on Monday" in page


async def test_store_content_is_escaped(api, database):
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(store_name="<script>alert(1)</script>"))

    page = (await api.get("/marketplace", headers=HTML)).text

    assert "<script>alert(1)" not in page
    assert "&lt;script&gt;" in page


async def test_login_and_dashboard_links_follow_the_visitor(api, database, token_for):
    guest = (await api.get("/marketplace", headers=HTML)).text
    assert 'href="/login"' in guest and 'href="/dashboard"' not in guest

    headers = token_for(await create_user(database, role=Role.VLCC), Role.VLCC) | HTML
    member = (await api.get("/marketplace", headers=headers)).text
    assert 'href="/dashboard"' in member


async def test_making_the_store_public_opened_nothing_else(api):
    for url in ("/admin/marketplace", "/admin/marketplace/products", "/dashboard"):
        response = await api.get(url, headers=HTML, follow_redirects=False)
        assert response.headers.get("location") == "/login", url
    assert (await api.get("/api/v1/farmers/")).status_code == 401


def test_store_files_reference_no_cdn():
    for name in ("app/web/static/css/store.css", "app/web/static/js/store.js", "app/web/templates/layouts/store.html"):
        source = Path(name).read_text(encoding="utf-8")
        assert "http://" not in source
        assert "https://" not in source.replace("https://wa.me/", "")


@pytest.mark.parametrize(
    ("value", "expected"), [(Decimal("14.50"), "14.5"), (Decimal("14.00"), "14"), (Decimal("100"), "100"), (None, "—")]
)
def test_quantity(value, expected):
    assert quantity(value) == expected


@pytest.mark.parametrize(
    ("months", "expected"), [(None, "—"), (1, "1 month"), (8, "8 months"), (12, "1 yr"), (42, "3.5 yrs"), (48, "4 yrs")]
)
def test_age_label(months, expected):
    assert age_label(months) == expected
