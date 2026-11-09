"""
Marketplace catalog repository interface.

Listing methods take the viewer: Super Admin reaches every listing, any other seller
only their own (DECISION-016). Reaching someone else's listing reads as "not found".

Python 3.13+
"""

from abc import ABC, abstractmethod
from datetime import datetime
from uuid import UUID

from app.modules.marketplace.domain.dto import (
    AnimalCard,
    AnimalDetail,
    AnimalFilters,
    AnimalTypeTile,
    BreedOption,
    CatalogOverview,
    CategoryTile,
    LowStockItem,
    ProductCard,
    ProductDetail,
    ProductFilters,
    SitemapListing,
)
from app.modules.marketplace.domain.entities import (
    Animal,
    AnimalBreed,
    AnimalType,
    Category,
    Enquiry,
    ListingViewer,
    Product,
)
from app.modules.marketplace.domain.enums import (
    AnimalStatus,
    BannerPlacement,
    EnquiryStatus,
    OrderStatus,
    ProductStatus,
)
from app.modules.marketplace.domain.merchandising import Banner, HomeSection, StoreSettings, TrendingTag
from app.modules.marketplace.domain.orders import CartVariant, Order, OrderSummary


class IOrderRepository(ABC):

    @abstractmethod
    async def cart_variants(self, variant_ids: set[UUID]) -> list[CartVariant]:
        """Only sizes that can be bought now: active, on a live product in an active category."""

    @abstractmethod
    async def take_stock(self, variant_id: UUID, quantity: int) -> bool:
        """Atomically reduce stock; False when there is not enough."""

    @abstractmethod
    async def return_stock(self, variant_id: UUID, quantity: int) -> None: ...

    @abstractmethod
    async def ref_for_token(self, checkout_token: str) -> str | None: ...

    @abstractmethod
    async def add_order(self, order: Order) -> None:
        """Raises DuplicateCheckoutException when the checkout token was already used."""

    @abstractmethod
    async def find_for_tracking(self, order_ref: str, phone: str) -> Order | None: ...

    @abstractmethod
    async def get_by_ref(self, order_ref: str) -> Order | None: ...

    @abstractmethod
    async def list_orders(
        self, viewer: ListingViewer, keyword: str | None, status: OrderStatus | None, offset: int, limit: int
    ) -> tuple[list[OrderSummary], int]: ...

    @abstractmethod
    async def get_order(self, order_id: UUID, viewer: ListingViewer) -> Order | None: ...

    @abstractmethod
    async def move_order(self, order: Order, from_status: OrderStatus) -> bool:
        """Saves the new status only if the order is still in from_status; False when someone got there first."""


class IStorefrontRepository(ABC):
    """What customers can see. No viewer: only live listings are ever returned."""

    @abstractmethod
    async def top_categories(self) -> list[CategoryTile]: ...

    @abstractmethod
    async def animal_types(self) -> list[AnimalTypeTile]: ...

    @abstractmethod
    async def featured_products(self, limit: int) -> list[ProductCard]: ...

    @abstractmethod
    async def trending_products(self, limit: int) -> list[ProductCard]: ...

    @abstractmethod
    async def category_products(self, category_id: UUID, limit: int) -> list[ProductCard]: ...

    @abstractmethod
    async def category_slug(self, category_id: UUID) -> str | None: ...

    @abstractmethod
    async def featured_animals(self, limit: int) -> list[AnimalCard]: ...

    @abstractmethod
    async def trending_animals(self, limit: int) -> list[AnimalCard]: ...

    @abstractmethod
    async def all_categories(self) -> list[tuple[UUID, UUID | None, str, str]]:
        """Active categories as (id, parent_id, name, slug)."""

    @abstractmethod
    async def animal_type_id(self, slug: str) -> UUID | None: ...

    @abstractmethod
    async def breeds_of_type(self, animal_type_id: UUID) -> list[BreedOption]: ...

    @abstractmethod
    async def list_products(self, filters: ProductFilters) -> tuple[list[ProductCard], int]: ...

    @abstractmethod
    async def list_animals(self, filters: AnimalFilters) -> tuple[list[AnimalCard], int]: ...

    @abstractmethod
    async def product_detail(self, slug: str) -> ProductDetail | None: ...

    @abstractmethod
    async def animal_detail(self, slug: str) -> AnimalDetail | None: ...

    @abstractmethod
    async def related_products(self, category_id: UUID, exclude_slug: str, limit: int) -> list[ProductCard]: ...

    @abstractmethod
    async def similar_animals(self, animal_type_id: UUID, exclude_slug: str, limit: int) -> list[AnimalCard]: ...

    @abstractmethod
    async def sitemap_products(self, limit: int) -> list[SitemapListing]: ...

    @abstractmethod
    async def sitemap_animals(self, limit: int) -> list[SitemapListing]: ...

    @abstractmethod
    async def enquiry_target(self, slug: str) -> tuple[UUID, UUID, str, AnimalStatus] | None:
        """(animal id, seller id, title, status) of an animal that can be opened publicly."""

    @abstractmethod
    async def open_enquiry_exists(self, animal_id: UUID, phone: str) -> bool: ...

    @abstractmethod
    async def add_enquiry(self, enquiry: Enquiry) -> None: ...


class IMerchandisingRepository(ABC):
    """Banners, home sections, trending links and store settings."""

    @abstractmethod
    async def save_banner(self, banner: Banner) -> None: ...

    @abstractmethod
    async def get_banner(self, banner_id: UUID) -> Banner | None: ...

    @abstractmethod
    async def list_banners(self) -> list[Banner]: ...

    @abstractmethod
    async def live_banners(self, placement: BannerPlacement, now: datetime) -> list[Banner]: ...

    @abstractmethod
    async def delete_banner(self, banner_id: UUID) -> None: ...

    @abstractmethod
    async def save_home_section(self, section: HomeSection) -> None: ...

    @abstractmethod
    async def get_home_section(self, section_id: UUID) -> HomeSection | None: ...

    @abstractmethod
    async def list_home_sections(self, visible_only: bool = False) -> list[HomeSection]: ...

    @abstractmethod
    async def delete_home_section(self, section_id: UUID) -> None: ...

    @abstractmethod
    async def save_trending_tag(self, tag: TrendingTag) -> None: ...

    @abstractmethod
    async def get_trending_tag(self, tag_id: UUID) -> TrendingTag | None: ...

    @abstractmethod
    async def list_trending_tags(self, active_only: bool = False) -> list[TrendingTag]: ...

    @abstractmethod
    async def delete_trending_tag(self, tag_id: UUID) -> None: ...

    @abstractmethod
    async def get_settings(self) -> StoreSettings | None: ...

    @abstractmethod
    async def save_settings(self, settings: StoreSettings, updated_by: UUID) -> None: ...


class IMarketplaceRepository(ABC):

    # ----- Masters -----

    @abstractmethod
    async def save_category(self, category: Category) -> None: ...

    @abstractmethod
    async def get_category(self, category_id: UUID) -> Category | None: ...

    @abstractmethod
    async def list_categories(self, active_only: bool = False) -> list[Category]: ...

    @abstractmethod
    async def category_slug_taken(self, slug: str) -> bool: ...

    @abstractmethod
    async def category_usage(self, category_id: UUID) -> int:
        """Products (deleted ones too, they still hold the link) plus sub-categories."""

    @abstractmethod
    async def delete_category(self, category_id: UUID) -> None: ...

    @abstractmethod
    async def save_animal_type(self, animal_type: AnimalType) -> None: ...

    @abstractmethod
    async def get_animal_type(self, animal_type_id: UUID) -> AnimalType | None: ...

    @abstractmethod
    async def list_animal_types(self, active_only: bool = False) -> list[AnimalType]: ...

    @abstractmethod
    async def animal_type_name_taken(self, name: str, exclude_id: UUID | None = None) -> bool: ...

    @abstractmethod
    async def animal_type_usage(self, animal_type_id: UUID) -> int:
        """Animals (deleted ones too) plus breeds."""

    @abstractmethod
    async def delete_animal_type(self, animal_type_id: UUID) -> None: ...

    @abstractmethod
    async def save_animal_breed(self, breed: AnimalBreed) -> None: ...

    @abstractmethod
    async def get_animal_breed(self, breed_id: UUID) -> AnimalBreed | None: ...

    @abstractmethod
    async def list_animal_breeds(self, animal_type_id: UUID | None = None, active_only: bool = False) -> list[AnimalBreed]: ...

    @abstractmethod
    async def breed_name_taken(self, animal_type_id: UUID, name: str, exclude_id: UUID | None = None) -> bool: ...

    @abstractmethod
    async def animal_breed_usage(self, breed_id: UUID) -> int: ...

    @abstractmethod
    async def delete_animal_breed(self, breed_id: UUID) -> None: ...

    # ----- Enquiries -----

    @abstractmethod
    async def list_enquiries(
        self, viewer: ListingViewer, keyword: str | None, status: EnquiryStatus | None, offset: int, limit: int
    ) -> tuple[list[Enquiry], int]: ...

    @abstractmethod
    async def update_enquiry(
        self, enquiry_id: UUID, viewer: ListingViewer, status: EnquiryStatus, notes: str | None
    ) -> None: ...

    # ----- Overview -----

    @abstractmethod
    async def overview(self, viewer: ListingViewer) -> CatalogOverview: ...

    @abstractmethod
    async def low_stock(self, viewer: ListingViewer, limit: int) -> list[LowStockItem]: ...

    # ----- Products -----

    @abstractmethod
    async def create_product(self, product: Product) -> None: ...

    @abstractmethod
    async def update_product(self, product: Product, viewer: ListingViewer) -> None: ...

    @abstractmethod
    async def get_product(self, product_id: UUID, viewer: ListingViewer) -> Product | None: ...

    @abstractmethod
    async def list_products(
        self, viewer: ListingViewer, keyword: str | None, offset: int, limit: int, status: ProductStatus | None = None
    ) -> tuple[list[Product], int]: ...

    @abstractmethod
    async def product_slug_taken(self, slug: str) -> bool: ...

    @abstractmethod
    async def sku_taken(self, sku: str, exclude_variant_ids: set[UUID]) -> bool: ...

    @abstractmethod
    async def delete_product(self, product_id: UUID, viewer: ListingViewer) -> None: ...

    # ----- Animals -----

    @abstractmethod
    async def create_animal(self, animal: Animal) -> None: ...

    @abstractmethod
    async def update_animal(self, animal: Animal, viewer: ListingViewer) -> None: ...

    @abstractmethod
    async def get_animal(self, animal_id: UUID, viewer: ListingViewer) -> Animal | None: ...

    @abstractmethod
    async def list_animals(
        self, viewer: ListingViewer, keyword: str | None, offset: int, limit: int, status: AnimalStatus | None = None
    ) -> tuple[list[Animal], int]: ...

    @abstractmethod
    async def animal_slug_taken(self, slug: str) -> bool: ...

    @abstractmethod
    async def delete_animal(self, animal_id: UUID, viewer: ListingViewer) -> None: ...
