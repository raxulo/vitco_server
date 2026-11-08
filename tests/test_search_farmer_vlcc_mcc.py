"""
Search on the Farmer / VLCC / MCC lists:
- farmers by farmer name, farmer code or VLCC name, optionally filtered to one VLCC;
- VLCCs and MCCs by name, code or the name of the user who created them;
and the count used for pagination always matches the rows found.
"""

from uuid import UUID, uuid4

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.farmer.infrastructure.repository import FarmerRepository
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.mcc.infrastructure.repository import MccRepository
from app.modules.vlcc.infrastructure.repository import VlccRepository
from tests.dataexchange.factories import create_farmers, create_user, create_vlcc


def _super_admin() -> CurrentUser:
    return CurrentUser(id=uuid4(), role=str(int(Role.SUPER_ADMIN)))


async def _rename_vlcc(database, vlcc_id: UUID, name: str) -> None:
    from sqlalchemy import update
    from app.modules.vlcc.infrastructure.models import VlccModel

    async with database.transaction() as session:
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc_id).values(name=name))


async def test_farmer_search_by_vlcc_name_and_vlcc_filter(database):
    owner = _super_admin()
    tag = uuid4().hex[:6]
    vlcc_a = await create_vlcc(database)
    vlcc_b = await create_vlcc(database)
    await _rename_vlcc(database, vlcc_a.id, f"Gokul {tag}")
    await _rename_vlcc(database, vlcc_b.id, f"Amul {tag}")
    farmers_a = await create_farmers(database, vlcc_a, 2, prefix=f"A{tag}")
    farmers_b = await create_farmers(database, vlcc_b, 3, prefix=f"B{tag}")
    repo = FarmerRepository(database)

    async with database.transaction():
        # VLCC name
        by_vlcc = await repo.search(f"Gokul {tag}", 0, 50, owner=owner)
        assert {f.user_id for f in by_vlcc} == {f["user_id"] for f in farmers_a}
        assert await repo.count_search(f"Gokul {tag}", owner=owner) == 2

        # Farmer code and farmer name still work
        code = farmers_b[0]["farmer_code"]
        assert [f.user_id for f in await repo.search(code, 0, 50, owner=owner)] == [farmers_b[0]["user_id"]]
        assert len(await repo.search(farmers_b[1]["name"], 0, 50, owner=owner)) == 1

        # VLCC filter: a keyword matching both VLCCs is narrowed to the chosen one
        narrowed = await repo.search(tag, 0, 50, vlcc_id=vlcc_b.id, owner=owner)
        assert {f.user_id for f in narrowed} == {f["user_id"] for f in farmers_b}
        assert await repo.count_search(tag, vlcc_id=vlcc_b.id, owner=owner) == 3
        assert await repo.count(vlcc_id=vlcc_a.id, owner=owner) == 2


async def test_vlcc_search_by_creator_name(database):
    owner = _super_admin()
    tag = uuid4().hex[:6]
    creator = await create_user(database, role=Role.ADMIN, name=f"Suresh Creator {tag}")
    mine = await create_vlcc(database, created_by=creator)
    await create_vlcc(database, created_by=await create_user(database, role=Role.ADMIN, name=f"Other {tag}"))
    repo = VlccRepository(database)

    async with database.transaction():
        found = await repo.search(f"Suresh Creator {tag}", 0, 50, owner)
        assert [v.id for v in found] == [mine.id]
        # Search results carry the creator name like the plain list does
        assert found[0].owner_name == f"Suresh Creator {tag}"
        assert await repo.count_search(f"Suresh Creator {tag}", owner) == 1

        # VLCC code still works
        assert [v.id for v in await repo.search(mine.code, 0, 50, owner)] == [mine.id]


def _manager(user_id: UUID, role: Role) -> CurrentUser:
    return CurrentUser(id=user_id, role=str(int(role)))


async def _mcc(database, created_by: UUID, tag: str) -> UUID:
    mcc_user = await create_user(database, role=Role.MCC, created_by=created_by)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=mcc_user, code=f"M{mcc_id.hex[:5]}", name=f"MCC {tag}",
                             mcc_type=MccType.NORMAL, created_by=created_by))
    return mcc_id


async def _vlcc_with_settings(database, created_by: UUID):
    """A VLCC as the app creates it: with its settings row (the VLCC list joins it)."""
    from sqlalchemy import update
    from app.modules.common.settings.infrastructure.models import SettingsModel
    from app.modules.vlcc.infrastructure.models import VlccModel

    vlcc = await create_vlcc(database, created_by=created_by)
    settings_id = uuid4()
    async with database.transaction() as session:
        session.add(SettingsModel(id=settings_id))
        await session.flush()
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc.id).values(settings_id=settings_id))
    return vlcc


async def test_admin_and_sub_admin_filters(database):
    """Admin filter = the Admin's line incl. its Sub Admins; Sub Admin filter = only its own."""
    owner = _super_admin()
    tag = uuid4().hex[:6]
    admin = await create_user(database, role=Role.ADMIN, name=f"Admin {tag}")
    sub = await create_user(database, role=Role.SUB_ADMIN, name=f"Sub {tag}", created_by=admin)
    other_admin = await create_user(database, role=Role.ADMIN, name=f"Other {tag}")

    admin_mcc = await _mcc(database, admin, tag)
    sub_mcc = await _mcc(database, sub, tag)
    other_mcc = await _mcc(database, other_admin, tag)
    admin_vlcc = await _vlcc_with_settings(database, admin)
    sub_vlcc = await _vlcc_with_settings(database, sub)
    other_vlcc = await _vlcc_with_settings(database, other_admin)

    mccs, vlccs = MccRepository(database), VlccRepository(database)
    as_admin, as_sub = _manager(admin, Role.ADMIN), _manager(sub, Role.SUB_ADMIN)

    async with database.transaction():
        # MCC list: by Admin includes its Sub Admin's MCC, never another Admin's
        found = {m.id for m in await mccs.list_mcc_with_user(0, 500, owner=owner, manager=as_admin)}
        assert {admin_mcc, sub_mcc} <= found and other_mcc not in found
        assert await mccs.count(owner, manager=as_admin) == len(found)
        assert {m.id for m in await mccs.list_mcc_with_user(0, 500, owner=owner, manager=as_sub)} == {sub_mcc}
        # Filter + search together
        assert await mccs.count_search(f"MCC {tag}", owner, manager=as_sub) == 1

        # VLCC list / search / counts follow the same lines
        by_admin = {v.id for v in await vlccs.list(0, 500, owner, manager=as_admin)}
        assert {admin_vlcc.id, sub_vlcc.id} <= by_admin and other_vlcc.id not in by_admin
        assert await vlccs.count(owner, manager=as_admin) == len(by_admin)
        assert {v.id for v in await vlccs.list(0, 500, owner, manager=as_sub)} == {sub_vlcc.id}
        assert await vlccs.count(owner, manager=as_sub) == 1
        assert {v.id for v in await vlccs.search(sub_vlcc.code, 0, 50, owner, manager=as_admin)} == {sub_vlcc.id}
        assert await vlccs.search(sub_vlcc.code, 0, 50, owner, manager=_manager(other_admin, Role.ADMIN)) == []


async def test_mcc_search_by_creator_name(database):
    owner = _super_admin()
    tag = uuid4().hex[:6]
    creator = await create_user(database, role=Role.ADMIN, name=f"Mahesh Creator {tag}")
    mcc_user = await create_user(database, role=Role.MCC, created_by=creator)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=mcc_user, code=f"MC{tag}", name=f"Centre {tag}",
                             mcc_type=MccType.NORMAL, created_by=creator))
    repo = MccRepository(database)

    async with database.transaction():
        found = await repo.list_mcc_with_user(0, 50, keyword=f"Mahesh Creator {tag}", owner=owner)
        assert [m.id for m in found] == [mcc_id]
        assert found[0].created_by_name == f"Mahesh Creator {tag}"
        assert await repo.count_search(f"Mahesh Creator {tag}", owner) == 1

        # Name and code still work
        assert [m.id for m in await repo.list_mcc_with_user(0, 50, keyword=f"MC{tag}", owner=owner)] == [mcc_id]
        assert await repo.count_search(f"Centre {tag}", owner) == 1
