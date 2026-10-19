from app.core.exceptions.base import ApplicationException


class AdvanceNotFoundException(ApplicationException):

    code = "ADVANCE_NOT_FOUND"
    message = "Advance not found."
    status_code = 404


class AdvanceNumberAlreadyExistsException(ApplicationException):

    code = "ADVANCE_NUMBER_ALREADY_EXISTS"
    message = "Advance number already exists."
    status_code = 409


class InvalidAdvanceException(ApplicationException):

    code = "INVALID_ADVANCE"
    message = "Invalid advance configuration."
    status_code = 400