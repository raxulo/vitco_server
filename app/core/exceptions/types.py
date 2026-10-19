from app.core.exceptions.base import ApplicationException


class UnauthorizedException(ApplicationException):
    code = "AUTH_UNAUTHORIZED"
    message = "Unauthorized."
    status_code = 401

