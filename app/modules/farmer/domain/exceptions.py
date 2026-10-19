from app.core.exceptions.base import ApplicationException


class FarmerNotFoundException(ApplicationException):

    code = "FARMER_NOT_FOUND"
    message = "Farmer not found."
    status_code = 404


class FarmerAlreadyExistsException(ApplicationException):

    code = "FARMER_ALREADY_EXISTS"
    message = "Farmer code or user already exists."
    status_code = 409


class InvalidFarmerException(ApplicationException):

    code = "INVALID_FARMER"
    message = "Invalid farmer."
    status_code = 400


class FarmerCodeAlreadyExistsException(ApplicationException):

    code = "FARMER_CODE_ALREADY_EXISTS"
    message = "Farmer code already exists."
    status_code = 409