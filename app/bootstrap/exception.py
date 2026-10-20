# """
# RealTimeTransfer
# ================

# Bootstrap Module: Exception Handling Setup

# Registers global exception mapping, validation captures, and error handlers.

# Python 3.13+
# """

# from __future__ import annotations

# import time
# from fastapi import FastAPI
# from fastapi.exceptions import RequestValidationError
# from fastapi.responses import JSONResponse
# from starlette.exceptions import HTTPException as StarletteHTTPException


# def register_exception_handlers(app: FastAPI) -> None:
#     """
#     Register global request validation and custom database error handlers.
#     """
    
#     @app.exception_handler(RequestValidationError)
#     async def validation_exception_handler(request, exc: RequestValidationError):
#         return JSONResponse(
#             status_code=422,
#             content={
#                 "error": "VAL_ERROR",
#                 "message": "Input validation failed.",
#                 "timestamp": int(time.time()),
#                 "details": exc.errors()
#             }
#         )

#     @app.exception_handler(StarletteHTTPException)
#     async def http_exception_handler(request, exc: StarletteHTTPException):
#         return JSONResponse(
#             status_code=exc.status_code,
#             content={
#                 "error": "HTTP_ERROR",
#                 "message": exc.detail,
#                 "timestamp": int(time.time())
#             }
#         )

#     @app.exception_handler(Exception)
#     async def global_exception_handler(request, exc: Exception):
#         # Fallback error wrapper for unhandled exceptions
#         return JSONResponse(
#             status_code=500,
#             content={
#                 "error": "INTERNAL_SERVER_ERROR",
#                 "message": "An unexpected error occurred processing your request.",
#                 "timestamp": int(time.time()),
#                 "details": str(exc)
#             }
#         )


"""
RealTimeTransfer
================

Exception Registration

Python 3.13+
"""
from app.core.exceptions.handlers import forbidden_exception_handler
from app.core.exceptions.base import ForbiddenException
from app.core.exceptions.handlers import validate_error_handler
from app.core.exceptions.base import ValidateError

from pydantic import ValidationError

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException

from app.core.exceptions.base import ApplicationException
from sqlalchemy.exc import IntegrityError

from app.core.exceptions.handlers import (
    application_exception_handler,
    http_exception_handler,
    integrity_error_handler,
    permission_error_handler,
    validation_exception_handler,
    unhandled_exception_handler,
    value_error_handler,
)


class ExceptionRegistrar:
    """
    Registers global exception handlers.
    """

    __slots__ = ()

    @classmethod
    def register(
        cls,
        app: FastAPI,
    ) -> None:

        app.add_exception_handler(
            HTTPException,
            http_exception_handler,
        )

        app.add_exception_handler(
            ValidateError,
            validate_error_handler,
        )

        app.add_exception_handler(
            ValidationError,
            validation_exception_handler,
        )

        app.add_exception_handler(
            ApplicationException,
            application_exception_handler,
        )

        app.add_exception_handler(
            PermissionError,
            permission_error_handler,
        )

        app.add_exception_handler(
            ValueError,
            value_error_handler,
        )

        app.add_exception_handler(
            IntegrityError,
            integrity_error_handler,
        )

        app.add_exception_handler(
            Exception,
            unhandled_exception_handler,
        )

        app.add_exception_handler(
            ForbiddenException,
            forbidden_exception_handler,
        )