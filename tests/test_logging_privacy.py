"""SQL lines carry buyer details and password hashes, so they stay out of the logs by default."""

import logging

import pytest

from app.config.settings import settings
from app.core.logging.manager import LoggerManager

SQL_LOGGERS = ("sqlalchemy.engine", "sqlalchemy.pool")


@pytest.fixture(autouse=True)
def restore_loggers():
    saved = {name: (logging.getLogger(name).level, logging.getLogger(name).handlers) for name in SQL_LOGGERS}
    yield
    for name, (level, handlers) in saved.items():
        logging.getLogger(name).setLevel(level)
        logging.getLogger(name).handlers = handlers


def _bind() -> LoggerManager:
    owner = logging.getLogger("test-logging-privacy")
    owner.setLevel(logging.INFO)
    manager = LoggerManager(owner)
    manager._bind_external_loggers()
    return manager


def test_sql_is_not_logged_by_default(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_ECHO", False)
    _bind()
    for name in SQL_LOGGERS:
        assert not logging.getLogger(name).isEnabledFor(logging.INFO)
    assert logging.getLogger("sqlalchemy.engine.Engine").getEffectiveLevel() == logging.WARNING


def test_sql_errors_are_still_logged(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_ECHO", False)
    _bind()
    assert logging.getLogger("sqlalchemy.engine").isEnabledFor(logging.ERROR)


def test_asking_for_sql_still_works(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_ECHO", True)
    _bind()
    assert logging.getLogger("sqlalchemy.engine").isEnabledFor(logging.INFO)


def test_other_loggers_keep_their_level(monkeypatch):
    monkeypatch.setattr(settings, "DATABASE_ECHO", False)
    _bind()
    assert logging.getLogger("uvicorn.error").isEnabledFor(logging.INFO)
