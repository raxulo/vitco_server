"""
Self Brand Middleware (Python 3.13+).

Puts the Self Brand of the signed-in web user on `request.state.brand` (logo URL
and the Admin's name, issue #41), so the sidebar and the tab icon can show the
Admin's logo and name without each page controller looking it up.

Registered innermost: it needs `request.state.user` (AuthenticationMiddleware)
and the request's DB session (DatabaseMiddleware). API, static and media
requests are skipped, as are visitors; templates then show the Vitco logo.
"""

import logging

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

_SKIP_PREFIXES = ("/api/", "/static/", "/marketplace", "/favicon.ico", "/robots.txt", "/sitemap.xml", "/healthz")

_log = logging.getLogger(__name__)


class BrandMiddleware(BaseHTTPMiddleware):

    async def dispatch(self, request: Request, call_next):
        user = getattr(request.state, "user", None)
        if user is not None and request.method == "GET" and not request.url.path.startswith(_SKIP_PREFIXES):
            try:
                from app.modules.dependencies import GetHandler

                request.state.brand = await GetHandler.profile_service(request).brand_of(user)
            except Exception:  # noqa: BLE001 - a brand lookup must never break a page
                _log.warning("BrandMiddleware: brand lookup failed", exc_info=True)
        return await call_next(request)
