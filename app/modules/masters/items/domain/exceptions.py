from app.core.exceptions.base import ApplicationException


class ItemNotFoundException(ApplicationException):

    code = "ITEM_NOT_FOUND"
    message = "Item not found."
    status_code = 404


class ItemCodeAlreadyExistsException(ApplicationException):

    code = "ITEM_CODE_ALREADY_EXISTS"
    message = "Item code already exists."
    status_code = 409


class InvalidItemException(ApplicationException):

    code = "INVALID_ITEM"
    message = "Invalid item configuration."
    status_code = 400