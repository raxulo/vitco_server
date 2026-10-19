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

    return Renderer.page(
        request=request,
        template="pages/errors/403.html",
        model={
            "message": exc.message,
        },
        status_code=403,
    )


async def validation_exception_handler(request, exc: ValidationError):
    errors = []
    for error in exc.errors():
        loc = error.get("loc", ())
        field = str(loc[-1]) if loc else "field"

        errors.append({
            "field": field,
            "message": error.get("msg", "Invalid value"),
            "type": error.get("type"),
        })
    message = "Validation Error"
    if len(errors) > 0:
        _m = errors[0].get('message')
        message =  f"{errors[0].get("field").replace("_", " ").capitalize()} : {_m}" if _m else "Please enter correct input field."


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