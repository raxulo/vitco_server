"""
RealTimeTransfer
================

Enterprise Audit Logger

Python 3.13+
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from app.core.logging.factory import LoggerFactory
from app.core.logging.context import LoggingContext


class AuditAction(StrEnum):

    LOGIN = "login"

    LOGOUT = "logout"

    CREATE = "create"

    UPDATE = "update"

    DELETE = "delete"

    DOWNLOAD = "download"

    UPLOAD = "upload"

    OTP_GENERATED = "otp_generated"

    OTP_VERIFIED = "otp_verified"

    PASSWORD_CHANGED = "password_changed"

    PERMISSION_CHANGED = "permission_changed"


@dataclass(slots=True, frozen=True)
class AuditEvent:

    action: AuditAction

    resource: str

    resource_id: str | None = None

    success: bool = True

    details: dict[str, Any] | None = None

    timestamp: str = datetime.now(
        UTC
    ).isoformat()


class AuditLogger:

    __slots__ = (
        "_logger",
    )

    def __init__(self) -> None:

        self._logger = LoggerFactory.get(
            "AUDIT"
        )

    def log(
        self,
        event: AuditEvent,
    ) -> None:

        context = LoggingContext.current()

        payload = asdict(event)

        if context:

            payload.update({

                "request_id": context.request_id,

                "trace_id": context.trace_id,

                "correlation_id": context.correlation_id,

                "user_id": context.user_id,

                "tenant_id": context.tenant_id,

                "ip": context.ip,
            })

        self._logger.info(

            "AUDIT",

            **payload,
        )


audit_logger = AuditLogger()