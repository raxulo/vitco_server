"""
RealTimeTransfer
================

Dependency Injection Exceptions

Python 3.13+
"""

from __future__ import annotations


class ContainerError(Exception):
    """
    Base container exception.
    """

    default_message = "Dependency injection container error."

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

class ProviderAlreadyRegisteredError(
    ContainerError,
):
    """
    Provider already exists.
    """

    default_message = (
        "Provider already registered."
    )


class ProviderNotFoundError(
    ContainerError,
):
    """
    Provider not found.
    """

    default_message = (
        "Provider not found."
    )


class RegistrationError(
    ContainerError,
):
    """
    Invalid registration.
    """

    default_message = (
        "Service registration failed."
    )


# ==========================================================
# Resolution
# ==========================================================

class ResolutionError(
    ContainerError,
):
    """
    Unable to resolve service.
    """

    default_message = (
        "Service resolution failed."
    )


class FactoryError(
    ResolutionError,
):
    """
    Factory execution failed.
    """

    default_message = (
        "Factory execution failed."
    )


class ConstructorInjectionError(
    ResolutionError,
):
    """
    Constructor injection failed.
    """

    default_message = (
        "Constructor injection failed."
    )


# ==========================================================
# Dependency
# ==========================================================

class CircularDependencyError(
    ResolutionError,
):
    """
    Circular dependency detected.
    """

    default_message = (
        "Circular dependency detected."
    )


class DependencyNotFoundError(
    ResolutionError,
):
    """
    Required dependency missing.
    """

    default_message = (
        "Dependency not found."
    )


# ==========================================================
# Scope
# ==========================================================

class ScopeError(
    ContainerError,
):
    """
    Scope related error.
    """

    default_message = (
        "Scope error."
    )


class ScopeNotActiveError(
    ScopeError,
):
    """
    No active request scope.
    """

    default_message = (
        "No active request scope."
    )


# ==========================================================
# Validation
# ==========================================================

class InvalidProviderError(
    ContainerError,
):
    """
    Invalid provider.
    """

    default_message = (
        "Invalid service provider."
    )


class InvalidFactoryError(
    InvalidProviderError,
):
    """
    Invalid factory.
    """

    default_message = (
        "Factory must be callable."
    )


class InvalidServiceTypeError(
    InvalidProviderError,
):
    """
    Invalid service type.
    """

    default_message = (
        "Invalid service type."
    )