"""
Hierarchy scopes work whatever type the owner's id has.

An id read back from PostgreSQL is asyncpg's own UUID class, which SQLAlchemy
cannot type as a bare parameter; inside a UNION / IN PostgreSQL then read it as
text and refused it ("operator does not exist: uuid = text"). The Excel worker
builds its owner from the job row, so a Sub Admin's or MCC's VLCC import failed
on PostgreSQL only. On SQLite these tests pass either way; with
TEST_DATABASE_URL they guard the fix.
"""

from uuid import UUID, uuid4

import pytest
from sqlalchemy import select

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.hierarchy import Hierarchy
from app.modules.administration.infrastructure.models import UserModel
from app.modules.vlcc.infrastructure.models import VlccModel
from tests.dataexchange.factories import create_user, create_vlcc

_ROLES = (Role.ADMIN, Role.SUB_ADMIN, Role.MCC, Role.VLCC, Role.FARMER)


async def _id_from_database(database, user_id: UUID):
    async with database.transaction() as session:
        return await session.scalar(select(UserModel.id).where(UserModel.id == user_id))


def _queries(owner: CurrentUser):
    in_scope = (
        Hierarchy.mcc_ids(owner),
        Hierarchy.vlcc_creators(owner),
        Hierarchy.vlcc_ids(owner),
        Hierarchy.visible_vlcc_ids(owner),
        Hierarchy.controlled_users(owner),
        Hierarchy.farmer_users(owner),
        Hierarchy.ancestor_users(owner),
    )
    yield from (select(VlccModel.id).where(VlccModel.created_by.in_(ids)) for ids in in_scope if ids is not None)
    for condition in (
        Hierarchy.shared_visible(owner, VlccModel.created_by),
        Hierarchy.shared_modifiable(owner, VlccModel.created_by),
        Hierarchy.code_conflict(owner, VlccModel.created_by),
    ):
        yield select(VlccModel.id).where(condition)


@pytest.mark.parametrize("role", _ROLES, ids=lambda role: role.name)
@pytest.mark.parametrize("id_type", ["uuid", "read_back"])
async def test_every_scope_runs_for_any_id_type(database, role, id_type):
    """`uuid`: as a request's CurrentUser has it. `read_back`: as the Excel worker gets it from the job row."""
    user_id = await create_user(database, role=role)
    raw = await _id_from_database(database, user_id) if id_type == "read_back" else user_id
    owner = CurrentUser(id=raw, role=Role(role))

    async with database.transaction() as session:
        for query in _queries(owner):
            await session.execute(query)


async def test_sub_admin_code_conflict_finds_its_own_vlcc(database):
    """The VLCC import's duplicate-code check, as the worker runs it for a Sub Admin."""
    admin = await create_user(database, role=Role.ADMIN)
    sub = await create_user(database, role=Role.SUB_ADMIN, created_by=admin)
    own = await create_vlcc(database, created_by=sub)
    stranger = await create_vlcc(database, created_by=await create_user(database, role=Role.ADMIN))
    owner = CurrentUser(id=await _id_from_database(database, sub), role=Role.SUB_ADMIN)

    async with database.transaction() as session:
        clashing = set(await session.scalars(
            select(VlccModel.vlcc_code).where(
                VlccModel.vlcc_code.in_([own.code, stranger.code]),
                Hierarchy.code_conflict(owner, VlccModel.created_by),
            )
        ))
    assert clashing == {own.code}


async def test_unknown_owner_matches_nothing(database):
    owner = CurrentUser(id=uuid4(), role=Role.SUB_ADMIN)
    async with database.transaction() as session:
        found = list(await session.scalars(select(VlccModel.id).where(VlccModel.id.in_(Hierarchy.vlcc_ids(owner)))))
    assert found == []
