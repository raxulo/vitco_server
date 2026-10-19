from app.core.exceptions.base import ApplicationException


class MccCollectionNotFoundException(ApplicationException):

    code = "MCC_COLLECTION_NOT_FOUND"
    message = "MCC milk collection not found."
    status_code = 404


class MccCollectionAlreadyExistsException(ApplicationException):

    code = "MCC_COLLECTION_ALREADY_EXISTS"
    message = "MCC collection already exists."
    status_code = 409


class InvalidMccCollectionException(ApplicationException):

    code = "INVALID_MCC_COLLECTION"
    message = "Invalid MCC collection data."
    status_code = 400


class MccCollectionNumberAlreadyExistsException(ApplicationException):

    code = "MCC_COLLECTION_NUMBER_ALREADY_EXISTS"
    message = "MCC collection number already exists."
    status_code = 409