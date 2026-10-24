"""
API fixtures: the real FastAPI app (full middleware stack and lifespan) on the
test database, called in-process through httpx.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import httpx
import pytest

from app.config.settings import settings
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.jwt import JWTService


@pytest.fixture(scope="session")
async def api(database) -> httpx.AsyncClient:
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


@pytest.fixture
def api_user(user_factory, token_for) -> Callable[..., Awaitable[tuple[UUID, dict[str, str]]]]:
    async def create(role: Role = Role.VLCC) -> tuple[UUID, dict[str, str]]:
        user_id = await user_factory(role)
        return user_id, token_for(user_id, role)

    return create
