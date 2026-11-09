"""
Fills the store with demo listings so it can be shown before real data exists.

    python scripts/seed_marketplace_demo.py            add the demo data (safe to run again)
    python scripts/seed_marketplace_demo.py --remove   take it out again

Everything it adds can be told apart, so --remove leaves real data alone: listings have slugs
starting with "demo-"; banners, links and settings are matched against the values below.
It refuses to run in production. The pictures are drawn here and are not photographs.

Python 3.13+
"""

from __future__ import annotations

import argparse
import asyncio
import io
import sys
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path
from uuid import UUID

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image, ImageDraw, ImageFilter, ImageFont  # noqa: E402
from sqlalchemy import select  # noqa: E402
from sqlalchemy.orm import selectinload  # noqa: E402

from app.config.settings import settings  # noqa: E402
from app.modules.administration.domain.enums import Role  # noqa: E402
from app.modules.administration.infrastructure.models import UserModel  # noqa: E402
from app.modules.marketplace.domain.enums import (  # noqa: E402
    AnimalGender,
    AnimalStatus,
    BannerPlacement,
    PregnancyStatus,
    ProductStatus,
)
from app.modules.marketplace.infrastructure.models import (  # noqa: E402
    MarketplaceAnimalBreedModel,
    MarketplaceAnimalImageModel,
    MarketplaceAnimalModel,
    MarketplaceAnimalTypeModel,
    MarketplaceBannerModel,
    MarketplaceCategoryModel,
    MarketplaceProductImageModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
    MarketplaceSettingsModel,
    MarketplaceTrendingTagModel,
)
from app.modules.media.application.services import MediaUrlService  # noqa: E402
from app.modules.media.domain.enums import MediaCategory  # noqa: E402
from app.modules.media.infrastructure.image_compressor import ProcessedImage  # noqa: E402

ICON_FONT = ROOT / "app/web/static/vendor/fontawesome/6.4.0/webfonts/fa-solid-900.woff2"
COW, PAW = "", ""
GLASS, JAR, CHEESE, BOTTLE, DROPLET = "", "", "", "", ""

Colour = tuple[int, int, int]
CREAM: Colour = (251, 243, 222)
GOLD: Colour = (233, 180, 76)
FOREST: Colour = (23, 73, 47)
FOREST_DARK: Colour = (15, 53, 34)
BROWN: Colour = (122, 79, 6)


@dataclass(slots=True, kw_only=True)
class DemoProduct:
    slug: str
    category: str
    title: str
    short: str
    description: str
    sizes: tuple[tuple[str, int, int, int], ...]  # name, MRP, price, stock
    icon: str
    tones: tuple[Colour, Colour, Colour]  # gradient top, gradient bottom, icon
    brand: str | None = "Vitco Farms"
    specs: dict[str, str] = field(default_factory=dict)
    featured: bool = True
    trending: bool = False


@dataclass(slots=True, kw_only=True)
class DemoAnimal:
    slug: str
    kind: str
    breed: str
    title: str
    price: int
    age: int
    lactation: int
    milk: str
    fat: str | None
    district: str
    state: str
    description: str
    tones: tuple[Colour, Colour, Colour]
    icon: str = COW
    village: str | None = None
    negotiable: bool = True
    pregnant_months: int | None = None
    calf: str | None = None
    health: str = "Healthy, active and eating well. Checked by a local vet last month."
    vaccination: str = "FMD and HS vaccines are up to date. Card available."
    status: AnimalStatus = AnimalStatus.PUBLISHED
    featured: bool = True
    trending: bool = False


_MILK = ((226, 236, 240), (250, 250, 244), (84, 128, 150))
_GHEE = ((250, 228, 170), (240, 190, 90), (150, 96, 12))
_CURD = ((246, 240, 226), (232, 222, 198), (150, 124, 72))
_COCONUT = ((214, 232, 206), (156, 196, 146), (40, 96, 62))
_COW = ((226, 200, 168), (176, 132, 92), (84, 50, 26))
_RED_COW = ((232, 188, 156), (190, 110, 72), (102, 42, 18))
_BUFFALO = ((150, 156, 160), (84, 88, 94), (28, 30, 34))
_GOAT = ((232, 222, 196), (190, 172, 132), (94, 76, 40))

PRODUCTS = (
    DemoProduct(slug="demo-a2-gir-cow-milk", category="milk", title="A2 Gir Cow Milk", short="Fresh farm milk, chilled and delivered the same morning.", description="Milk from our Gir cows, chilled right after milking and packed the same day.\n\nBoil before use. Keep refrigerated.", sizes=(("500 ml", 45, 42, 80), ("1 L", 85, 78, 120)), icon=GLASS, tones=_MILK, specs={"Shelf life": "2 days, refrigerated", "Fat": "4.5%", "Pack": "Food-grade pouch"}, trending=True),
    DemoProduct(slug="demo-fresh-toned-milk", category="milk", title="Fresh Toned Milk", short="Everyday milk for tea, coffee and the family.", description="Light, everyday toned milk from nearby collection centres.", sizes=(("500 ml", 30, 28, 150), ("1 L", 58, 54, 200)), icon=GLASS, tones=_MILK, brand="Vitco Dairy", specs={"Shelf life": "2 days, refrigerated", "Fat": "3%"}),
    DemoProduct(slug="demo-buffalo-full-cream-milk", category="milk", title="Buffalo Full Cream Milk", short="Rich and creamy, great for sweets and thick chai.", description="Full cream buffalo milk with natural richness, ideal for sweets, curd and thick chai.", sizes=(("1 L", 78, 72, 90),), icon=GLASS, tones=_MILK, brand="Vitco Dairy", specs={"Shelf life": "2 days, refrigerated", "Fat": "6.5%"}),
    DemoProduct(slug="demo-desi-cow-ghee", category="ghee-butter", title="Pure Desi Cow Ghee", short="Slow-cooked the village way, with a rich aroma.", description="Made in small batches by slowly heating cultured butter from cow milk. Golden colour, grainy texture and the aroma of home.\n\nNo added colour or preservatives.", sizes=(("500 ml", 420, 389, 40), ("1 L", 820, 749, 35)), icon=JAR, tones=_GHEE, specs={"Shelf life": "9 months", "Made from": "Cow milk butter", "Storage": "Cool, dry place"}, trending=True),
    DemoProduct(slug="demo-buffalo-ghee", category="ghee-butter", title="Buffalo Ghee", short="Creamy white ghee for everyday cooking.", description="Smooth buffalo ghee with a mild taste, good for parathas, dal and sweets.", sizes=(("500 ml", 360, 335, 30), ("1 L", 700, 649, 18)), icon=JAR, tones=_GHEE, specs={"Shelf life": "9 months"}),
    DemoProduct(slug="demo-white-butter", category="ghee-butter", title="White Butter", short="Soft, unsalted makkhan, churned fresh.", description="Unsalted white butter, churned fresh. Spread it on hot rotis or use it for cooking.", sizes=(("200 g", 145, 129, 4), ("500 g", 320, 299, 8)), icon=JAR, tones=_GHEE, specs={"Shelf life": "7 days, refrigerated"}),
    DemoProduct(slug="demo-malai-paneer", category="curd-paneer", title="Malai Paneer", short="Soft fresh paneer, made every morning.", description="Soft paneer made fresh every morning from full cream milk.", sizes=(("200 g", 110, 99, 30), ("500 g", 260, 239, 22)), icon=CHEESE, tones=_CURD, brand="Vitco Dairy", specs={"Shelf life": "3 days, refrigerated"}, trending=True),
    DemoProduct(slug="demo-thick-set-curd", category="curd-paneer", title="Thick Set Curd", short="Thick, naturally set dahi.", description="Naturally set curd with a thick, creamy texture.", sizes=(("400 g", 55, 55, 0),), icon=CHEESE, tones=_CURD, brand="Vitco Dairy", specs={"Shelf life": "4 days, refrigerated"}),
    DemoProduct(slug="demo-sweet-lassi", category="curd-paneer", title="Sweet Lassi", short="Chilled, thick and lightly sweet.", description="Traditional thick lassi, lightly sweetened. Best served chilled.", sizes=(("200 ml", 30, 25, 60),), icon=GLASS, tones=_CURD, brand="Vitco Dairy", featured=False),
    DemoProduct(slug="demo-virgin-coconut-oil", category="coconut-oils", title="Virgin Coconut Oil", short="Cold pressed, for cooking, skin and hair.", description="Cold pressed from fresh coconut milk, with a light natural aroma.", sizes=(("250 ml", 299, 249, 25), ("500 ml", 560, 479, 15)), icon=BOTTLE, tones=_COCONUT, brand="Kerala Gold", specs={"Shelf life": "12 months", "Method": "Cold pressed"}, trending=True),
    DemoProduct(slug="demo-tender-coconut-water", category="coconut-oils", title="Tender Coconut Water", short="Naturally sweet and refreshing.", description="Bottled tender coconut water with nothing added.", sizes=(("330 ml", 90, 70, 35),), icon=DROPLET, tones=_COCONUT, brand="Kerala Gold", specs={"Shelf life": "30 days, unopened"}),
    DemoProduct(slug="demo-groundnut-oil", category="coconut-oils", title="Cold Pressed Groundnut Oil", short="Traditional wood-pressed cooking oil.", description="Wood-pressed groundnut oil with its natural flavour intact.", sizes=(("1 L", 340, 299, 40),), icon=BOTTLE, tones=_COCONUT, brand=None, featured=False),
)

ANIMALS = (
    DemoAnimal(slug="demo-gir-cow-second-lactation", kind="cow", breed="Gir", title="Gir cow, second lactation", price=85000, age=48, lactation=2, milk="14.5", fat="4.8", village="Chomu", district="Jaipur", state="Rajasthan", description="A calm, well-kept Gir cow in her second lactation. Easy to milk and used to hand and machine milking.\n\nMilk records are available and you are welcome to visit before buying.", tones=_RED_COW, calf="Female calf, 3 months old, can be sold together", trending=True),
    DemoAnimal(slug="demo-sahiwal-cow-calm-healthy", kind="cow", breed="Sahiwal", title="Sahiwal cow, calm and healthy", price=72000, age=36, lactation=1, milk="11", fat="4.5", district="Ajmer", state="Rajasthan", description="Young Sahiwal cow in her first lactation, with a good temperament and steady milk.", tones=_RED_COW, status=AnimalStatus.RESERVED),
    DemoAnimal(slug="demo-hf-cross-high-yield", kind="cow", breed="HF Cross", title="HF cross cow, high yield", price=95000, age=54, lactation=3, milk="22", fat="3.6", district="Karnal", state="Haryana", description="Strong HF cross cow giving a high daily yield on balanced feed. Suits a commercial dairy.", tones=_COW, negotiable=False, pregnant_months=3, trending=True),
    DemoAnimal(slug="demo-jersey-cross-cow", kind="cow", breed="Jersey Cross", title="Jersey cross cow, rich milk", price=68000, age=42, lactation=2, milk="15", fat="4.9", district="Nashik", state="Maharashtra", description="Compact Jersey cross cow with rich milk and low feed needs. Easy to manage for small farms.", tones=_COW),
    DemoAnimal(slug="demo-murrah-buffalo-high-yield", kind="buffalo", breed="Murrah", title="Murrah buffalo, high yield", price=125000, age=60, lactation=3, milk="16", fat="7.2", village="Barwala", district="Hisar", state="Haryana", description="Classic Murrah buffalo with tightly curled horns and a strong milk record.\n\nMilk slip from the collection centre can be shown on request.", tones=_BUFFALO, negotiable=False, calf="Male calf, 2 months old", trending=True),
    DemoAnimal(slug="demo-mehsana-buffalo", kind="buffalo", breed="Mehsana", title="Mehsana buffalo, steady milker", price=98000, age=56, lactation=2, milk="12.5", fat="7", district="Mehsana", state="Gujarat", description="Docile Mehsana buffalo known for a long, steady milking period.", tones=_BUFFALO, pregnant_months=5),
    DemoAnimal(slug="demo-jaffarabadi-buffalo", kind="buffalo", breed="Jaffarabadi", title="Jaffarabadi buffalo, heavy build", price=140000, age=66, lactation=4, milk="18", fat="7.5", district="Junagadh", state="Gujarat", description="Large Jaffarabadi buffalo with very rich milk. This listing shows how a sold animal looks.", tones=_BUFFALO, status=AnimalStatus.SOLD, featured=False),
    DemoAnimal(slug="demo-sirohi-goat-with-kid", kind="goat", breed="Sirohi", title="Sirohi goat with kid", price=18000, age=30, lactation=2, milk="2.5", fat=None, district="Sirohi", state="Rajasthan", description="Hardy Sirohi goat with a healthy kid. Does well in dry conditions.", tones=_GOAT, icon=PAW, calf="One kid, 2 months old"),
    DemoAnimal(slug="demo-jamunapari-goat", kind="goat", breed="Jamunapari", title="Jamunapari goat, long-legged milker", price=24000, age=28, lactation=1, milk="3", fat=None, district="Etawah", state="Uttar Pradesh", description="Tall Jamunapari goat with a good milk yield for her size.", tones=_GOAT, icon=PAW, featured=False),
    DemoAnimal(slug="demo-marwari-sheep", kind="sheep", breed="Marwari", title="Marwari sheep, young ewe", price=12000, age=20, lactation=1, milk="0.8", fat=None, district="Jodhpur", state="Rajasthan", description="Young Marwari ewe, well suited to dry grazing land.", tones=_GOAT, icon=PAW, featured=False),
)

BANNERS = (
    ("Milk you can trust, from cows you can meet", "Choose healthy Gir and Sahiwal cows with their milk records.", "Browse animals", "/marketplace/animals", BannerPlacement.HOME_HERO, COW, (FOREST_DARK, (46, 104, 70), GOLD)),
    ("Pure desi ghee, slow-cooked the village way", "Free delivery on orders above ₹499.", "Shop ghee", "/marketplace/products?category=ghee-butter", BannerPlacement.HOME_HERO, JAR, ((92, 58, 12), (190, 130, 40), CREAM)),
    ("Fresh milk at your door every morning", "Pay on delivery. No app or sign-up needed.", "Shop milk", "/marketplace/products?category=milk", BannerPlacement.HOME_HERO, GLASS, (FOREST_DARK, (70, 112, 110), CREAM)),
    ("Festive ghee offer", "Save on desi cow ghee", None, "/marketplace/products?category=ghee-butter", BannerPlacement.HOME_MIDDLE, JAR, ((92, 58, 12), (178, 118, 40), CREAM)),
    ("New buffaloes this week", "Murrah, Mehsana and more", None, "/marketplace/animals?type=buffalo", BannerPlacement.HOME_MIDDLE, COW, ((22, 56, 58), (60, 110, 112), CREAM)),
)

TAGS = (
    ("Gir cow", "/marketplace/animals?search=gir"),
    ("Murrah buffalo", "/marketplace/animals?search=murrah"),
    ("Desi ghee", "/marketplace/products?search=ghee"),
    ("Paneer", "/marketplace/products?search=paneer"),
    ("Coconut oil", "/marketplace/products?search=coconut"),
)

# Filled in only where the store has nothing yet. The phone numbers are not real.
SETTINGS: dict[str, object] = {
    "tagline": "Honest dairy animals and fresh farm products, sold directly.",
    "support_phone": "9000000000",
    "whatsapp_number": "919000000000",
    "support_email": "hello@example.com",
    "address": "Jaipur, Rajasthan",
    "delivery_charge": Decimal("40.00"),
    "free_delivery_above": Decimal("499.00"),
    "min_order_amount": Decimal("100.00"),
}
POLICIES = {
    "shipping": "Demo text. Orders inside our delivery area usually arrive the next morning.",
    "returns": "Demo text. Tell us within 24 hours if a product arrives damaged and we will replace it.",
    "terms": "Demo text. Animals are sold directly by the seller; please visit and inspect before you buy.",
    "privacy": "Demo text. We use your phone number and address only to deliver your order.",
}


# =========================================================
# PICTURES
# =========================================================


def draw_art(
    size: tuple[int, int], top: Colour, bottom: Colour, ink: Colour, icon: str,
    scale: float = .52, centre_x: float = .5, centre_y: float = .5,
) -> bytes:
    """A soft gradient with one large icon, so a demo card never looks broken."""
    width, height = size
    ramp = Image.linear_gradient("L").resize(size)
    picture = Image.composite(Image.new("RGB", size, bottom), Image.new("RGB", size, top), ramp)

    glow = Image.new("L", size, 0)
    radius = int(min(size) * .46)
    x, y = int(width * centre_x), int(height * centre_y)
    ImageDraw.Draw(glow).ellipse((x - radius, y - radius, x + radius, y + radius), fill=70)
    glow = glow.filter(ImageFilter.GaussianBlur(radius // 2))
    picture.paste(Image.new("RGB", size, (255, 255, 255)), mask=glow)

    font = ImageFont.truetype(str(ICON_FONT), int(min(size) * scale))
    ImageDraw.Draw(picture).text((x, y), icon, font=font, fill=ink, anchor="mm")

    buffer = io.BytesIO()
    picture.save(buffer, "WEBP", quality=84)
    return buffer.getvalue()


def _gallery(item: DemoProduct | DemoAnimal, size: tuple[int, int]) -> list[bytes]:
    top, bottom, ink = item.tones
    return [draw_art(size, top, bottom, ink, item.icon), draw_art(size, bottom, top, ink, item.icon, scale=.7)]


# =========================================================
# ADD
# =========================================================


async def add_demo(database, media) -> dict[str, int]:
    # Pictures first: drawing is slow, and the write lock should stay short
    product_art = {item.slug: _gallery(item, (800, 800)) for item in PRODUCTS}
    animal_art = {item.slug: _gallery(item, (960, 720)) for item in ANIMALS}
    banner_art = {banner[0]: draw_art(*_banner_shape(banner)) for banner in BANNERS}
    # Phones show the hero as a square with its text at the bottom, so the icon goes above the text
    phone_art = {
        title: draw_art((800, 800), top, bottom, ink, icon, scale=.28, centre_y=.2)
        for title, _, _, _, placement, icon, (top, bottom, ink) in BANNERS
        if placement == BannerPlacement.HOME_HERO
    }
    added = {"products": 0, "animals": 0, "banners": 0, "links": 0}

    async with database.transaction() as session:
        seller = await session.scalar(
            select(UserModel.id)
            .where(UserModel.role == Role.SUPER_ADMIN, UserModel.is_deleted.is_(False), UserModel.is_active.is_(True))
            .order_by(UserModel.created_at)
            .limit(1)
        )
        if seller is None:
            raise SystemExit("No active Super Admin found. Start the app once, then run this again.")

        added["products"] = await _add_products(session, media, seller, product_art)
        added["animals"] = await _add_animals(session, media, seller, animal_art)
        added["banners"] = await _add_banners(session, media, seller, banner_art, phone_art)
        added["links"] = await _add_links(session)
        await _fill_settings(session)
    return added


def _banner_shape(banner: tuple) -> tuple:
    _, _, _, _, placement, icon, (top, bottom, ink) = banner
    size = (1600, 600) if placement == BannerPlacement.HOME_HERO else (800, 300)
    return (size, top, bottom, ink, icon, .62, .78)


async def _store(media, data: bytes, category: MediaCategory, seller: UUID, name: str) -> tuple[UUID, str]:
    stored = await media.store_listing_image(ProcessedImage(data), category, seller, name)
    return stored.id, MediaUrlService.build(stored.storage_key)


async def _add_products(session, media, seller: UUID, art: dict[str, list[bytes]]) -> int:
    existing = set(await session.scalars(select(MarketplaceProductModel.slug).where(MarketplaceProductModel.slug.like("demo-%"))))
    categories = dict((await session.execute(select(MarketplaceCategoryModel.slug, MarketplaceCategoryModel.id))).all())
    count = 0
    for order, item in enumerate(PRODUCTS):
        if item.slug in existing or item.category not in categories:
            continue
        product = MarketplaceProductModel(
            seller_user_id=seller, category_id=categories[item.category], title=item.title, slug=item.slug, brand=item.brand,
            short_description=item.short, description=item.description,
            specifications=[{"label": label, "value": value} for label, value in item.specs.items()],
            status=ProductStatus.PUBLISHED, is_featured=item.featured, is_trending=item.trending, sort_order=order,
        )
        session.add(product)
        await session.flush()
        for position, (name, mrp, price, stock) in enumerate(item.sizes):
            session.add(MarketplaceProductVariantModel(
                product_id=product.id, name=name, mrp=Decimal(mrp), price=Decimal(price), stock=stock,
                is_default=position == 0, sort_order=position,
            ))
        for position, data in enumerate(art[item.slug]):
            media_id, url = await _store(media, data, MediaCategory.PRODUCT, seller, item.title)
            session.add(MarketplaceProductImageModel(product_id=product.id, media_id=media_id, url=url, alt_text=item.title, sort_order=position))
        count += 1
    return count


async def _add_animals(session, media, seller: UUID, art: dict[str, list[bytes]]) -> int:
    existing = set(await session.scalars(select(MarketplaceAnimalModel.slug).where(MarketplaceAnimalModel.slug.like("demo-%"))))
    types = dict((await session.execute(select(MarketplaceAnimalTypeModel.slug, MarketplaceAnimalTypeModel.id))).all())
    breeds = {
        (type_id, name): breed_id
        for type_id, name, breed_id in (await session.execute(
            select(MarketplaceAnimalBreedModel.animal_type_id, MarketplaceAnimalBreedModel.name, MarketplaceAnimalBreedModel.id)
        )).all()
    }
    count = 0
    for order, item in enumerate(ANIMALS):
        if item.slug in existing or item.kind not in types:
            continue
        type_id = types[item.kind]
        animal = MarketplaceAnimalModel(
            seller_user_id=seller, animal_type_id=type_id, breed_id=breeds.get((type_id, item.breed)), title=item.title, slug=item.slug,
            gender=AnimalGender.FEMALE, price=Decimal(item.price), is_negotiable=item.negotiable, age_months=item.age,
            lactation_number=item.lactation, milk_litres_per_day=Decimal(item.milk), fat_percent=Decimal(item.fat) if item.fat else None,
            pregnancy_status=PregnancyStatus.PREGNANT if item.pregnant_months else PregnancyStatus.NOT_PREGNANT,
            pregnancy_months=item.pregnant_months, calf_details=item.calf, health_notes=item.health, vaccination_notes=item.vaccination,
            village=item.village, district=item.district, state=item.state, description=item.description, status=item.status,
            is_featured=item.featured, is_trending=item.trending, sort_order=order,
        )
        session.add(animal)
        await session.flush()
        for position, data in enumerate(art[item.slug]):
            media_id, url = await _store(media, data, MediaCategory.ANIMAL, seller, item.title)
            session.add(MarketplaceAnimalImageModel(animal_id=animal.id, media_id=media_id, url=url, alt_text=item.title, sort_order=position))
        count += 1
    return count


async def _add_banners(session, media, seller: UUID, art: dict[str, bytes], phone_art: dict[str, bytes]) -> int:
    existing = set(await session.scalars(select(MarketplaceBannerModel.title)))
    count = 0
    for order, (title, subtitle, label, url, placement, _, _) in enumerate(BANNERS):
        if title in existing:
            continue
        _, image_url = await _store(media, art[title], MediaCategory.BANNER, seller, title)
        phone_url = None
        if title in phone_art:
            _, phone_url = await _store(media, phone_art[title], MediaCategory.BANNER, seller, title)
        session.add(MarketplaceBannerModel(title=title, subtitle=subtitle, cta_label=label, cta_url=url, image_url=image_url, mobile_image_url=phone_url, placement=placement, sort_order=order))
        count += 1
    return count


async def _add_links(session) -> int:
    existing = set(await session.scalars(select(MarketplaceTrendingTagModel.label)))
    count = 0
    for order, (label, url) in enumerate(TAGS):
        if label not in existing:
            session.add(MarketplaceTrendingTagModel(label=label, url=url, sort_order=order))
            count += 1
    return count


async def _fill_settings(session) -> None:
    row = await session.scalar(select(MarketplaceSettingsModel))
    if row is None:
        row = MarketplaceSettingsModel(store_name="Vitco Marketplace")
        session.add(row)
    for name, value in SETTINGS.items():
        if not getattr(row, name):  # nothing set yet, or a zero charge
            setattr(row, name, value)
    row.policies = POLICIES | (row.policies or {})


# =========================================================
# REMOVE
# =========================================================


async def remove_demo(database, media) -> dict[str, int]:
    removed = {"products": 0, "animals": 0, "banners": 0, "links": 0}
    async with database.transaction() as session:
        for key, model in (("products", MarketplaceProductModel), ("animals", MarketplaceAnimalModel)):
            rows = list(await session.scalars(select(model).where(model.slug.like("demo-%")).options(selectinload(model.images))))
            await media.delete_images([image.media_id for row in rows for image in row.images if image.media_id])
            for row in rows:
                await session.delete(row)
            removed[key] = len(rows)

        banners = list(await session.scalars(
            select(MarketplaceBannerModel).where(MarketplaceBannerModel.title.in_([banner[0] for banner in BANNERS]))
        ))
        for banner in banners:
            await media.delete_image_by_url(banner.image_url)
            await media.delete_image_by_url(banner.mobile_image_url)
            await session.delete(banner)
        removed["banners"] = len(banners)

        for label, url in TAGS:
            tag = await session.scalar(select(MarketplaceTrendingTagModel).where(MarketplaceTrendingTagModel.label == label, MarketplaceTrendingTagModel.url == url))
            if tag is not None:
                await session.delete(tag)
                removed["links"] += 1

        row = await session.scalar(select(MarketplaceSettingsModel))
        if row is not None:
            for name, value in SETTINGS.items():
                if getattr(row, name) == value:
                    default = Decimal("0") if name in ("delivery_charge", "min_order_amount") else None
                    setattr(row, name, default)
            row.policies = {key: text for key, text in (row.policies or {}).items() if POLICIES.get(key) != text}
    return removed


# =========================================================
# COMMAND
# =========================================================


async def _run(remove: bool) -> None:
    from app.main import app
    from app.modules.media.application.services import MediaService

    # Only the database, not the app's full startup: that also recovers Excel jobs,
    # which belong to the server that may be running right now.
    container = app.state.application.container
    await container.database.startup()
    try:
        media = container.resolve(MediaService)
        result = await (remove_demo if remove else add_demo)(container.database, media)
    finally:
        await container.database.shutdown()
    print(("Removed: " if remove else "Added: ") + ", ".join(f"{count} {name}" for name, count in result.items()))


def main() -> None:
    parser = argparse.ArgumentParser(description="Add or remove the marketplace demo data.")
    parser.add_argument("--remove", action="store_true", help="take the demo data out again")
    arguments = parser.parse_args()
    if settings.is_production:
        raise SystemExit("Refusing to run: this is a production environment.")
    asyncio.run(_run(arguments.remove))


if __name__ == "__main__":
    main()
