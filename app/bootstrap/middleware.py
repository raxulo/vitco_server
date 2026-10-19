"""
RealTimeTransfer
================

Middleware Registration Composition Root

Python 3.13+
"""

from app.config.settings import settings
from app.modules.auth.infrastructure.jwt import JWTService
from app.middleware.authentication import AuthenticationMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from fastapi import FastAPI
from starlette.middleware.cors import CORSMiddleware
from starlette.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.request_id import RequestIdMiddleware

class DatabaseMiddleware(BaseHTTPMiddleware):

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):

        async with request.app.state.application.container.database.transaction():

            response = await call_next(request)

            return response
            
class MiddlewareRegistrar:
    """
    Registers application middleware.
    """

    __slots__ = ()

    @classmethod
    def register(
        cls,
        app: FastAPI,
    ) -> None:
        # Register Database Session context first
        cls._database_session(app)
        cls._trusted_hosts(app)
        cls._auth(app)
        cls._cors(app)
        cls._gzip(app)
        cls._request_id(app)
        cls._logging(app)

    # ---------------------------------------------------------

    @staticmethod
    def _database_session(
        app: FastAPI,
    ) -> None:
        app.add_middleware(DatabaseMiddleware)

    # ---------------------------------------------------------

    @staticmethod
    def _trusted_hosts(
        app: FastAPI,
    ) -> None:
        app.add_middleware(
            TrustedHostMiddleware,
            allowed_hosts=["*"],
        )

    # ---------------------------------------------------------

    @staticmethod
    def _cors(
        app: FastAPI,
    ) -> None:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )

    # ---------------------------------------------------------

    @staticmethod
    def _gzip(
        app: FastAPI,
    ) -> None:
        app.add_middleware(GZipMiddleware, minimum_size=1024)

    # ---------------------------------------------------------

    @staticmethod
    def _request_id(
        app: FastAPI,
    ) -> None:
        app.add_middleware(RequestIdMiddleware)

    # ---------------------------------------------------------

    @staticmethod
    def _logging(
        app: FastAPI,
    ) -> None:
        app.add_middleware(LoggingMiddleware)

    @staticmethod
    def _auth(app:FastAPI):
        jwt = JWTService(
            secret_key=settings.SECRET_KEY,
        )

        app.add_middleware(
            AuthenticationMiddleware,
            jwt_service=jwt,
            public_routes={
                "/",
                "/marketplace",
                "/marketplace/",
                "/api/v1/marketplace",
                "/api/v1/marketplace/",
                "/healthz",
                "/docs",
                "/redoc",
                "/openapi.json",
                "/api/v1/auth/login",
                "/login", "/auth/login"
            },
        )