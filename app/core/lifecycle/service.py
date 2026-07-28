"""
RealTimeTransfer
================

Lifecycle Service

Python 3.13+
"""

from __future__ import annotations

from abc import ABC
from abc import abstractmethod
from enum import Enum
from typing import Final


class ServiceState(str, Enum):
    """
    Current lifecycle state.
    """

    CREATED = "created"

    STARTING = "starting"

    RUNNING = "running"

    STOPPING = "stopping"

    STOPPED = "stopped"

    FAILED = "failed"


class LifecycleService(ABC):
    """
    Base class for every infrastructure service.

    Examples
    --------

    Database

    Redis

    MQTT

    Mail

    Scheduler

    Storage

    Metrics
    """

    #
    # Lower value starts first.
    #
    priority: Final[int] = 100

    def __init__(self) -> None:

        self._state = ServiceState.CREATED

    # -----------------------------------------------------
    # Properties
    # -----------------------------------------------------

    @property
    def name(self) -> str:

        return self.__class__.__name__

    @property
    def state(self) -> ServiceState:

        return self._state

    @property
    def running(self) -> bool:

        return self._state is ServiceState.RUNNING

    # -----------------------------------------------------
    # Internal
    # -----------------------------------------------------

    def _set_state(
        self,
        state: ServiceState,
    ) -> None:

        self._state = state

    # -----------------------------------------------------
    # Lifecycle
    # -----------------------------------------------------

    @abstractmethod
    async def start(self) -> None:
        """
        Start service.
        """

    @abstractmethod
    async def stop(self) -> None:
        """
        Stop service.
        """


# """
# RealTimeTransfer
# ================

# Lifecycle Service Interface

# Defines the contract for infrastructure services that
# participate in the application lifecycle.

# Python : 3.13
# """

# from __future__ import annotations

# from abc import ABC, abstractmethod
# from typing import Any


# class LifecycleService(ABC):
#     """
#     Base contract for all lifecycle-aware services.

#     Examples
#     --------
#     - DatabaseManager
#     - RedisManager
#     - StorageManager
#     - QueueManager
#     - WebSocketManager
#     - TransferEngine
#     - NotificationManager
#     """

#     @property
#     @abstractmethod
#     def name(self) -> str:
#         """
#         Unique service name.
#         """
#         raise NotImplementedError

#     @property
#     def priority(self) -> int:
#         """
#         Startup priority.

#         Lower number = starts earlier.
#         Higher number = starts later.

#         Shutdown order is automatically reversed.
#         """
#         return 100

#     @abstractmethod
#     async def start(self) -> None:
#         """
#         Start the service.
#         """
#         raise NotImplementedError

#     @abstractmethod
#     async def stop(self) -> None:
#         """
#         Gracefully stop the service.
#         """
#         raise NotImplementedError

#     async def health(self) -> dict[str, Any]:
#         """
#         Service health information.

#         Override if required.
#         """
#         return {
#             "service": self.name,
#             "healthy": True,
#         }

#     async def ready(self) -> bool:
#         """
#         Readiness probe.

#         Override if required.
#         """
#         return True