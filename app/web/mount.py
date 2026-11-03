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
from starlette.templating import Jinja2Templates


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

        app.mount("/static",StaticFiles(directory=base / "static",), name="static",)

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