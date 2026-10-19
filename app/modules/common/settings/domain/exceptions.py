"""
Settings Application Exceptions
"""


from app.core.exceptions.base import ApplicationException


class SettingsNotFoundError(ApplicationException):
    code = "SETTINGS_NOT_FOUND"
    message = "Settings not found."
    status_code = 404


class SettingsAlreadyExistsError(ApplicationException):
    code = "SETTINGS_ALREADY_EXISTS"
    message = "Settings already exists."
    status_code = 400