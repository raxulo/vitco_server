"""
RealTimeTransfer
================

Enterprise Logging Middleware

Heavy Traffic Ready

Python 3.13+
"""

from __future__ import annotations

import time
import uuid

from starlette.middleware.base import (
    BaseHTTPMiddleware,
)

from starlette.requests import Request
from starlette.responses import Response

from app.core.logging.context import LoggingContext
from app.core.logging.factory import LoggerFactory


class LoggingMiddleware(
    BaseHTTPMiddleware,
):

    __slots__ = (
        "_logger",
    )

    def __init__(
        self,
        app,
    ) -> None:

        super().__init__(app)

        self._logger = LoggerFactory.get(
            "HTTP"
        )

    async def dispatch(
        self,
        request: Request,
        call_next,
    ) -> Response:

        started = time.perf_counter()

        token = LoggingContext.create(

            request_id=uuid.uuid4().hex,

            trace_id=request.headers.get(
                "X-Trace-Id"
            ),

            correlation_id=request.headers.get(
                "X-Correlation-Id"
            ),

            ip=(
                request.client.host
                if request.client
                else None
            ),
        )

        try:

            response = await call_next(
                request
            )

            duration = round(

                (
                    time.perf_counter()
                    - started
                )
                * 1000,

                2,
            )

            self._logger.info(

                "HTTP Request",

                method=request.method,

                path=request.url.path,

                status=response.status_code,

                duration_ms=duration,
            )

            response.headers[
                "X-Request-ID"
            ] = LoggingContext.current().request_id

            return response

        except Exception as ex:

            duration = round(

                (
                    time.perf_counter()
                    - started
                )
                * 1000,

                2,
            )

            self._logger.exception(

                "Unhandled Exception",

                method=request.method,

                path=request.url.path,

                duration_ms=duration,
            )

            raise

        finally:

            LoggingContext.reset(
                token
            )