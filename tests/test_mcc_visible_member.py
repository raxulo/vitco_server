"""
Visible Member on FAT / SNF and Fixed Rate MCCs: when disabled, the sample number
detail leaves out the VLCC's name and nothing else, and sync reports the setting.
"""

import json
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.config.settings import settings
from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.jwt import JWTService
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.domain.enums import MilkType
from app.modules.vlcc.infrastructure.models import VlccModel
from tests.dataexchange.factories import create_user, create_vlcc

HTML = {"accept": "text/html"}
SAMPLE_API = "/api/v1/mccs/collection-by-sample-result"
SHOP_NAME = "Secret Shop Name"


def _mcc_token(user_id: UUID, mcc_id: UUID) -> dict[str, str]:
    token = JWTService(secret_key=settings.SECRET_KEY).create_access_token(
        str(user_id), {"role": str(int(Role.MCC)), "name": "MCC", "own_id": str(mcc_id)}
    )
    return {"Authorization": f"Bearer {token}"}


async def _mcc(database, created_by: UUID, mcc_type: MccType, visible_member: bool = True) -> tuple[UUID, UUID]:
    user_id = await create_user(database, role=Role.MCC, created_by=created_by, name="MCC User")
    mcc_id, settings_id = uuid4(), uuid4()
    async with database.transaction() as session:
        session.add(SettingsModel(id=settings_id))
        await session.flush()
        session.add(MccModel(
            id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name=f"{mcc_type.name} MCC", mcc_type=mcc_type,
            created_by=created_by, settings_id=settings_id, visible_member=visible_member,
            sample_start=1, sample_end=1000,
        ))
    return user_id, mcc_id


@pytest.fixture
async def scene(database):
    """A weight MCC recorded sample 5 from a VLCC; other MCCs of the same owner look it up."""
    admin = await create_user(database, role=Role.ADMIN)
    _, weight_mcc = await _mcc(database, admin, MccType.WEIGHT)
    vlcc = await create_vlcc(database, created_by=admin)
    async with database.transaction() as session:
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc.id).values(name=SHOP_NAME))
        session.add(MccCollectionModel(
            id=uuid4(), mcc_id=weight_mcc, vlcc_id=vlcc.id, sample_number=5, can_count=3, shift=CollectionShift.MORNING,
            milk_type=MilkType.COW, quantity=Decimal("42.50"), collected_at=now_naive_ist(),
        ))
    return admin, vlcc


async def _ask(api, database, scene, mcc_type: MccType, visible_member: bool):
    admin, _ = scene
    user_id, mcc_id = await _mcc(database, admin, mcc_type, visible_member)
    response = await api.post(
        SAMPLE_API, json={"sample_number": 5, "shift": 0}, headers=_mcc_token(user_id, mcc_id)
    )
    assert response.status_code == 200, response.text
    return response.json()["collection_detail"]


@pytest.mark.parametrize("mcc_type", [MccType.FAT_SNF, MccType.FIXED_RATE])
async def test_disabled_hides_only_the_vlcc_name(api, database, scene, mcc_type):
    _, vlcc = scene

    detail = await _ask(api, database, scene, mcc_type, visible_member=False)

    assert detail["vlcc_name"] is None
    assert detail["vlcc_id"] == str(vlcc.id)
    assert detail["quantity"] == 42.5 and detail["can_count"] == 3
    assert detail["mcc_name"] == "WEIGHT MCC"


@pytest.mark.parametrize("mcc_type", [MccType.FAT_SNF, MccType.FIXED_RATE])
async def test_enabled_shows_the_name(api, database, scene, mcc_type):
    assert (await _ask(api, database, scene, mcc_type, visible_member=True))["vlcc_name"] == SHOP_NAME


@pytest.mark.parametrize("mcc_type", [MccType.NORMAL])
async def test_other_types_always_show_the_name(api, database, scene, mcc_type):
    """A stored False can't hide anything on a type without the setting, such as after a type change."""
    assert (await _ask(api, database, scene, mcc_type, visible_member=False))["vlcc_name"] == SHOP_NAME


@pytest.mark.parametrize(
    ("mcc_type", "supported"),
    [(MccType.FAT_SNF, True), (MccType.FIXED_RATE, True), (MccType.NORMAL, False), (MccType.WEIGHT, False)],
)
def test_rule(mcc_type, supported):
    assert mcc_type.supports_visible_member is supported
    assert mcc_type.shows_member_name(True) is True
    assert mcc_type.shows_member_name(False) is (not supported)


async def test_new_mcc_defaults_to_enabled(database):
    admin = await create_user(database, role=Role.ADMIN)
    user_id = await create_user(database, role=Role.MCC, created_by=admin)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name="New", mcc_type=MccType.FAT_SNF, created_by=admin))
    async with database.transaction() as session:
        assert await session.scalar(select(MccModel.visible_member).where(MccModel.id == mcc_id)) is True


async def test_web_lookup_sends_no_name_but_still_fills_the_form(api, database, scene, token_for):
    admin, vlcc = scene
    _, mcc_id = await _mcc(database, admin, MccType.FAT_SNF, visible_member=False)

    response = await api.get(
        "/mcc-collections/get-sample-result",
        params={"mcc_id": str(mcc_id), "sample_number": "5", "shift": "0", "collection_date": now_naive_ist().strftime("%Y-%m-%dT%H:%M")},
        headers=token_for(admin, Role.ADMIN) | HTML,
    )

    filled = json.loads(response.headers["hx-trigger"])["populate-fields"]
    assert filled["vlcc_name"] == "" and filled["vlcc_id"] == str(vlcc.id)
    assert filled["quantity"] == "42.50" and filled["can_count"] == 3
    assert SHOP_NAME not in response.headers["hx-trigger"] and SHOP_NAME not in response.text


@pytest.mark.parametrize(("visible_member", "name_shown"), [(False, False), (True, True)])
async def test_collection_form_follows_the_setting(api, database, scene, token_for, visible_member, name_shown):
    admin, vlcc = scene
    _, mcc_id = await _mcc(database, admin, MccType.FAT_SNF, visible_member)

    page = (await api.get("/mcc-collections/load-form", params={"mcc_id": str(mcc_id)}, headers=token_for(admin, Role.ADMIN) | HTML)).text

    assert f'value="{vlcc.id}"' in page  # the VLCC can still be selected
    assert (SHOP_NAME in page) is name_shown
    assert f"UIC: {vlcc.code}" in page


@pytest.mark.parametrize(
    ("mcc_type", "stored", "reported"),
    [
        (MccType.FAT_SNF, False, False),
        (MccType.FAT_SNF, True, True),
        (MccType.FIXED_RATE, False, False),
        (MccType.NORMAL, False, True),
    ],
)
async def test_sync_reports_the_setting(api, database, mcc_type, stored, reported):
    admin = await create_user(database, role=Role.ADMIN)
    user_id, mcc_id = await _mcc(database, admin, mcc_type, stored)

    response = await api.get("/api/v1/sync/", headers=_mcc_token(user_id, mcc_id))

    assert response.status_code == 200, response.text
    assert response.json()["mcc_info"]["visible_member"] is reported
