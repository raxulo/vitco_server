"""Phase 16: what the refreshed pages tell people must be true."""

import re
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import delete

from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import AnimalStatus, ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceEnquiryModel,
    MarketplaceHomeSectionModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
)
from tests.dataexchange.factories import create_user

BASE = "/admin/marketplace"
API = "/api/v1/marketplace"
HTML = {"accept": "text/html"}


@pytest.fixture
async def seller(database):
    return await create_user(database, role=Role.SUPER_ADMIN)


@pytest.fixture
def admin(token_for, seller) -> dict[str, str]:
    return token_for(seller, Role.SUPER_ADMIN) | HTML


def _tab_count(page: str, label: str) -> str | None:
    found = re.search(rf"</i>{label}\s*(?:<span class=\"mk-count\">([^<]+))?", page)
    assert found, f"{label} tab is missing"
    return found.group(1)


async def _settings(database, **fields) -> None:
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceSettingsModel))
        session.add(MarketplaceSettingsModel(**({"store_name": "Shop", "created_by": uuid4()} | fields)))


async def test_tabs_show_new_enquiries_on_every_page(api, database, seller, admin):
    type_id, slug = uuid4(), f"a-{uuid4().hex}"
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceEnquiryModel))
        session.add(MarketplaceAnimalTypeModel(id=type_id, name=f"Cow {type_id.hex}", slug=f"t-{type_id.hex}"))
        await session.flush()
        session.add(MarketplaceAnimalModel(seller_user_id=seller, animal_type_id=type_id, title="Gir", slug=slug, price=Decimal("1"), status=AnimalStatus.PUBLISHED))

    assert _tab_count((await api.get(f"{BASE}/products", headers=admin)).text, "Enquiries") is None

    await api.post(f"{API}/animals/{slug}/enquiries", json={"buyer_name": "Asha", "buyer_phone": "9876543210"})

    for url in (BASE, f"{BASE}/products", f"{BASE}/settings", f"{BASE}/orders"):
        assert _tab_count((await api.get(url, headers=admin)).text, "Enquiries") == "1"


async def test_overview_lists_the_newest_orders_first(api, database, seller, admin):
    category_id, product_id, variant_id = uuid4(), uuid4(), uuid4()
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=category_id, name=f"C {category_id.hex}", slug=f"c-{category_id.hex}"))
        await session.flush()
        session.add(MarketplaceProductModel(id=product_id, seller_user_id=seller, category_id=category_id, title="Ghee", slug=f"p-{product_id.hex}", status=ProductStatus.PUBLISHED))
        await session.flush()
        session.add(MarketplaceProductVariantModel(id=variant_id, product_id=product_id, name="1 L", mrp=Decimal("100"), price=Decimal("100"), stock=50, is_default=True))
    await _settings(database, delivery_charge=Decimal("0"))

    refs = []
    for _ in range(6):
        placed = await api.post(f"{API}/orders", json={
            "items": [{"variant_id": str(variant_id), "quantity": 1}], "buyer_name": "Asha Devi", "buyer_phone": "9876543210",
            "address_line": "12 Temple Road", "pincode": "302001", "checkout_token": str(uuid4()), "expected_total": "100.00",
        })
        refs.append(placed.json()["data"]["order_ref"])

    page = (await api.get(BASE, headers=admin)).text
    section = page.split('id="latest-title"')[1].split('id="low-stock-title"')[0]

    assert section.count('class="mk-item-title"') == 5
    assert sum(ref in section for ref in refs) == 5


@pytest.mark.parametrize(
    ("name", "icon"),
    [("Fresh Milk", "fa-glass-water"), ("Ghee & Butter", "fa-jar"), ("Curd", "fa-cheese"), ("Coconut Oils", "fa-bottle-droplet"), ("Honey", "fa-basket-shopping")],
)
async def test_category_without_a_picture_gets_a_fitting_icon(api, database, name, icon):
    row_id = uuid4()
    async with database.transaction() as session:
        await session.execute(delete(MarketplaceHomeSectionModel))
        session.add(MarketplaceCategoryModel(id=row_id, name=f"{name} {row_id.hex[:6]}", slug=f"s-{row_id.hex}", sort_order=-1))
        session.add(MarketplaceHomeSectionModel(section_type="CATEGORIES", title="Categories", item_limit=100))

    page = (await api.get("/marketplace", headers=HTML)).text
    # The same link also appears in the header and the door chips
    links = page.split(f'href="/marketplace/products?category=s-{row_id.hex}"')
    tile = next(part for part in links[1:] if "st-tile-letter" in part[:200])

    assert f'class="fa-solid {icon}"' in tile[:200]
