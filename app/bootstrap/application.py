"""
RealTimeTransfer
================

Application Factory

Creates and configures the FastAPI application.

Python : 3.13
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.core.config import config


class ApplicationFactory:
    """
    Enterprise FastAPI Application Factory.

    Responsibilities
    ----------------
    • Create FastAPI instance
    • Configure OpenAPI
    • Configure JSON serialization
    • Configure Documentation
    • Prepare application metadata

    NOTE:
    Middleware, Routers, Lifespan and DI are registered
    outside this class to keep responsibilities separated.
    """

    @staticmethod
    def create() -> FastAPI:

        app = FastAPI(
            title=config.settings.APP_NAME,
            version=config.settings.APP_VERSION,
            debug=config.settings.DEBUG,
            default_response_class=ORJSONResponse,
            docs_url="/docs",
            redoc_url="/redoc",
            openapi_url="/openapi.json",
        )

        return app


def create_application() -> FastAPI:
    """
    Application entry point.

    Returns
    -------
    FastAPI
        Configured FastAPI application.
    """
    return ApplicationFactory.create()