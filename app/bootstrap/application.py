# """
# RealTimeTransfer
# ================

# Bootstrap Module: Application Entrypoint

# Triggers the AppBuilder pipeline.

# Python 3.13+
# """

# from __future__ import annotations

# from fastapi import FastAPI
# from app.bootstrap.builder import AppBuilder


# def create_application() -> FastAPI:
#     """
#     Application entry point resolving sequential Fluent Builder stages.
#     """
#     return (
#         AppBuilder()
#         .setup_openapi()
#         .discover_services()
#         .setup_middleware()
#         .setup_routers()
#         .setup_exceptions()
#         .setup_health()
#         .build()
#     )


"""
RealTimeTransfer
================

Application Factory

Public application entry point.

Python 3.13+
"""

from __future__ import annotations

from fastapi import FastAPI

from app.bootstrap.builder import ApplicationBuilder


__all__ = (
    "create_application",
)


def create_application() -> FastAPI:
    """
    Create and configure the FastAPI application.

    This is the only public bootstrap API.
    """

    return ApplicationBuilder().build()