"""
Marketplace domain exceptions.

Python 3.13+
"""

from app.core.exceptions.base import ApplicationException


class SellingNotAllowedException(ApplicationException):
    code = "MARKETPLACE_SELLING_NOT_ALLOWED"
    message = "You are not allowed to manage marketplace listings."
    status_code = 403


class ListingValidationException(ApplicationException):
    """Carries one message per form field in `errors`."""

    code = "MARKETPLACE_INVALID_LISTING"
    message = "Please correct the highlighted fields."
    status_code = 422

    def __init__(self, errors: dict[str, str]) -> None:
        super().__init__(details=errors)
        self.errors = errors


class MasterInUseException(ApplicationException):
    code = "MARKETPLACE_MASTER_IN_USE"
    message = "This record is in use and cannot be deleted. Deactivate it instead."
    status_code = 409


class CategoryNotFoundException(ApplicationException):
    code = "MARKETPLACE_CATEGORY_NOT_FOUND"
    message = "Category not found."
    status_code = 404


class AnimalTypeNotFoundException(ApplicationException):
    code = "MARKETPLACE_ANIMAL_TYPE_NOT_FOUND"
    message = "Animal type not found."
    status_code = 404


class AnimalBreedNotFoundException(ApplicationException):
    code = "MARKETPLACE_ANIMAL_BREED_NOT_FOUND"
    message = "Animal breed not found."
    status_code = 404


class ProductNotFoundException(ApplicationException):
    code = "MARKETPLACE_PRODUCT_NOT_FOUND"
    message = "Product not found."
    status_code = 404


class AnimalNotFoundException(ApplicationException):
    code = "MARKETPLACE_ANIMAL_NOT_FOUND"
    message = "Animal not found."
    status_code = 404


class TooManyRequestsException(ApplicationException):
    code = "MARKETPLACE_TOO_MANY_REQUESTS"
    message = "Too many attempts. Please wait a few minutes and try again."
    status_code = 429

    def __init__(self, retry_after: int) -> None:
        super().__init__(details={"retry_after": retry_after})
        self.retry_after = retry_after


class OrderNotFoundException(ApplicationException):
    code = "MARKETPLACE_ORDER_NOT_FOUND"
    message = "Order not found."
    status_code = 404


class InvalidOrderMoveException(ApplicationException):
    code = "MARKETPLACE_INVALID_ORDER_MOVE"
    message = "This order cannot move to that status."
    status_code = 409


class OutOfStockException(ApplicationException):
    """Raised inside the order savepoint, so stock already taken goes back."""

    code = "MARKETPLACE_OUT_OF_STOCK"
    message = "Some items just went out of stock. Please review your cart."
    status_code = 409


class DuplicateCheckoutException(ApplicationException):
    code = "MARKETPLACE_DUPLICATE_CHECKOUT"
    message = "This order was already placed."
    status_code = 409


class EnquiryNotFoundException(ApplicationException):
    code = "MARKETPLACE_ENQUIRY_NOT_FOUND"
    message = "Enquiry not found."
    status_code = 404


class AnimalNotAvailableException(ApplicationException):
    code = "MARKETPLACE_ANIMAL_NOT_AVAILABLE"
    message = "This animal has been sold."
    status_code = 409


class BannerNotFoundException(ApplicationException):
    code = "MARKETPLACE_BANNER_NOT_FOUND"
    message = "Banner not found."
    status_code = 404


class HomeSectionNotFoundException(ApplicationException):
    code = "MARKETPLACE_HOME_SECTION_NOT_FOUND"
    message = "Home section not found."
    status_code = 404


class TrendingTagNotFoundException(ApplicationException):
    code = "MARKETPLACE_TRENDING_TAG_NOT_FOUND"
    message = "Trending link not found."
    status_code = 404
