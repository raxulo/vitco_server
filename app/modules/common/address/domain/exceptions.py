from app.core.exceptions.base import ApplicationException

class AddressNotFoundException(ApplicationException):
    code = "ADDRESS_NOT_FOUND"
    message = "Address not found."
    status_code = 404


class AddressAlreadyExistsException(ApplicationException):
    code = "ADDRESS_ALREADY_EXISTS"
    message = "Address already exists."
    status_code = 400


class InvalidAddressException(ApplicationException):
    code = "INVALID_ADDRESS"
    message = "Invalid address."
    status_code = 400