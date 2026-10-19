from app.core.exceptions.base import ApplicationException

class DeviceItemVersionNotFoundError(ApplicationException):
    code = "DEVICE_ITEM_VERSION_NOT_FOUND"
    message = "Device item version not found."
    status_code = 404
