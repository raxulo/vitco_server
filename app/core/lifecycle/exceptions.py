"""
RealTimeTransfer
================

Lifecycle Exceptions

Python 3.13+
"""

from __future__ import annotations


class LifecycleError(Exception):
    """
    Base lifecycle exception.
    """

    default_message = "Lifecycle operation failed."

    def __init__(
        self,
        message: str | None = None,
    ) -> None:

        super().__init__(
            message or self.default_message
        )


# ==========================================================
# Registration
# ==========================================================

class ServiceRegistrationError(LifecycleError):
    """
    Service registration failed.
    """

    default_message = (
        "Service registration failed."
    )


class DuplicateServiceError(LifecycleError):
    """
    Service already registered.
    """

    default_message = (
        "Service already exists."
    )


# ==========================================================
# Lifecycle
# ==========================================================

class ServiceStartError(LifecycleError):
    """
    Failed to start service.
    """

    default_message = (
        "Service failed to start."
    )


class ServiceStopError(LifecycleError):
    """
    Failed to stop service.
    """

    default_message = (
        "Service failed to stop."
    )


class ServiceAlreadyRunningError(LifecycleError):
    """
    Service is already running.
    """

    default_message = (
        "Service is already running."
    )


class ServiceAlreadyStoppedError(LifecycleError):
    """
    Service is already stopped.
    """

    default_message = (
        "Service is already stopped."
    )


# ==========================================================
# Dependency
# ==========================================================

class ServiceDependencyError(LifecycleError):
    """
    Dependency resolution failed.
    """

    default_message = (
        "Service dependency error."
    )


class CircularDependencyError(
    ServiceDependencyError,
):
    """
    Circular dependency detected.
    """

    default_message = (
        "Circular service dependency detected."
    )


class MissingDependencyError(
    ServiceDependencyError,
):
    """
    Required dependency not found.
    """

    default_message = (
        "Required dependency not found."
    )


# ==========================================================
# Timeout
# ==========================================================

class ServiceTimeoutError(LifecycleError):
    """
    Service operation timeout.
    """

    default_message = (
        "Service startup timeout."
    )


# ==========================================================
# Health
# ==========================================================

class ServiceHealthError(LifecycleError):
    """
    Service health check failed.
    """

    default_message = (
        "Service health check failed."
    )