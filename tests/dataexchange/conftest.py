"""
API fixtures for the Excel exchange tests; `api` and `token_for` come from tests/conftest.py.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from uuid import UUID

import pytest

from app.modules.administration.domain.enums import Role


@pytest.fixture
def api_user(user_factory, token_for) -> Callable[..., Awaitable[tuple[UUID, dict[str, str]]]]:
    async def create(role: Role = Role.VLCC) -> tuple[UUID, dict[str, str]]:
        user_id = await user_factory(role)
        return user_id, token_for(user_id, role)

    return create
