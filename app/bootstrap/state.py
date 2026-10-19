"""
RealTimeTransfer
================

Application Runtime State

Holds application-wide runtime state.

Python 3.13+
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.core.container.container import ServiceContainer


# =====================================================================
# Application Status
# =====================================================================


class ApplicationStatus(StrEnum):
    """
    Application lifecycle status.
    """

    CREATED = "created"
    STARTING = "starting"
    RUNNING = "running"
    STOPPING = "stopping"
    STOPPED = "stopped"


# =====================================================================
# Application State
# =====================================================================


@dataclass
class ApplicationState:
    """
    Global runtime state.

    This object exists for the entire lifetime of the application.

    It should NEVER contain:

        - Request data
        - Business data
        - User sessions
        - Repository instances

    It SHOULD contain:

        - Runtime status
        - DI Container
        - Startup time
        - Runtime metadata
    """

    # ----------------------------------------------------------
    # Runtime
    # ----------------------------------------------------------

    status: ApplicationStatus = ApplicationStatus.CREATED

    started_at: float = field(
        default_factory=time.monotonic,
    )

    # ----------------------------------------------------------
    # Infrastructure
    # ----------------------------------------------------------

    container: ServiceContainer = field(
        default_factory=ServiceContainer,
    )

    # ----------------------------------------------------------
    # Runtime Metadata
    # ----------------------------------------------------------

    metadata: dict[str, Any] = field(
        default_factory=dict,
    )

    
    # ==========================================================
    # Status
    # ==========================================================

    def set_status(
        self,
        status: ApplicationStatus,
    ) -> None:

        self.status = status

    # ==========================================================
    # Metadata
    # ==========================================================

    def set(
        self,
        key: str,
        value: Any,
    ) -> None:

        self.metadata[key] = value

    # ----------------------------------------------------------

    def get(
        self,
        key: str,
        default: Any = None,
    ) -> Any:

        return self.metadata.get(
            key,
            default,
        )

    # ----------------------------------------------------------

    def remove(
        self,
        key: str,
    ) -> None:

        self.metadata.pop(
            key,
            None,
        )

    # ----------------------------------------------------------

    def clear(self) -> None:

        self.metadata.clear()

    # ==========================================================
    # Runtime Properties
    # ==========================================================

    @property
    def uptime(self) -> float:
        """
        Returns application uptime in seconds.
        """

        return time.monotonic() - self.started_at

    # ----------------------------------------------------------

    @property
    def is_running(self) -> bool:

        return self.status is ApplicationStatus.RUNNING

    # ----------------------------------------------------------

    @property
    def is_starting(self) -> bool:

        return self.status is ApplicationStatus.STARTING

    # ----------------------------------------------------------

    @property
    def is_stopping(self) -> bool:

        return self.status is ApplicationStatus.STOPPING

    # ----------------------------------------------------------

    @property
    def is_stopped(self) -> bool:

        return self.status is ApplicationStatus.STOPPED