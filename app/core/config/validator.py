"""
RealTimeTransfer
================

Configuration Validator

Python 3.13+
"""

from __future__ import annotations

from collections.abc import Callable

from app.core.config.settings import Settings


class ConfigurationError(RuntimeError):
    """
    Raised when application configuration is invalid.
    """


class ConfigValidator:
    """
    Enterprise configuration validator.

    Validates every configuration section
    before application startup.
    """

    __slots__ = (
        "_settings",
        "_errors",
    )

    def __init__(
        self,
        settings: Settings,
    ) -> None:

        self._settings = settings

        self._errors: list[str] = []

    # --------------------------------------------------
    # Public
    # --------------------------------------------------

    def validate(self) -> None:

        self._run(self._validate_server)

        self._run(self._validate_database)

        self._run(self._validate_security)

        self._run(self._validate_storage)

        self._run(self._validate_cache)

        self._run(self._validate_logging)

        if self._errors:

            raise ConfigurationError(

                "\n".join(self._errors)
            )

    # --------------------------------------------------
    # Helpers
    # --------------------------------------------------

    def _run(
        self,
        validator: Callable[[], None],
    ) -> None:

        validator()

    def _error(
        self,
        message: str,
    ) -> None:

        self._errors.append(message)

    # --------------------------------------------------
    # Server
    # --------------------------------------------------

    def _validate_server(self) -> None:

        server = self._settings.server

        if not (1 <= server.http.port <= 65535):

            self._error(
                "Server port must be between 1 and 65535."
            )

        if server.http.workers <= 0:

            self._error(
                "Workers must be greater than zero."
            )

    # --------------------------------------------------
    # Database
    # --------------------------------------------------

    def _validate_database(self) -> None:

        database = self._settings.database

        if not database.url:

            self._error(
                "Database URL is required."
            )

        if database.pool.pool_size <= 0:

            self._error(
                "Database pool size must be positive."
            )

        if database.pool.max_overflow < 0:

            self._error(
                "Database max overflow cannot be negative."
            )

    # --------------------------------------------------
    # Security
    # --------------------------------------------------

    def _validate_security(self) -> None:

        security = self._settings.security

        if security.password.min_length < 8:

            self._error(
                "Password minimum length must be at least 8."
            )

        if security.jwt.access_token_expire <= 0:

            self._error(
                "Access token expiry must be greater than zero."
            )

        if security.otp.length < 4:

            self._error(
                "OTP length must be at least 4."
            )

    # --------------------------------------------------
    # Storage
    # --------------------------------------------------

    def _validate_storage(self) -> None:

        storage = self._settings.storage

        if storage.validation.max_file_size <= 0:

            self._error(
                "Maximum file size must be positive."
            )

        if storage.chunk.chunk_size <= 0:

            self._error(
                "Chunk size must be positive."
            )

    # --------------------------------------------------
    # Cache
    # --------------------------------------------------

    def _validate_cache(self) -> None:

        cache = self._settings.cache

        if cache.memory.max_entries <= 0:

            self._error(
                "Memory cache size must be positive."
            )

        if cache.policy.default_ttl <= 0:

            self._error(
                "Cache TTL must be greater than zero."
            )

    # --------------------------------------------------
    # Logging
    # --------------------------------------------------

    def _validate_logging(self) -> None:

        logging = self._settings.logging

        if logging.file.max_size <= 0:

            self._error(
                "Log file size must be positive."
            )

        if logging.file.backup_count < 1:

            self._error(
                "Backup count must be at least one."
            )