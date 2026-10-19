"""
Marketplace API Pydantic Schemas

Validation & Response schemas for Marketplace APIs:
- Banners & Hero Banners
- Trending Search Tags
- Product Categories & Cards
- Cattle / Livestock Animals
- Catalog Products
- Marketplace Orders

Python 3.13+
"""
from typing import Any, List, Optional
from uuid import UUID
from pydantic import BaseModel, Field


# --- Banner Schemas ---

class CreateBannerRequest(BaseModel):
    """Request schema for creating a Hero Banner."""
    title: str = Field(..., min_length=1, description="Banner title")
    subtitle: Optional[str] = Field(None, description="Banner subtitle")
    badge: Optional[str] = Field(None, description="Badge text (e.g. OFFER)")
    image_url: Optional[str] = Field(None, description="Image URL")
    cta_text: Optional[str] = Field(None, description="Call-to-action text")
    cta_target_url: Optional[str] = Field(None, description="Target URL")
    bg_gradient: Optional[str] = Field(None, description="Background gradient CSS")
    sort_order: int = Field(0, description="Sort order index")


class BannerSchema(BaseModel):
    """Hero Banner schema."""
    id: str = Field(..., description="Banner UUID")
    title: str = Field(..., description="Title")
    subtitle: Optional[str] = Field(None, description="Subtitle")
    badge: Optional[str] = Field(None, description="Badge")
    image_url: Optional[str] = Field(None, description="Image URL")
    image: Optional[str] = Field(None, description="Display image fallback URL")
    cta_text: Optional[str] = Field(None, description="CTA Text")
    cta_target_url: Optional[str] = Field(None, description="CTA Target URL")
    bg_gradient: Optional[str] = Field(None, description="Background gradient")
    sort_order: int = Field(0, description="Sort order")
    is_active: bool = Field(True, description="Active status")


# --- Trending Tag Schemas ---

class CreateTrendingTagRequest(BaseModel):
    """Request schema for creating a Trending Search Tag."""
    title: str = Field(..., min_length=1, description="Tag title (e.g. Sahiwal Cow)")
    url_path: str = Field(..., description="Filter path URL")
    sort_order: int = Field(0, description="Sort order index")


class TrendingTagSchema(BaseModel):
    """Trending Search Tag schema."""
    id: str = Field(..., description="Tag UUID")
    title: str = Field(..., description="Tag title")
    url_path: str = Field(..., description="Filter path URL")
    sort_order: int = Field(0, description="Sort order")
    is_active: bool = Field(True, description="Active status")


# --- Category Schemas ---

class CreateCategoryRequest(BaseModel):
    """Request schema for creating a Marketplace Category."""
    name: str = Field(..., min_length=1, description="Category name")
    slug: Optional[str] = Field(None, description="Category slug identifier")
    description: Optional[str] = Field(None, description="Description")
    color: Optional[str] = Field(None, description="Hex accent color")
    icon: Optional[str] = Field(None, description="Icon class or URL")
    sort_order: int = Field(0, description="Sort order")


class CategorySchema(BaseModel):
    """Marketplace Category schema."""
    id: str = Field(..., description="Category UUID")
    name: str = Field(..., description="Name")
    slug: str = Field(..., description="Slug")
    description: Optional[str] = Field(None, description="Description")
    color: Optional[str] = Field(None, description="Color code")
    icon: Optional[str] = Field(None, description="Icon class")
    sort_order: int = Field(0, description="Sort order")
    is_active: bool = Field(True, description="Active status")


# --- Animal / Livestock Schemas ---

class CreateAnimalRequest(BaseModel):
    """Request schema for listing a Cattle/Livestock Animal."""
    animal_type: str = Field(..., description="Cow, Buffalo, Goat, Sheep, Bull, etc.")
    title: str = Field(..., min_length=1, description="Listing title")
    price: float = Field(..., gt=0.0, description="Price in INR")
    breed: Optional[str] = Field(None, description="Breed name (e.g. Gir, Murrah)")
    age_months: Optional[int] = Field(None, ge=0, description="Age in months")
    milk_yield_liters: Optional[float] = Field(None, ge=0.0, description="Daily milk yield in Liters")
    lactation: Optional[int] = Field(None, ge=0, description="Lactation number")
    discount_percent: Optional[float] = Field(None, ge=0.0, le=100.0, description="Discount percentage")
    badge: Optional[str] = Field(None, description="Badge text (e.g. HIGH YIELD)")
    description: Optional[str] = Field(None, description="Detailed description")
    images: List[str] = Field(default_factory=list, description="List of image URLs")


class AnimalSchema(BaseModel):
    """Animal listing schema."""
    id: str = Field(..., description="Listing UUID")
    seller_user_id: Optional[str] = Field(None, description="Seller User UUID")
    seller_name: Optional[str] = Field(None, description="Seller Name")
    animal_type: str = Field(..., description="Animal Type")
    title: str = Field(..., description="Title")
    price: float = Field(..., description="Price")
    original_price: Optional[float] = Field(None, description="Original Price before discount")
    breed: Optional[str] = Field(None, description="Breed")
    age_months: Optional[int] = Field(None, description="Age in months")
    milk_yield_liters: Optional[float] = Field(None, description="Milk yield in Liters")
    lactation: Optional[int | str] = Field(None, description="Lactation number or description")
    discount_percent: Optional[float] = Field(None, description="Discount %")
    badge: Optional[str] = Field(None, description="Badge text")
    description: Optional[str] = Field(None, description="Description")
    images: List[str] = Field(default_factory=list, description="Images list")
    is_active: bool = Field(True, description="Active status")


# --- Catalog Product Schemas ---

class CreateProductRequest(BaseModel):
    """Request schema for creating a Catalog Product."""
    category_id: UUID = Field(..., description="Category UUID")
    title: str = Field(..., min_length=1, description="Product title")
    price: float = Field(..., gt=0.0, description="Price")
    compare_at_price: Optional[float] = Field(None, description="Original price before discount")
    brand_name: Optional[str] = Field(None, description="Brand name")
    description: Optional[str] = Field(None, description="Description")
    badge: Optional[str] = Field(None, description="Badge text")
    is_featured: bool = Field(False, description="Featured product flag")
    images: List[str] = Field(default_factory=list, description="List of product image URLs")


class ProductSchema(BaseModel):
    """Catalog Product schema."""
    id: str = Field(..., description="Product UUID")
    category_id: str = Field(..., description="Category UUID")
    category_name: Optional[str] = Field(None, description="Category Name")
    title: str = Field(..., description="Product title")
    price: float = Field(..., description="Price")
    compare_at_price: Optional[float] = Field(None, description="Original price")
    discount_percent: Optional[float] = Field(None, description="Discount %")
    brand_name: Optional[str] = Field(None, description="Brand name")
    description: Optional[str] = Field(None, description="Description")
    badge: Optional[str] = Field(None, description="Badge")
    is_featured: bool = Field(False, description="Featured flag")
    images: List[str] = Field(default_factory=list, description="Product images")
    is_active: bool = Field(True, description="Active status")


# --- Order Schemas ---

class CreateOrderRequest(BaseModel):
    """Request schema for placing a Marketplace Order."""
    item_type: str = Field("product", description="'animal' or 'product'")
    item_id: UUID = Field(..., description="Target Animal/Product UUID")
    quantity: int = Field(1, ge=1, description="Quantity")
    delivery_address: str = Field(..., min_length=1, description="Shipping/Delivery address")
    contact_phone: Optional[str] = Field(None, description="Contact phone number")
    notes: Optional[str] = Field(None, description="Order notes")


class OrderSchema(BaseModel):
    """Marketplace Order schema."""
    id: str = Field(..., description="Order UUID")
    buyer_user_id: str = Field(..., description="Buyer User UUID")
    buyer_name: Optional[str] = Field(None, description="Buyer Name")
    item_type: str = Field(..., description="animal or product")
    item_id: str = Field(..., description="Item UUID")
    item_title: Optional[str] = Field(None, description="Item Title")
    quantity: int = Field(..., description="Quantity")
    unit_price: float = Field(..., description="Unit price")
    total_amount: float = Field(..., description="Total order amount")
    status: str = Field(..., description="Order status (PENDING, CONFIRMED, COMPLETED, CANCELLED)")
    delivery_address: Optional[str] = Field(None, description="Delivery address")
    contact_phone: Optional[str] = Field(None, description="Contact phone")
    created_at: str = Field(..., description="Creation timestamp")


class UpdateOrderStatusRequest(BaseModel):
    """Request schema for updating order status."""
    status: str = Field(..., description="PENDING, CONFIRMED, SHIPPED, DELIVERED, CANCELLED")


# --- Catalog Summary Data & Responses ---

class CatalogData(BaseModel):
    """Marketplace Catalog Summary Data payload."""
    banners: List[BannerSchema] = Field(default_factory=list, description="Hero Banners")
    trending_tags: List[TrendingTagSchema] = Field(default_factory=list, description="Trending Search Tags")
    categories: List[CategorySchema] = Field(default_factory=list, description="Product Categories")
    animals: List[AnimalSchema] = Field(default_factory=list, description="Cattle/Livestock Animals")
    products: List[ProductSchema] = Field(default_factory=list, description="Catalog Products")
    animal_types: List[str] = Field(default_factory=list, description="Available animal type filter options")


class MarketplaceCatalogResponse(BaseModel):
    """Catalog Response Wrapper."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Marketplace catalog fetched successfully", description="Response message")
    data: CatalogData = Field(..., description="Catalog summary payload")


class MarketplaceListResponse(BaseModel):
    """Standard paginated response wrapper for generic marketplace list items."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Marketplace items fetched successfully", description="Response message")
    items: List[Any] = Field(default_factory=list, description="Items list")
    limit: Optional[int] = Field(None, description="Items per page")
    offset: Optional[int] = Field(None, description="Offset")
    total: int = Field(0, description="Total matching items")
    pages: int = Field(1, description="Total pages")
    next_page: Optional[int] = Field(None, description="Next page number")
    has_more: bool = Field(False, description="Has more pages indicator")
    type: Optional[str] = Field(None, description="Type of items")


class MarketplaceSingleResponse(BaseModel):
    """Single marketplace record response wrapper."""
    status: bool = Field(True, description="Status indicator")
    code: int = Field(200, description="HTTP status code")
    message: str = Field("Operation successful", description="Response message")
    data: Any = Field(..., description="Data object")
    type: str = Field(..., description="Data object")
