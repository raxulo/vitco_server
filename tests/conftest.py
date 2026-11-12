"""
Test harness — runs every test against a real, throw-away database.

- Default: a temporary SQLite file.
- `TEST_DATABASE_URL` set to a PostgreSQL server URL (any existing database on it,
  e.g. `postgresql+asyncpg://postgres:secret@localhost:5432/postgres`): the run
  creates `quickyee_test_<hex>` there and drops it at the end.

The environment is set before anything from `app` is imported, because the
settings object is read once at import time.

Python 3.13+
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path
from uuid import uuid4 as _uuid4

from sqlalchemy.engine import make_url

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="quickyee-tests-"))

_SERVER_URL = os.environ.get("TEST_DATABASE_URL", "").strip()
_TEST_DB_NAME = f"quickyee_test_{_uuid4().hex[:12]}"

if _SERVER_URL:
    os.environ["DATABASE_URL"] = (
        make_url(_SERVER_URL).set(database=_TEST_DB_NAME).render_as_string(hide_password=False)
    )
else:
    os.environ["DATABASE_URL"] = f"sqlite+aiosqlite:///{(_TEST_ROOT / 'test.db').as_posix()}"
os.environ["EXCHANGE_PATH"] = str(_TEST_ROOT / "exchange")
os.environ["EXCHANGE_WORKER_ENABLED"] = "false"
os.environ["LOG_PATH"] = str(_TEST_ROOT / "logs")
os.environ["MEDIA_PATH"] = str(_TEST_ROOT / "media")
os.environ["MARKETPLACE_RATE_LIMIT_ENABLED"] = "false"  # all test clients share one IP; test_rate_limit.py turns it on
os.environ["EXCHANGE_UPLOAD_CHUNK_MB"] = "1"          # small chunks keep upload test files small

from collections.abc import AsyncIterator, Awaitable, Callable  # noqa: E402
from uuid import UUID, uuid4  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402

from app.config.database import database_config  # noqa: E402
from app.config.settings import settings  # noqa: E402
from app.core.database.factory import DatabaseFactory  # noqa: E402
from app.core.database.manager import DatabaseManager  # noqa: E402
from app.modules.administration.domain.enums import Role  # noqa: E402
from app.modules.administration.infrastructure.models import UserModel  # noqa: E402
from app.modules.auth.infrastructure.jwt import JWTService  # noqa: E402

# Register every model of the app (as the API does) before create_all runs
import app.modules.configurator  # noqa: E402,F401


@pytest.fixture(scope="session")
def test_root() -> Path:
    return _TEST_ROOT


async def _server_execute(statement: str) -> None:
    """Run CREATE / DROP DATABASE on the Postgres server, outside a transaction."""
    from sqlalchemy import text
    from sqlalchemy.ext.asyncio import create_async_engine

    engine = create_async_engine(_SERVER_URL, isolation_level="AUTOCOMMIT")
    try:
        async with engine.connect() as connection:
            await connection.execute(text(statement))
    finally:
        await engine.dispose()


@pytest.fixture(scope="session")
async def database() -> AsyncIterator[DatabaseManager]:
    # Also catches `app` having been imported before this file set DATABASE_URL
    marker = _TEST_DB_NAME if _SERVER_URL else _TEST_ROOT.as_posix()
    assert marker in database_config.url, "tests must never run against a real database"

    if _SERVER_URL:
        await _server_execute(f'CREATE DATABASE "{_TEST_DB_NAME}"')
    manager = DatabaseFactory(database_config).create()
    try:
        await manager.startup()
        yield manager
    finally:
        await manager.shutdown()
        if _SERVER_URL:
            await _server_execute(f'DROP DATABASE IF EXISTS "{_TEST_DB_NAME}" WITH (FORCE)')
        shutil.rmtree(_TEST_ROOT, ignore_errors=True)


@pytest.fixture(scope="session")
async def api(database: DatabaseManager) -> AsyncIterator[httpx.AsyncClient]:
    """The real FastAPI app (full middleware stack and lifespan), called in-process."""
    from app.main import app

    async with app.router.lifespan_context(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture(scope="session")
def token_for() -> Callable[[UUID, Role], dict[str, str]]:
    jwt = JWTService(secret_key=settings.SECRET_KEY)

    def headers(user_id: UUID, role: Role = Role.VLCC) -> dict[str, str]:
        token = jwt.create_access_token(str(user_id), {"role": str(int(role)), "name": "Test"})
        return {"Authorization": f"Bearer {token}"}

    return headers


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
