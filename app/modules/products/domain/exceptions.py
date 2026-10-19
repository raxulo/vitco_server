from app.core.exceptions.base import ApplicationException


class ProductNotFoundException(ApplicationException):

    code = "PRODUCT_NOT_FOUND"
    message = "Product not found."
    status_code = 404


class ProductCodeAlreadyExistsException(ApplicationException):

    code = "PRODUCT_CODE_ALREADY_EXISTS"
    message = "Product code already exists."
    status_code = 409


class InvalidProductException(ApplicationException):

    code = "INVALID_PRODUCT"
    message = "Invalid product configurations."
    status_code = 400