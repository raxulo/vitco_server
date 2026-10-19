from fastapi.responses import RedirectResponse
from app.web.framework.reponses import Responses
from app.web.framework.htmx import HTMXBuilder

from typing import Any

from fastapi import Request
from starlette.responses import Response

from app.web.framework.context_builder import ContextBuilder


class Renderer:
    """
    Enterprise Renderer

    page()      -> Full HTML Page
    partial()   -> HTMX Partial
    redirect()  -> RedirectResponse
    json()      -> JSONResponse
    empty()     -> Empty ResponseBuilder
    """
    @staticmethod
    def page(
        *,
        request: Request,
        template: str,
        model: Any | None = None,
        status_code: int = 200,
    ) -> Response:

        return request.app.state.templates.TemplateResponse(
            request=request,
            name=template,
            context=ContextBuilder.build(
                request=request,
                model=model,
            ),
            status_code=status_code,
        )

    @staticmethod
    def partial(
        *,
        request: Request,
        template: str,
        model: Any | None = None,
        status_code: int = 200,
    ) -> HTMXBuilder:

        response = request.app.state.templates.TemplateResponse(
            request=request,
            name=template,
            context=ContextBuilder.build(
                request=request,
                model=model,
            ),
            status_code=status_code,
        )

        return HTMXBuilder(response)

    @staticmethod
    def redirect(
        url: str,
        status_code: int = 302,
    )-> RedirectResponse:

        return Responses.redirect(
            url=url,
            status_code=status_code,
        )

    @staticmethod
    def htmx_redirect(
        url: str,
        status_code: int = 302,
    )-> Response:

        return Responses.htmx_redirect(
            url=url,
        )

    @staticmethod
    def json(
        data: Any,
        status_code: int = 200,
    ):

        return Responses.json(
            data=data,
            status_code=status_code,
        )

    @staticmethod
    def empty(
        status_code: int = 200,
    ) -> HTMXBuilder:

        return HTMXBuilder(
            Responses.empty(
                status_code=status_code
            )
        )