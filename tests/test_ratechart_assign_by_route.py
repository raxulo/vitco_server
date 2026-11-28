"""Rate chart bulk assign (append) used by Assign by Route."""
from contextlib import asynccontextmanager
from datetime import datetime
from uuid import uuid4

import pytest

from app.modules.administration.domain.enums import Role
from app.modules.ratechart.application.command import AssignChartToOwnersCommand
from app.modules.ratechart.application.handler import RateChartHandler
from app.modules.ratechart.domain.entities import RateChartAssignment


class _FakeDb:
    @asynccontextmanager
    async def transaction(self):
        yield


class _FakeRepo:
    def __init__(self, existing):
        self.existing = existing
        self.created: list[RateChartAssignment] = []

    async def get_assignments_by_owners(self, owner_ids):
        return [a for a in self.existing if a.owner_id in owner_ids]

    async def create_assignment(self, entity):
        self.created.append(entity)


def _row(owner_id, chart_id, priority):
    now = datetime(2026, 1, 1)
    return RateChartAssignment(
        id=uuid4(), owner_type=Role.MCC, owner_id=owner_id, rate_chart_id=chart_id,
        priority=priority, is_default=priority == 0, is_active=True,
        created_by=None, created_at=now, updated_at=now,
    )


@pytest.mark.asyncio
async def test_appends_skips_duplicates_and_keeps_default():
    chart, other = uuid4(), uuid4()
    fresh, has_other, has_chart = uuid4(), uuid4(), uuid4()
    repo = _FakeRepo([_row(has_other, other, 0), _row(has_other, uuid4(), 1), _row(has_chart, chart, 0)])
    handler = RateChartHandler(_FakeDb(), repo)

    result = await handler.assign_chart_to_owners(AssignChartToOwnersCommand(
        owner_type=Role.MCC, owner_ids=[fresh, has_other, has_chart, fresh], rate_chart_id=chart,
    ))

    assert (result.assigned, result.skipped) == (2, 1)
    by_owner = {a.owner_id: a for a in repo.created}
    assert by_owner[fresh].is_default and by_owner[fresh].priority == 0
    assert not by_owner[has_other].is_default and by_owner[has_other].priority == 2


@pytest.mark.asyncio
async def test_empty_owner_list_is_noop():
    handler = RateChartHandler(_FakeDb(), _FakeRepo([]))
    result = await handler.assign_chart_to_owners(AssignChartToOwnersCommand(
        owner_type=Role.VLCC, owner_ids=[], rate_chart_id=uuid4(),
    ))
    assert (result.assigned, result.skipped) == (0, 0)
