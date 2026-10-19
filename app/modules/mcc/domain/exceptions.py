from app.core.exceptions.base import ApplicationException


class MccNotFoundException(ApplicationException):

    code = "MCC_NOT_FOUND"
    message = "MCC not found."
    status_code = 404


class MccAlreadyExistsException(ApplicationException):

    code = "MCC_ALREADY_EXISTS"
    message = "MCC code already exists."
    status_code = 409


class InvalidMccException(ApplicationException):

    code = "INVALID_MCC"
    message = "Invalid MCC."
    status_code = 400

class MccCodeAlreadyExistsException(ApplicationException):

    code = "MCC_CODE_ALREADY_EXISTS"
    message = "MCC code already exists."
    status_code = 409