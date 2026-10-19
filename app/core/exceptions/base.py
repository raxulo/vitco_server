from typing import Any


class ForbiddenException(Exception):
    status_code = 403

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)


class ApplicationException(Exception):
    """
    Base Exception
    Domain/Application should inherit from this.
    No HTTP dependency.
    """

    code: str = "APPLICATION_ERROR"
    message: str = "Application Error"
    status_code: int = 500

    def __init__(
        self,
        message: str | None = None,
        *,
        details: dict[str, Any] | None = None,
    ) -> None:

        self.code = self.code
        self.status_code = self.status_code
        self.message = message or self.message
        self.details = details or {}

        super().__init__(self.message)



class ValidateError(Exception):
    status_code = 422

    def __init__(self, message: str):
        self.message = message
        super().__init__(message)