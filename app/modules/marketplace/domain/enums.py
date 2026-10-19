from enum import StrEnum

class MarketplaceOrderStatus(StrEnum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"

class MarketplacePostType(StrEnum):
    PRODUCT = "product"
    ANIMAL = "animal"


class ProductStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    DELETED = "deleted"


class ProductOfferStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    INACTIVE = "inactive"
    OUT_OF_STOCK = "out_of_stock"
    DELETED = "deleted"


class AnimalListingStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    SOLD = "sold"
    INACTIVE = "inactive"
    CANCELLED = "cancelled"
    DELETED = "deleted"


class AnimalGender(StrEnum):
    MALE = "male"
    FEMALE = "female"


class PregnancyStatus(StrEnum):
    NOT_APPLICABLE = "not_applicable"
    NOT_PREGNANT = "not_pregnant"
    PREGNANT = "pregnant"
    UNKNOWN = "unknown"

class AnimalType(StrEnum):
    BUFFALO = "Buffalo"
    COW = "Cow"
    GOAT = "Goat"
    SHEEP = "Sheep"
    OTHER = "Other"