"""
Test harness — runs every test against a real, temporary SQLite database.

The environment is set before anything from `app` is imported, because the
settings object is read once at import time.

Python 3.13+
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="quickyee-tests-"))

os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TEST_ROOT / 'test.db').as_posix()}"
os.environ["EXCHANGE_PATH"] = str(_TEST_ROOT / "exchange")
os.environ["EXCHANGE_WORKER_ENABLED"] = "false"
os.environ["LOG_PATH"] = str(_TEST_ROOT / "logs")
os.environ["EXCHANGE_UPLOAD_CHUNK_MB"] = "1"          # small chunks keep upload test files small

from collections.abc import AsyncIterator, Awaitable, Callable  # noqa: E402
from uuid import UUID, uuid4  # noqa: E402

import pytest  # noqa: E402

from app.config.database import database_config  # noqa: E402
from app.core.database.factory import DatabaseFactory  # noqa: E402
from app.core.database.manager import DatabaseManager  # noqa: E402
from app.modules.administration.domain.enums import Role  # noqa: E402
from app.modules.administration.infrastructure.models import UserModel  # noqa: E402

# Register every table the tests touch before create_all runs
import app.modules.dataexchange.infrastructure.models  # noqa: E402,F401


@pytest.fixture(scope="session")
def test_root() -> Path:
    return _TEST_ROOT


@pytest.fixture(scope="session")
async def database() -> AsyncIterator[DatabaseManager]:
    assert database_config.url.startswith("sqlite"), "tests must never run against a real database"
    manager = DatabaseFactory(database_config).create()
    await manager.startup()
    try:
        yield manager
    finally:
        await manager.shutdown()
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
def user_factory(database: DatabaseManager) -> Callable[..., Awaitable[UUID]]:
    """Insert a real user row and return its id."""

    async def create(role: Role = Role.VLCC, name: str = "Test User") -> UUID:
        user_id = uuid4()
        digits = str(user_id.int)[-10:]
        async with database.transaction() as session:
            session.add(
                UserModel(
                    id=user_id,
                    name=name,
                    email=f"{user_id.hex}@test.local",
                    mobile=f"9{digits[1:]}",
                    password_hash="not-a-real-hash",
                    role=role,
                )
            )
        return user_id

    return create
