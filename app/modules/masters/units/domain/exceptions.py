from app.core.exceptions.base import ApplicationException


class UnitNotFoundException(ApplicationException):

    code = "UNIT_NOT_FOUND"
    message = "Unit not found."
    status_code = 404


class UnitAlreadyExistsException(ApplicationException):

    code = "UNIT_ALREADY_EXISTS"
    message = "Unit name already exists."
    status_code = 409


class InvalidUnitException(ApplicationException):

    code = "INVALID_UNIT"
    message = "Invalid unit configuration."
    status_code = 400