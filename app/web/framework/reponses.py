from __future__ import annotations

from typing import Any

from starlette.responses import (
    HTMLResponse,
    JSONResponse,
    RedirectResponse,
    Response,
)


class Responses:

    @staticmethod
    def html(
        html: str,
        status_code: int = 200,
    ) -> HTMLResponse:

        return HTMLResponse(
            content=html,
            status_code=status_code,
        )

    @staticmethod
    def json(
        data: Any,
        status_code: int = 200,
    ) -> JSONResponse:

        return JSONResponse(
            content=data,
            status_code=status_code,
        )

    @staticmethod
    def redirect(
        url: str,
        status_code: int = 303,
    ) -> RedirectResponse:

        res = RedirectResponse(
            url=url,
            status_code=303,
        )
        res.headers["HX-Redirect"] = url
        return res

    @staticmethod
    def htmx_redirect(
        url: str,
    ) -> Response:

        res = Response(
            content=None,
            status_code=200,
        )
        res.headers["HX-Redirect"] = url
        return res

    @staticmethod
    def empty(
        status_code: int = 200,
    ) -> Response:

        return Response(
            status_code=status_code,
        )

    @staticmethod
    def no_content() -> Response:

        return Response(
            status_code=204,
        )