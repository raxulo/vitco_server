from app.core.exceptions.base import ApplicationException


class VlccCollectionNotFoundException(ApplicationException):

    code = "VLCC_COLLECTION_NOT_FOUND"
    message = "VLCC milk collection not found."
    status_code = 404


class VlccCollectionAlreadyExistsException(ApplicationException):

    code = "VLCC_COLLECTION_ALREADY_EXISTS"
    message = "VLCC collection already exists."
    status_code = 409


class InvalidVlccCollectionException(ApplicationException):

    code = "INVALID_VLCC_COLLECTION"
    message = "Invalid VLCC collection data."
    status_code = 400


class VlccCollectionNumberAlreadyExistsException(ApplicationException):

    code = "VLCC_COLLECTION_NUMBER_ALREADY_EXISTS"
    message = "VLCC collection number already exists."
    status_code = 409