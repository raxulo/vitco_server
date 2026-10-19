"""
RealTimeTransfer
================

High-Performance ASGI Logging Middleware using standard logging

Python 3.13+
"""

from __future__ import annotations
from app.core.logging.context import LogContext

import os
import binascii
import time
import logging
from typing import Any

from app.core.logging.context import LoggerContext

# High-performance startup token and lock-free request counter
_BASE_TOKEN = binascii.hexlify(os.urandom(8)).decode("utf-8")
_COUNTER = 0

logger = logging.getLogger("app")


def generate_request_id() -> str:
    """
    Ultra-fast in-memory unique Request ID generator.
    Avoids system urandom syscalls on every request.
    """
    global _COUNTER
    _COUNTER += 1
    return f"{_BASE_TOKEN}-{_COUNTER}"


class LoggingMiddleware:
    """
    High-performance raw ASGI middleware for request-response logging.
    Avoids Starlette's BaseHTTPMiddleware concurrency/streaming overhead.
    """

    __slots__ = ("app",)

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict[str, Any], receive: Any, send: Any) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        start_time = time.perf_counter()

        # Fast header scanning (prevents dict allocations and key hashing)
        request_id = ""
        trace_id = ""
        for key, val in scope.get("headers", []):
            if key == b"x-request-id":
                request_id = val.decode("utf-8")
            elif key == b"x-trace-id":
                trace_id = val.decode("utf-8")
            if request_id and trace_id:
                break

        if not request_id:
            request_id = generate_request_id()
        if not trace_id:
            trace_id = request_id

        # Get client IP
        client = scope.get("client")
        client_ip = client[0] if client else ""

        # Initialize thread-safe / context-safe logging context
        token = LoggerContext.set(LogContext(request_id=request_id, user_id="-", path=scope["path"]))

        async def send_wrapper(message: dict[str, Any]) -> None:
            if message["type"] == "http.response.start":
                status = message["status"]
                duration = round((time.perf_counter() - start_time) * 1000, 2)

                # Log response details using standard logging
                logger.info(
                    "HTTP %s %s %s in %sms",
                    scope["method"],
                    scope["path"],
                    status,
                    duration,
                    extra={
                        "status_code": status,
                        "duration_ms": duration,
                        "request_id": request_id,
                    }
                )

                # Inject Request ID header into response headers
                res_headers = list(message.get("headers", []))
                res_headers.append((b"x-request-id", request_id.encode("utf-8")))
                message["headers"] = res_headers

            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        except Exception as exc:
            duration = round((time.perf_counter() - start_time) * 1000, 2)
            logger.exception(
                "HTTP %s %s failed in %sms - %s",
                scope["method"],
                scope["path"],
                duration,
                exc,
                extra={
                    "duration_ms": duration,
                }
            )
            raise
        finally:
            LoggerContext.reset(token)