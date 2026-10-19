from app.core.exceptions.base import ApplicationException


class VlccNotFoundException(ApplicationException):

    code = "VLCC_NOT_FOUND"
    message = "VLCC not found."
    status_code = 404


class VlccAlreadyExistsException(ApplicationException):

    code = "VLCC_ALREADY_EXISTS"
    message = "VLCC code or user already exists."
    status_code = 409


class InvalidVlccException(ApplicationException):

    code = "INVALID_VLCC"
    message = "Invalid VLCC."
    status_code = 400


class VlccCodeAlreadyExistsException(ApplicationException):

    code = "VLCC_CODE_ALREADY_EXISTS"
    message = "VLCC code already exists."
    status_code = 409

class VlccConfigurationNotFoundException(ApplicationException):

    code = "VLCC_CONFIGURATION_NOT_FOUND"
    message = "VLCC configuration not found."
    status_code = 404

class VlccConfigurationAlreadyExistsException(ApplicationException):

    code = "VLCC_CONFIGURATION_ALREADY_EXISTS"
    message = "VLCC configuration already exists."
    status_code = 409

class InvalidVlccConfigurationException(ApplicationException):

    code = "INVALID_VLCC_CONFIGURATION"
    message = "Invalid VLCC configuration."
    status_code = 400
