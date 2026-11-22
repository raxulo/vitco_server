"""
Router Registration.

Python 3.13+
"""

from __future__ import annotations

from fastapi import FastAPI
from app.api.v1.router import api_v1_router
from app.api.v1.routers.support_ws import router as support_ws_router


class RouterRegistrar:
    """
    Registers all application routers.
    """

    __slots__ = ()

    @classmethod
    def register(cls, app: FastAPI) -> None:
        cls.rest_api_routers(app)
        cls.web_routers(app)

    @classmethod
    def rest_api_routers(cls, app: FastAPI) -> None:
        app.include_router(api_v1_router, prefix="/api/v1")
        app.include_router(support_ws_router)  # /ws/support (staff) and /ws/support/app (requesters)

    @classmethod
    def web_routers(cls, app: FastAPI) -> None:
        from app.web.router import WebRouterRegistrar

        WebRouterRegistrar.register(app)


class ModuleRegistrar:
    """
    Placeholder/Registrar for modular route groups.
    """
    __slots__ = ()