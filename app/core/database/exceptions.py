"""
RealTimeTransfer
Enterprise Database Exceptions

Python : 3.13
"""

from __future__ import annotations


class DatabaseError(Exception):
    """
    Base exception for all database errors.
    """

    default_message = "Database operation failed."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.default_message)


class DatabaseConnectionError(DatabaseError):
    """
    Database connection failed.
    """

    default_message = "Unable to connect to the database."


class DatabaseDisconnectionError(DatabaseError):
    """
    Database disconnect failed.
    """

    default_message = "Unable to disconnect from the database."


class DatabaseTimeoutError(DatabaseError):
    """
    Database operation timeout.
    """

    default_message = "Database operation timed out."


class DatabaseIntegrityError(DatabaseError):
    """
    Integrity constraint violation.
    """

    default_message = "Database integrity constraint violated."


class TransactionError(DatabaseError):
    """
    Transaction failure.
    """

    default_message = "Database transaction failed."


class SessionError(DatabaseError):
    """
    Session creation or lifecycle failure.
    """

    default_message = "Database session error."


class QueryExecutionError(DatabaseError):
    """
    SQL execution failed.
    """

    default_message = "Failed to execute database query."


class DriverNotFoundError(DatabaseError):
    """
    Requested database driver is unavailable.
    """

    default_message = "Requested database driver was not found."


class DriverConfigurationError(DatabaseError):
    """
    Invalid driver configuration.
    """

    default_message = "Database driver configuration is invalid."


class DatabaseHealthCheckError(DatabaseError):
    """
    Health check failed.
    """

    default_message = "Database health check failed."


# Registry exceptions
class DriverAlreadyRegisteredError(DatabaseError):
    """Database driver is already registered."""
    default_message = "Database driver is already registered."


class RegistryFrozenError(DatabaseError):
    """Registry has been frozen and cannot accept modifications."""
    default_message = "Registry is frozen."