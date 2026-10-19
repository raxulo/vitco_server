from app.core.exceptions.base import ApplicationException

class InvalidCredentials(ApplicationException):
    code = "AUTH_INVALID_CREDENTIALS"
    message = "Invalid email or password."
    status_code = 401


class EmailNotVerified(ApplicationException):
    code = "AUTH_EMAIL_NOT_VERIFIED"
    message = "Email is not verified."
    status_code = 403


class AccountDisabled(ApplicationException):
    code = "AUTH_ACCOUNT_DISABLED"
    message = "Account has been disabled."
    status_code = 403


class InvalidToken(ApplicationException):
    code = "AUTH_INVALID_TOKEN"
    message = "Invalid token."
    status_code = 401


class TokenExpired(ApplicationException):
    code = "AUTH_TOKEN_EXPIRED"
    message = "Token expired."
    status_code = 401