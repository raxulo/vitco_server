"""
RealTimeTransfer
================

Application Exception Handlers

Python 3.13+
"""
from app.core.exceptions.base import ForbiddenException
from fastapi.responses import HTMLResponse
from fastapi.encoders import jsonable_encoder
from app.core.exceptions.base import ValidateError

from pydantic import ValidationError
from sqlalchemy.exc import IntegrityError
from app.web.framework.renderer import Renderer
from app.web.framework.helpers import WebHelper

from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.core.exceptions.base import ApplicationException

async def application_exception_handler(request, exc: ApplicationException):


    # REST API
    if WebHelper.is_api(request):
        return Renderer.json(
            {
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                "details": exc.details,
            },
        },
            status_code=exc.status_code,
        )

    # HTMX Request
    if WebHelper.is_web(request):
        return (
            Renderer
            .empty(status_code=exc.status_code)
            .error(exc.message)
            .build()
        )

    # Normal Browser Request
    return Renderer.page(
        request=request,
        template="pages/errors/error.html",
        model={"message": exc.message},
        status_code=exc.status_code,
    )

async def http_exception_handler(request, exc: HTTPException):
    if WebHelper.is_api(request):
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "success": False,
                "error": {
                    "code": "HTTP_ERROR",
                    "message": str(exc),
                    "details": {},
                },
            },
        )
    if exc.status_code == 404:

        return Renderer.page(
            request=request,
            template="pages/errors/404.html",
            status_code=404,
        )

    if exc.status_code == 403:

        return Renderer.page(
            request=request,
            template="pages/errors/403.html",
            model={"message": exc.detail},
            status_code=403,
        )

    return Renderer.page(
        request=request,
        template="pages/errors/error.html",
        model={"message": exc.detail if hasattr(exc, "detail") else str(exc)},
        status_code=exc.status_code,
    )

async def forbidden_exception_handler(request, exc: ForbiddenException):

    # API / HTMX form submits: JSON so the popup can show the reason
    if WebHelper.is_api(request) or WebHelper.is_htmx(request):
        return _error_json(403, "FORBIDDEN", exc.message)

    return Renderer.page(
        request=request,
        template="pages/errors/403.html",
        model={
            "message": exc.message,
        },
        status_code=403,
    )


def _readable_validation_message(error: dict) -> str:
    """
    One clear sentence for the popup:
    - our own rules (ValueError in a validator) are shown as written,
    - pydantic's built-in checks are prefixed with the field label.
    """
    message = str(error.get("msg") or "Invalid value")
    for prefix in ("Value error, ", "Assertion failed, "):
        if message.startswith(prefix):
            return message[len(prefix):]

    loc = [part for part in error.get("loc", ()) if isinstance(part, str) and part not in ("body", "query")]
    if not loc:
        return message
    label = loc[-1].replace("_", " ").capitalize()
    return f"{label}: {message}"


async def validation_exception_handler(request, exc: ValidationError):
    errors = []
    for error in exc.errors():
        loc = error.get("loc", ())
        field = str(loc[-1]) if loc else "field"

        errors.append({
            "field": field,
            "message": _readable_validation_message(error),
            "type": error.get("type"),
        })
    message = errors[0]["message"] if errors else "Please enter correct input field."


    return JSONResponse(
        status_code=422,
        content=jsonable_encoder({
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": message ,
                "details": exc.errors(),
            },
        }),
    )


def _error_json(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "success": False,
            "error": {
                "code": code,
                "message": message,
                "details": {},
            },
        },
    )


async def permission_error_handler(request, exc: PermissionError):
    """Role / permission refusals (e.g. "VLCC creation is not allowed") reach the user's popup."""
    message = str(exc) or "You do not have permission to do this."
    if WebHelper.is_api(request) or WebHelper.is_htmx(request):
        return _error_json(403, "FORBIDDEN", message)
    return Renderer.page(
        request=request,
        template="pages/errors/403.html",
        model={"message": message},
        status_code=403,
    )


async def value_error_handler(request, exc: ValueError):
    """Business rules raised as ValueError (e.g. "Please enter the VLCC code") reach the user as-is."""
    return _error_json(400, "INVALID_INPUT", str(exc) or "Invalid input.")


_UNIQUE_FIELD_MESSAGES = {
    "users.email": "Email already exists.",
    "users.mobile": "Mobile number is already registered.",
}


async def integrity_error_handler(request, exc: IntegrityError):
    """Database safety net: a duplicate that slipped past the checks still gets a clear message."""
    detail = str(getattr(exc, "orig", exc))
    for column, message in _UNIQUE_FIELD_MESSAGES.items():
        if column in detail:
            return _error_json(409, "ALREADY_EXISTS", message)
    if "UNIQUE" in detail.upper():
        return _error_json(409, "ALREADY_EXISTS", "This record already exists.")
    return _error_json(400, "INTEGRITY_ERROR", "The data could not be saved. Please check the values and try again.")


async def unhandled_exception_handler(request, exc: Exception):

    return JSONResponse(
        status_code=500,
        content={
            "success": False,
            "error": {
                "code": "INTERNAL_SERVER_ERROR",
                "message": "An unexpected error occurred processing your request.",   
                "details": str(exc),
            },
        },
    )


async def validate_error_handler(
    request,
    exc: ValidateError,
):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": "VALIDATION_ERROR",
                "message": exc.message,
            },
        },
    )