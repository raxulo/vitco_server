"""
RealTimeTransfer
================

OpenAPI Configuration

Python 3.13+
"""

from __future__ import annotations

from fastapi import FastAPI

from app.config.settings import settings


class OpenAPIConfigurator:
    """
    Configures OpenAPI metadata.
    """

    __slots__ = ()

    @classmethod
    def configure(
        cls,
        app: FastAPI,
    ) -> None:
        """
        Configure OpenAPI metadata.
        """

        app.title = settings.APP_NAME

        app.description = settings.APP_DESCRIPTION

        app.version = settings.APP_VERSION

        app.openapi_tags = (
            {
                "name": "Authentication",
                "description": "Authentication APIs",
            },
            {
                "name": "Users",
                "description": "User Management",
            },
            {
                "name": "Farmers",
                "description": "Farmer APIs",
            },
            {
                "name": "Health",
                "description": "Health Monitoring",
            },
        )
