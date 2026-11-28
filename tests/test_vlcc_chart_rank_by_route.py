"""VLCC chart rank by route (Assign by Route)."""
from contextlib import asynccontextmanager
from uuid import uuid4

import pytest

from app.modules.vlcc.application.handler import VlccHandler
from app.modules.vlcc.domain.exceptions import InvalidVlccException


class _FakeDb:
    @asynccontextmanager
    async def transaction(self):
        yield


class _FakeRepo:
    def __init__(self, user_ids):
        self.user_ids = user_ids
        self.calls = []

    async def set_chart_rank_by_route(self, route_code, chart_rank, owner):
        self.calls.append((route_code, chart_rank))
        return self.user_ids


def _handler(repo):
    handler = VlccHandler.__new__(VlccHandler)
    handler._database = _FakeDb()
    handler._vlcc_repository = repo
    return handler


@pytest.mark.asyncio
@pytest.mark.parametrize("rank", [0, 16, -1])
async def test_rank_out_of_range_rejected(rank):
    repo = _FakeRepo([])
    with pytest.raises(InvalidVlccException):
        await _handler(repo).apply_chart_rank_by_route(5, rank, owner=None)
    assert repo.calls == []


@pytest.mark.asyncio
@pytest.mark.parametrize("rank", [1, 15])
async def test_valid_rank_returns_user_ids(rank):
    ids = [uuid4(), uuid4()]
    repo = _FakeRepo(ids)
    assert await _handler(repo).apply_chart_rank_by_route(5, rank, owner=None) == ids
    assert repo.calls == [(5, rank)]
