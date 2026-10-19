from fastapi import status
from app.core.exceptions.base import ApplicationException

class UserAlreadyExistsException(ApplicationException):
    code = "USER_ALREADY_EXISTS"
    message = "User already exists."
    status_code = status.HTTP_409_CONFLICT

class UserNotFoundException(ApplicationException):
    code = "USER_NOT_FOUND"
    message = "User not found."
    status_code = status.HTTP_404_NOT_FOUND

class EmailNotFoundException(ApplicationException):
    code = "EMAIL_NOT_FOUND"
    message = "Email not found."
    status_code = status.HTTP_404_NOT_FOUND

class EmailAlreadyExistsException(ApplicationException):
    code = "EMAIL_ALREADY_EXISTS"
    message = "Email already exists."
    status_code = status.HTTP_409_CONFLICT


class EmailOrMobileAlreadyExistsException(ApplicationException):
    code = "EMAIL_OR_MOBILE_ALREADY_EXISTS"
    message = "Email or mobile already exists."
    status_code = status.HTTP_409_CONFLICT


class UnauthorizedException(ApplicationException):
    code = "UNAUTHORIZED"
    message = "Unauthorized."
    status_code = status.HTTP_401_UNAUTHORIZED
    