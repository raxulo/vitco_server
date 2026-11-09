"""
RealTimeTransfer
================

Web Bootstrap

Python 3.13+
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.responses import Response
from starlette.templating import Jinja2Templates
from starlette.types import Scope


class CachedStaticFiles(StaticFiles):
    """
    Static files with explicit browser caching.

    vendor/<name>/<version>/... never changes in place (a new version is a new
    folder), so it is cached for a year without revalidation. Our own CSS / JS
    change between deploys, so the browser revalidates them (ETag -> 304).
    """

    _VENDOR_CACHE = "public, max-age=31536000, immutable"
    _APP_CACHE = "no-cache"

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        if response.status_code in (200, 304):
            is_vendor = path.replace("\\", "/").startswith("vendor/")
            response.headers["Cache-Control"] = (
                self._VENDOR_CACHE if is_vendor else self._APP_CACHE
            )
        return response


class WebMount:

    __slots__ = ()

    _templates: Jinja2Templates | None = None

    @classmethod
    def initialize(
        cls,
        app: FastAPI,
    ) -> None:
        """
        Initialize web engine.
        """

        base = Path(__file__).resolve().parent

        # -------------------------
        # Static Files
        # -------------------------

        app.mount("/static", CachedStaticFiles(directory=base / "static"), name="static")

        # -------------------------
        # Templates
        # -------------------------

        cls._templates = Jinja2Templates(directory=str(base / "templates"))
        

        # cls._register_globals()

        cls._register_filters()

    # ---------------------------------------------------------

    @classmethod
    def templates(
        cls,
    ) -> Jinja2Templates:

        if cls._templates is None:
            raise RuntimeError(
                "WebMount.initialize() not called."
            )

        return cls._templates

    # ---------------------------------------------------------

    @classmethod
    def _register_globals(
        cls,
    ) -> None:

        env = cls.templates.env

        env.globals.update(

            app_name="RealTimeTransfer",

            app_version="1.0.0",

        )

    # ---------------------------------------------------------

    @classmethod
    def _register_filters(
        cls,
    ) -> None:
        from app.web.framework.renderer import Renderer
        env = cls.templates().env
        env.filters["chart_type_name"] = lambda x: {0: "Formula", 1: "CSV", 2: "Prodata", 3: "Text"}.get(int(x), "Formula")
        env.filters["status_name"] = lambda x: {0: "Inactive", 1: "Active", 2: "Archived"}.get(int(x), "Inactive")
        env.filters["milk_type_name"] = lambda x: {0: "Cow", 1: "Buffalo", 2: "Mixed"}.get(int(x) if x is not None else 2, "Mixed")
        # Decimal display that truncates instead of rounding: {{ v|fixed }} / {{ v|fixed(3) }}
        from app.core.numeric import fixed
        env.filters["fixed"] = fixed
        from app.web.framework.formatting import age_label, inr, quantity
        env.filters["inr"] = inr
        env.filters["quantity"] = quantity
        env.filters["age_label"] = age_label
        from app.web.storefront.cart_cookie import cart_count
        env.filters["cart_count"] = cart_count
        from app.web.storefront.seo import store_url
        env.globals["store_url"] = store_url