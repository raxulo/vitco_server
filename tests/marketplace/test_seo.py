"""What search engines see, through the real app."""

import json
import re
from decimal import Decimal
from uuid import UUID, uuid4
from xml.etree import ElementTree

import pytest

from app.config.settings import settings
from app.modules.administration.domain.enums import Role
from app.modules.marketplace.domain.enums import AnimalStatus, ProductStatus
from app.modules.marketplace.infrastructure.models import (
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceCategoryModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)
from tests.dataexchange.factories import create_user

HTML = {"accept": "text/html"}
NOINDEX = '<meta name="robots" content="noindex">'


@pytest.fixture
async def seller(database) -> UUID:
    return await create_user(database, role=Role.SUPER_ADMIN)


async def _product(database, seller: UUID, title: str, status=ProductStatus.PUBLISHED, stock: int = 5) -> str:
    product_id, category_id = uuid4(), uuid4()
    slug = f"p-{product_id.hex}"
    async with database.transaction() as session:
        session.add(MarketplaceCategoryModel(id=category_id, name=f"Cat {category_id.hex}", slug=f"c-{category_id.hex}"))
        await session.flush()
        session.add(MarketplaceProductModel(id=product_id, seller_user_id=seller, category_id=category_id, title=title, slug=slug, status=status))
        await session.flush()
        session.add(MarketplaceProductVariantModel(product_id=product_id, name="1 L", mrp=Decimal("120"), price=Decimal("100.50"), stock=stock, is_default=True))
        session.add(MarketplaceProductImageModel(product_id=product_id, url="/media/ghee.webp"))
    return slug


async def _animal(database, seller: UUID, status=AnimalStatus.PUBLISHED) -> str:
    type_id, slug = uuid4(), f"a-{uuid4().hex}"
    async with database.transaction() as session:
        session.add(MarketplaceAnimalTypeModel(id=type_id, name=f"Cow {type_id.hex}", slug=f"t-{type_id.hex}"))
        await session.flush()
        session.add(MarketplaceAnimalModel(seller_user_id=seller, animal_type_id=type_id, title="Gir", slug=slug, price=Decimal("85000"), status=status))
    return slug


def _json_ld(html: str) -> dict:
    return json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1))


def _meta(html: str, name: str) -> str:
    return re.search(rf'<meta property="{name}" content="([^"]*)"', html).group(1)


def _canonical(html: str) -> str:
    return re.search(r'<link rel="canonical" href="([^"]*)"', html).group(1)


async def test_product_page_has_structured_data_and_previews(api, database, seller):
    slug = await _product(database, seller, "Desi Ghee", stock=0)

    html = (await api.get(f"/marketplace/products/{slug}", headers=HTML)).text
    data = _json_ld(html)

    assert data["@type"] == "Product" and data["name"] == "Desi Ghee"
    assert data["offers"][0]["price"] == "100.50" and data["offers"][0]["priceCurrency"] == "INR"
    assert data["offers"][0]["availability"].endswith("OutOfStock")
    assert data["image"][0].endswith("/media/ghee.webp") and data["image"][0].startswith("http")
    assert _canonical(html).endswith(f"/marketplace/products/{slug}")
    assert _meta(html, "og:type") == "product"
    assert _meta(html, "og:image").endswith("/media/ghee.webp")
    assert "Desi Ghee" in _meta(html, "og:title")


@pytest.mark.parametrize(
    ("status", "availability"),
    [(AnimalStatus.PUBLISHED, "InStock"), (AnimalStatus.RESERVED, "LimitedAvailability"), (AnimalStatus.SOLD, "SoldOut")],
)
async def test_animal_availability_is_truthful(api, database, seller, status, availability):
    slug = await _animal(database, seller, status)
    data = _json_ld((await api.get(f"/marketplace/animals/{slug}", headers=HTML)).text)
    assert data["offers"]["availability"].endswith(availability)
    assert data["offers"]["price"] == "85000.00"


async def test_hostile_title_stays_inert(api, database, seller):
    title = '</script><script>alert(1)</script>"\'&'
    slug = await _product(database, seller, title)

    html = (await api.get(f"/marketplace/products/{slug}", headers=HTML)).text

    assert "<script>alert(1)" not in html
    assert _json_ld(html)["name"] == title  # still correct for the search engine


@pytest.mark.parametrize(
    "url", ["/marketplace/cart", "/marketplace/checkout", "/marketplace/track", "/marketplace/search?q=ghee", "/marketplace/products/nope"]
)
async def test_private_and_thin_pages_are_noindex(api, url):
    html = (await api.get(url, headers=HTML, follow_redirects=True)).text
    assert NOINDEX in html
    assert 'rel="canonical"' not in html and 'property="og:' not in html


@pytest.mark.parametrize("url", ["/marketplace", "/marketplace/products", "/marketplace/animals"])
async def test_public_pages_can_be_indexed(api, url):
    html = (await api.get(url, headers=HTML)).text
    assert NOINDEX not in html
    assert _canonical(html).endswith(url)


async def test_filters_share_a_canonical_but_pages_and_categories_do_not(api):
    filtered = (await api.get("/marketplace/products?min_price=10&sort=price_asc&search=x", headers=HTML)).text
    assert _canonical(filtered).endswith("/marketplace/products")

    second = (await api.get("/marketplace/animals?page=2&sort=milk_desc", headers=HTML)).text
    assert _canonical(second).endswith("/marketplace/animals?page=2")


async def test_public_url_setting_wins_over_the_host_header(api, database, seller, monkeypatch):
    monkeypatch.setattr(settings, "MARKETPLACE_PUBLIC_URL", "https://shop.example.com/")
    slug = await _product(database, seller, "Ghee")

    html = (await api.get(f"/marketplace/products/{slug}", headers={**HTML, "host": "evil.example"})).text

    assert _canonical(html) == f"https://shop.example.com/marketplace/products/{slug}"
    assert "evil.example" not in _canonical(html)


async def test_robots_opens_only_the_store(api):
    response = await api.get("/robots.txt")
    lines = response.text.splitlines()

    assert response.status_code == 200
    assert "Allow: /marketplace" in lines and "Disallow: /" in lines
    assert "Disallow: /marketplace/checkout" in lines
    assert next(line for line in lines if line.startswith("Sitemap:")).endswith("/sitemap.xml")


async def test_sitemap_lists_only_live_listings(api, database, seller):
    live = await _product(database, seller, "Live")
    draft = await _product(database, seller, "Draft", status=ProductStatus.DRAFT)
    animal = await _animal(database, seller)
    reserved = await _animal(database, seller, AnimalStatus.RESERVED)
    sold = await _animal(database, seller, AnimalStatus.SOLD)
    hidden = await _animal(database, seller, AnimalStatus.DRAFT)

    response = await api.get("/sitemap.xml")

    assert response.status_code == 200 and "xml" in response.headers["content-type"]
    names = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    urls = [node.text for node in ElementTree.fromstring(response.text).findall("s:url/s:loc", names)]
    assert any(url.endswith(f"/marketplace/products/{live}") for url in urls)
    assert any(url.endswith(f"/marketplace/animals/{animal}") for url in urls)
    assert any(url.endswith(f"/marketplace/animals/{reserved}") for url in urls)
    for gone in (draft, sold, hidden):
        assert not any(url.endswith(gone) for url in urls)
    assert any(url.endswith("/marketplace/products") for url in urls)
    assert not any("/admin" in url or "/checkout" in url or "/cart" in url for url in urls)
