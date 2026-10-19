from app.core.exceptions.base import ApplicationException

class MilkQualityConfigNotFoundException(ApplicationException):
    
    code = "MILK_QUALITY_CONFIG_NOT_FOUND"
    message = "Milk quality configuration not found."
    status_code = 404


class MilkQualityConfigAlreadyExistsException(ApplicationException):
    
    code = "MILK_QUALITY_CONFIG_ALREADY_EXISTS"
    message = "Milk quality configuration already exists."
    status_code = 400


class InvalidMilkQualityConfigException(ApplicationException):

    code = "INVALID_MILK_QUALITY_CONFIG"
    message = "Invalid milk quality configuration."
    status_code = 400