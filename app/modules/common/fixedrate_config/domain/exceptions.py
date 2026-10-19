from app.core.exceptions.base import ApplicationException

class FixedRateConfigNotFoundException(ApplicationException):
    
    code = "FIXED_RATE_CONFIG_NOT_FOUND"
    message = "Fixed rate configuration not found."
    status_code = 404


class FixedRateConfigAlreadyExistsException(ApplicationException):
    
    code = "FIXED_RATE_CONFIG_ALREADY_EXISTS"
    message = "Fixed rate configuration already exists."
    status_code = 400


class InvalidFixedRateConfigException(ApplicationException):

    code = "INVALID_FIXED_RATE_CONFIG"
    message = "Invalid fixed rate configuration."
    status_code = 400