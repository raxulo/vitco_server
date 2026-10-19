"""
RealTimeTransfer
================

Application Builder

Composition Root

Python 3.13+
"""

from app.modules.admin.application.handler import AdminHandler
from app.web.mount import WebMount
from fastapi import FastAPI

from app.bootstrap.state import ApplicationState
from app.bootstrap.router import RouterRegistrar
from app.bootstrap.middleware import MiddlewareRegistrar
from app.bootstrap.exception import ExceptionRegistrar
from app.bootstrap.openapi import OpenAPIConfigurator
from app.bootstrap.lifespan import lifespan
from app.config.settings import settings


class ApplicationBuilder:
    """
    Builds and configures the FastAPI application.

    This is the application's Composition Root.
    """

    __slots__ = (
        "_app",
        "_state",
    )

    def __init__(self) -> None:
        # Hide documentation in production for security and performance
        docs_url = "/docs" if settings.DEBUG else None
        redoc_url = "/redoc" if settings.DEBUG else None
        openapi_url = "/openapi.json" if settings.DEBUG else None

        self._app = FastAPI(
            docs_url=docs_url,
            redoc_url=redoc_url,
            openapi_url=openapi_url,
        )

        self._state = ApplicationState()

    # ---------------------------------------------------------

    def build(self) -> FastAPI:

        self._register_state()
        self._configure_lifespan()
        self._configure_infrastructure()
        self._configure_modules()
        self._web_configurator()
        self._configure_middlewares()
        self._configure_exception_handlers()
        self._configure_routes()
        self._configure_health()
        self._configure_openapi()
        self._freeze_container()
        return self._app

    # =========================================================
    # Internal
    # =========================================================


    async def _create_super_admin(self):
        seeder = self._state.container.resolve(AdminHandler)
        await seeder.create_super_admin()
        
    def _register_state(self) -> None:

        self._app.state.application  = self._state

    # ---------------------------------------------------------

    def _freeze_container(self) -> None:
        self._state.container.freeze()

    # ---------------------------------------------------------

    def _configure_lifespan(self) -> None:

        self._app.router.lifespan_context = lifespan

    # ---------------------------------------------------------

    def _configure_openapi(self) -> None:
        # Only configure OpenAPI if openapi_url is enabled
        if self._app.openapi_url:
            OpenAPIConfigurator.configure(self._app)

    # ---------------------------------------------------------

    def _configure_middlewares(self) -> None:
        MiddlewareRegistrar.register(self._app)

    # ---------------------------------------------------------

    def _configure_exception_handlers(self) -> None:
        ExceptionRegistrar.register(self._app)

    # ---------------------------------------------------------

    def _configure_routes(self) -> None:
        RouterRegistrar.register(self._app)

    # ---------------------------------------------------------

    def _configure_health(self) -> None:
        from app.bootstrap.health import register_health_endpoints
        register_health_endpoints(self._app)

    # ---------------------------------------------------------

    def _configure_infrastructure(self) -> None:
        from app.bootstrap.infrastructure import InfrastructureConfigurator
        InfrastructureConfigurator.configure(self._state.container)

    def _configure_modules(self):
        from app.modules.configurator import ModuleConfigurator

        ModuleConfigurator.configure(self._state)

    def _web_configurator(self):
        web = WebMount()
        web.initialize(self._app)
        self._app.state.templates = web.templates()


        