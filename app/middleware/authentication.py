"""
Enterprise JWT Authentication Middleware

Python 3.13+
"""
from app.modules.administration.domain.enums import Role
from app.web.framework.renderer import Renderer
from app.web.framework.helpers import WebHelper

import time
from dataclasses import dataclass
from uuid import UUID

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

from app.modules.auth.infrastructure.jwt import JWTService

@dataclass(slots=True, frozen=True)
class CurrentUser:
    id: UUID
    role: str
    own_id: UUID | None = None
    name: str | None = None
    profile_image: str | None = None
    permissions: frozenset[str] | None = None

    @property
    def role_type(self) -> Role:
        if isinstance(self.role, Role):
            return self.role
        try:
            return Role(int(self.role))
        except (ValueError, TypeError):
            try:
                return Role[str(self.role)]
            except (KeyError, TypeError):
                return Role.ADMIN

    @property
    def is_farmer_vlcc(self) -> bool:
        return self.role_type == Role.VLCC_FARMER

class AuthenticationMiddleware(BaseHTTPMiddleware):

    __slots__ = (
        "_jwt",
        "_public_routes",
        "_account_cache",
    )

    # A token only counts while its user still exists, is active and not deleted.
    # The answer is cached briefly so a request costs at most one primary-key read.
    _ACCOUNT_CHECK_TTL = 30.0

    def __init__(
        self,
        app,
        jwt_service: JWTService,
        public_routes: set[str],
    ) -> None:

        super().__init__(app)

        self._jwt = jwt_service
        self._public_routes = public_routes
        self._account_cache: dict[UUID, tuple[bool, float]] = {}

    async def _account_is_valid(self, request: Request, user_id: UUID) -> bool:
        """False for a token whose user was removed, deleted or disabled (e.g. an old login)."""
        now = time.monotonic()
        cached = self._account_cache.get(user_id)
        if cached and cached[1] > now:
            return cached[0]

        from sqlalchemy import select
        from app.modules.administration.infrastructure.models import UserModel

        database = request.app.state.application.container.database
        async with database.transaction() as session:
            row = (
                await session.execute(
                    select(UserModel.is_active, UserModel.is_deleted).where(UserModel.id == user_id)
                )
            ).first()
        valid = row is not None and bool(row.is_active) and not row.is_deleted

        if len(self._account_cache) > 10_000:
            self._account_cache.clear()
        self._account_cache[user_id] = (valid, now + self._ACCOUNT_CHECK_TTL)
        return valid

    async def dispatch(
        self,
        request: Request,
        call_next,
    ):
        if not hasattr(request.state, "user"):
            request.state.user = None

        path = request.url.path

        public_routes_startswith = (
            "/static", "/api/v1/media/", "/api/v1/files/", "/marketplace", "/api/v1/marketplace"
        )

        # -----------------------------------------
        # Try Decoding Token if Present (For both Public & Protected)
        # -----------------------------------------
        authorization = None
        if WebHelper.is_web(request) or path.startswith("/api/v1/excel/"):
            authorization = request.cookies.get('access_token')
            if not authorization:
                authorization = request.headers.get("Authorization")
        else:
            authorization = request.headers.get("Authorization")

        if authorization:
            import urllib.parse
            auth_str = urllib.parse.unquote(authorization).strip('"\'' + " \t\r\n")
            if auth_str.startswith("Bearer "):
                token = auth_str[7:].strip()
            elif auth_str.startswith("Bearer"):
                token = auth_str[6:].strip()
            elif WebHelper.is_web(request) or path.startswith("/api/v1/excel/"):
                token = auth_str
            else:
                token = None

            if token:
                try:
                    payload = self._jwt.decode(token)
                    if payload and "sub" in payload:
                        raw_own_id = payload.get("own_id")
                        own_id = None
                        if raw_own_id:
                            try:
                                own_id = UUID(str(raw_own_id))
                            except (ValueError, TypeError):
                                own_id = None

                        raw_sub = payload["sub"]
                        if raw_sub and await self._account_is_valid(request, UUID(str(raw_sub))):
                            request.state.user = CurrentUser(
                                id=UUID(str(raw_sub)),
                                role=str(payload.get("role", "")),
                                name=payload.get("name"),
                                own_id=own_id,
                                profile_image=payload.get("profile_image", None),
                                permissions=frozenset(payload.get("permissions", [])),
                            )
                except Exception as e:
                    import logging
                    logging.getLogger(__name__).warning("AuthenticationMiddleware: Token decode failed: %s", e)

        # -----------------------------------------
        # Public Routes Check
        # -----------------------------------------
        if path in self._public_routes or path.startswith(public_routes_startswith):
            return await call_next(request)

        # -----------------------------------------
        # Protected Routes Check
        # -----------------------------------------
        if getattr(request.state, "user", None) is None:
            if WebHelper.is_web(request):
                return Renderer.redirect(url="/login")
            else:
                from fastapi.responses import JSONResponse
                return JSONResponse(
                    status_code=401,
                    content={
                        "success": False,
                        "error": {
                            "code": "AUTH_UNAUTHORIZED",
                            "message": "Unauthorized.",
                            "details": {},
                        },
                    },
                )

        return await call_next(request)



"""
Enterprise Authentication Middleware

Python 3.13+
"""

# from __future__ import annotations

# from collections.abc import Awaitable, Callable

# from fastapi import Request
# from fastapi.responses import JSONResponse, RedirectResponse
# from starlette.middleware.base import BaseHTTPMiddleware
# from starlette.responses import Response

# from app.core.auth.authentication import (
#     AuthenticationService,
# )

# from app.core.auth.models import (
#     RequestContext,
# )


# class AuthenticationMiddleware(
#     BaseHTTPMiddleware
# ):

#     __slots__ = (
#         "_auth",
#         "_public_paths",
#     )


#     def __init__(
#         self,
#         app,
#         auth_service: AuthenticationService,
#     ):

#         super().__init__(app)

#         self._auth = auth_service


#         self._public_paths = {

#             "/",

#             "/login",

#             "/auth/login",

#             "/forgot-password",

#             "/reset-password",

#             "/docs",

#             "/openapi.json",

#         }


#     async def dispatch(
#         self,
#         request: Request,
#         call_next: Callable[
#             [Request],
#             Awaitable[Response]
#         ],
#     ) -> Response:


#         path = request.url.path


#         # -------------------------------
#         # Public Routes
#         # -------------------------------

#         if path in self._public_paths:

#             request.state.context = (
#                 RequestContext()
#             )

#             return await call_next(
#                 request
#             )


#         # -------------------------------
#         # Read Cookie
#         # -------------------------------

#         token = request.cookies.get(
#             "access_token"
#         )


#         # -------------------------------
#         # Authenticate
#         # -------------------------------

#         context = await self._auth.authenticate(
#             token
#         )


#         request.state.context = context


#         # -------------------------------
#         # Protected Check
#         # -------------------------------

#         if not context.authenticated:


#             if path.startswith("/api"):

#                 return JSONResponse(

#                     status_code=401,

#                     content={

#                         "error":
#                         "unauthorized",

#                         "message":
#                         "Authentication required",

#                     },

#                 )


#             return RedirectResponse(

#                 url="/login",

#                 status_code=302,

#             )


#         return await call_next(
#             request
#         )