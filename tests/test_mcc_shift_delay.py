"""
MCC Shift Delay and the live, read-only entry date / shift (Phase 22, DECISION-029).

- The MCC stores `shift_delay` ("HH:MM", default "00:00") and sync reports it.
- A new MCC collection entered on the web is stamped at now - shift delay, in the shift of
  that time from the MCC's morning shift end; a VLCC collection at now, by the VLCC's shifts.
- Posted dates and shifts are ignored, and an edit keeps the stored ones.

Python 3.13+
"""

import re
from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from sqlalchemy import select, update

from app.config.settings import settings
from app.core.validators import shift_delay as shift_delay_value
from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.jwt import JWTService
from app.modules.collections.mcc_collection.domain.clock import collection_moment, shift_at
from app.modules.collections.mcc_collection.domain.enums import CollectionShift, MilkType
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.mcc.application.handler import MccHandler
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.mcc.presentation.requests import CreateMccRequest, UpdateMccRequest
from app.modules.vlcc.infrastructure.models import VlccModel
from app.web.mcc.assembler import MccAssembler
from tests.dataexchange.factories import create_farmers, create_user, create_vlcc, unique_mobile

HTML = {"accept": "text/html"}


# =========================================================
# Rules (pure)
# =========================================================

def test_user_example_same_day():
    moment, shift = collection_moment(datetime(2026, 11, 14, 10, 44), "05:44", "10:00")
    assert moment == datetime(2026, 11, 14, 5, 0)
    assert shift == CollectionShift.MORNING


def test_user_example_previous_day():
    moment, shift = collection_moment(datetime(2026, 10, 11, 0, 30), "05:20", "10:00")
    assert moment == datetime(2026, 10, 10, 19, 10)
    assert shift == CollectionShift.EVENING


@pytest.mark.parametrize("delay", [None, "", "00:00", "bad"])
def test_no_delay_keeps_the_time(delay):
    now = datetime(2026, 11, 14, 8, 15, 42, 123456)
    assert collection_moment(now, delay, "10:00") == (now.replace(microsecond=0), CollectionShift.MORNING)


@pytest.mark.parametrize(
    ("hour", "minute", "morning_end", "expected"),
    [
        (9, 59, "10:00", CollectionShift.MORNING),
        (10, 0, "10:00", CollectionShift.EVENING),
        (23, 30, "10:00", CollectionShift.EVENING),
        (3, 0, "10:00", CollectionShift.MORNING),
        (11, 59, None, CollectionShift.MORNING),   # no settings: split at 12:00
        (12, 0, "", CollectionShift.EVENING),
    ],
)
def test_shift_from_morning_end(hour, minute, morning_end, expected):
    assert shift_at(datetime(2026, 11, 14, hour, minute), morning_end) == expected


@pytest.mark.parametrize(("raw", "clean"), [(None, "00:00"), ("", "00:00"), (" 05:44 ", "05:44"), ("5:30", "05:30"), ("23:59", "23:59")])
def test_shift_delay_accepted(raw, clean):
    assert shift_delay_value(raw) == clean


@pytest.mark.parametrize("raw", ["24:00", "12:60", "abc", "0544", "5", "-01:00"])
def test_shift_delay_refused(raw):
    with pytest.raises(ValueError, match="HH:MM"):
        shift_delay_value(raw)


# =========================================================
# MCC create / edit / sync
# =========================================================

def _form(code: str, **extra) -> dict:
    # Only FAT / SNF MCCs have a shift delay
    return {"code": code, "name": "Delay MCC", "mobile": unique_mobile(), "email": f"d{code}@gmail.com",
            "password": "Pass@123", "mcc_type": str(int(MccType.FAT_SNF)), **extra}


async def _stored_delay(database, mcc_id: UUID) -> str:
    async with database.transaction() as session:
        return await session.scalar(select(MccModel.shift_delay).where(MccModel.id == mcc_id))


async def test_create_and_edit_keep_the_delay(api, database):
    from app.main import app

    admin = await create_user(database, role=Role.ADMIN)
    owner = CurrentUser(id=admin, role=str(Role.ADMIN.value))
    handler = app.state.application.container.resolve(MccHandler)
    code = str(uuid4().int)[:6]

    form = CreateMccRequest.model_validate(_form(code, shift_delay="05:44"))
    async with app.state.application.container.database.transaction():
        created = await handler.full_create(MccAssembler.create(form, admin), owner=owner)
    mcc_id = created.mcc.id
    assert await _stored_delay(database, mcc_id) == "05:44"

    # A blank field means no delay
    edit = UpdateMccRequest.model_validate(_form(code, shift_delay="", mobile=created.user.mobile, email=created.user.email))
    async with app.state.application.container.database.transaction():
        await handler.full_update(MccAssembler.update(edit, mcc_id, admin), owner=owner)
    assert await _stored_delay(database, mcc_id) == "00:00"


def test_form_without_the_field_defaults_to_no_delay():
    assert CreateMccRequest.model_validate(_form("123456")).shift_delay == "00:00"


def test_form_refuses_a_bad_delay():
    with pytest.raises(ValueError, match="Shift delay"):
        CreateMccRequest.model_validate(_form("123456", shift_delay="25:00"))


@pytest.mark.parametrize("model", [CreateMccRequest, UpdateMccRequest])
@pytest.mark.parametrize(("delay", "morning_start", "allowed"), [
    ("05:44", "06:00", True),    # whole time compared: 05:44 is before 06:00
    ("06:00", "06:00", True),
    ("06:01", "06:00", False),
    ("07:00", "06:30", False),
    ("23:59", "05:00", False),
])
def test_delay_at_most_the_morning_start(model, delay, morning_start, allowed):
    data = _form("123456", shift_delay=delay, morning_collection_start=morning_start)
    if allowed:
        assert model.model_validate(data).shift_delay == delay
    else:
        with pytest.raises(ValueError, match="cannot be more than the morning shift start time"):
            model.model_validate(data)


@pytest.mark.parametrize("mcc_type", list(MccType))
def test_every_type_keeps_its_delay(mcc_type):
    form = _form("123456", mcc_type=str(int(mcc_type)), shift_delay="05:44", sample_start="1", sample_end="100")
    assert CreateMccRequest.model_validate(form).shift_delay == "05:44"
    assert UpdateMccRequest.model_validate(form).shift_delay == "05:44"


async def _mcc(
    database, admin: UUID, *, shift_delay: str = "00:00", morning_end: str = "10:00", mcc_type: MccType = MccType.FAT_SNF,
) -> tuple[UUID, UUID]:
    user_id = await create_user(database, role=Role.MCC, created_by=admin, name="Delay MCC")
    mcc_id, settings_id = uuid4(), uuid4()
    async with database.transaction() as session:
        session.add(SettingsModel(id=settings_id, morning_collection_end=morning_end))
        await session.flush()
        session.add(MccModel(
            id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name="Delay MCC", mcc_type=mcc_type,
            created_by=admin, settings_id=settings_id, shift_delay=shift_delay,
        ))
    return user_id, mcc_id


async def test_existing_mccs_have_no_delay(database):
    admin = await create_user(database, role=Role.ADMIN)
    user_id = await create_user(database, role=Role.MCC, created_by=admin)
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(id=mcc_id, user_id=user_id, code=f"M{mcc_id.hex[:6]}", name="Old", mcc_type=MccType.NORMAL, created_by=admin))
    assert await _stored_delay(database, mcc_id) == "00:00"


async def test_sync_reports_the_delay(api, database):
    admin = await create_user(database, role=Role.ADMIN)
    user_id, mcc_id = await _mcc(database, admin, shift_delay="05:44")
    token = JWTService(secret_key=settings.SECRET_KEY).create_access_token(
        str(user_id), {"role": str(int(Role.MCC)), "name": "MCC", "own_id": str(mcc_id)}
    )

    response = await api.get("/api/v1/sync/", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200, response.text
    assert response.json()["mcc_info"]["shift_delay"] == "05:44"


async def test_a_normal_mcc_uses_its_delay(api, database, token_for, monkeypatch):
    admin = await create_user(database, role=Role.ADMIN)
    _, mcc_id = await _mcc(database, admin, shift_delay="05:44", mcc_type=MccType.NORMAL)
    _freeze(monkeypatch, "mcc_collection", datetime(2026, 11, 14, 10, 44, 0))

    page = (await api.get("/mcc-collections/load-form", params={"mcc_id": str(mcc_id)},
                          headers=token_for(admin, Role.ADMIN) | HTML)).text

    assert 'data-live-clock="2026-11-14T05:00:00"' in page


@pytest.mark.parametrize("mcc_type", list(MccType))
async def test_mcc_form_shows_the_field_for_every_type(api, database, token_for, mcc_type):
    admin = await create_user(database, role=Role.ADMIN)
    _, mcc_id = await _mcc(database, admin, shift_delay="05:44", mcc_type=mcc_type)

    page = (await api.get(f"/mcc/edit/{mcc_id}", headers=token_for(admin, Role.ADMIN) | HTML)).text

    card = re.search(r'id="field-shift-delay" style="([^"]*)"', page).group(1)
    field = re.search(r'<input[^>]*id="shift-delay"[^>]*>', page, re.S).group(0)
    assert "display:none" not in card and "disabled" not in field
    assert 'value="05:44"' in field


# =========================================================
# Web collection entry
# =========================================================

def _freeze(monkeypatch, module: str, at: datetime) -> None:
    monkeypatch.setattr(f"app.web.{module}.controller.now_naive_ist", lambda: at)


def _mcc_entry(mcc_id: UUID, vlcc_id: UUID, **extra) -> dict:
    return {"mcc_id": str(mcc_id), "vlcc_id": str(vlcc_id), "milk_type": "0", "fat_percent": "4.0",
            "snf_percent": "8.5", "quantity": "10", "rate_per_unit": "40", "mcc_type": "1", "status": "0", **extra}


async def test_mcc_entry_is_stamped_now_minus_delay(api, database, token_for, monkeypatch):
    admin = await create_user(database, role=Role.ADMIN)
    _, mcc_id = await _mcc(database, admin, shift_delay="05:20")
    vlcc = await create_vlcc(database, created_by=admin)
    _freeze(monkeypatch, "mcc_collection", datetime(2026, 10, 11, 0, 30, 15))

    # Whatever date and shift the browser sends are ignored
    response = await api.post(
        "/mcc-collections/create",
        data=_mcc_entry(mcc_id, vlcc.id, collection_date="2030-01-01T09:00", shift="0"),
        headers=token_for(admin, Role.ADMIN) | HTML,
    )

    assert response.status_code == 200, response.text
    async with database.transaction() as session:
        row = (await session.execute(
            select(MccCollectionModel.collected_at, MccCollectionModel.shift).where(MccCollectionModel.mcc_id == mcc_id)
        )).one()
    assert row.collected_at == datetime(2026, 10, 10, 19, 10, 15)
    assert row.shift == CollectionShift.EVENING
    # The next entry's form shows the live clock again
    assert 'data-live-clock="2026-10-10T19:10:15"' in response.text


async def test_mcc_form_shows_the_delayed_clock_read_only(api, database, token_for, monkeypatch):
    admin = await create_user(database, role=Role.ADMIN)
    _, mcc_id = await _mcc(database, admin, shift_delay="05:44", morning_end="10:00")
    _freeze(monkeypatch, "mcc_collection", datetime(2026, 11, 14, 10, 44, 0))

    page = (await api.get("/mcc-collections/load-form", params={"mcc_id": str(mcc_id)},
                          headers=token_for(admin, Role.ADMIN) | HTML)).text

    assert 'data-live-clock="2026-11-14T05:00:00"' in page
    assert 'data-morning-end="10:00"' in page
    assert 'id="cf-date" class="form-control cf-locked" required readonly' in page
    assert '<option value="0" selected>Morning</option>' in page


async def test_mcc_edit_page_shows_the_stored_date_and_shift(api, database, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    _, mcc_id = await _mcc(database, admin, shift_delay="05:20")
    vlcc = await create_vlcc(database, created_by=admin)
    collection_id = uuid4()
    async with database.transaction() as session:
        session.add(MccCollectionModel(
            id=collection_id, mcc_id=mcc_id, vlcc_id=vlcc.id, shift=CollectionShift.EVENING,
            milk_type=MilkType.COW, quantity=Decimal("5"), collected_at=datetime(2026, 11, 1, 19, 15, 0),
        ))

    page = (await api.get(f"/mcc-collections/edit/{collection_id}", headers=token_for(admin, Role.ADMIN) | HTML)).text

    # Saving an edit goes to the edit route, never to create (which would add a second entry)
    assert f'hx-post="/mcc-collections/edit/{collection_id}"' in page
    assert 'value="2026-11-01T19:15:00"' in page and "data-live-clock" not in page
    assert '<option value="1" selected>Evening</option>' in page


async def _vlcc_with_farmer(database, admin: UUID, morning_end: str):
    vlcc = await create_vlcc(database, created_by=admin)
    settings_id = uuid4()
    async with database.transaction() as session:
        session.add(SettingsModel(id=settings_id, morning_collection_end=morning_end))
        await session.flush()
        await session.execute(update(VlccModel).where(VlccModel.id == vlcc.id).values(settings_id=settings_id))
    await create_farmers(database, vlcc, 1, prefix=f"S{vlcc.id.hex[:4]}")
    async with database.transaction() as session:
        farmer_id = await session.scalar(select(FarmerModel.id).where(FarmerModel.vlcc_id == vlcc.id))
    return vlcc, farmer_id


def _vlcc_entry(vlcc_id: UUID, farmer_id: UUID, **extra) -> dict:
    return {"vlcc_id": str(vlcc_id), "farmer_id": str(farmer_id), "milk_type": "0", "fat_percent": "4.0",
            "snf_percent": "8.5", "quantity": "10", "rate_per_unit": "40", "status": "0", **extra}


async def _vlcc_row(database, vlcc_id: UUID):
    async with database.transaction() as session:
        return (await session.execute(
            select(VlccCollectionModel.id, VlccCollectionModel.collected_at, VlccCollectionModel.shift,
                   VlccCollectionModel.quantity).where(VlccCollectionModel.vlcc_id == vlcc_id)
        )).one()


async def test_vlcc_entry_uses_now_and_the_vlcc_shifts(api, database, token_for, monkeypatch):
    admin = await create_user(database, role=Role.ADMIN)
    vlcc, farmer_id = await _vlcc_with_farmer(database, admin, morning_end="09:00")
    _freeze(monkeypatch, "vlcc_collection", datetime(2026, 11, 14, 9, 30, 5))

    response = await api.post(
        "/vlcc-collections/create",
        data=_vlcc_entry(vlcc.id, farmer_id, collection_date="2030-01-01T06:00", shift="0"),
        headers=token_for(admin, Role.ADMIN) | HTML,
    )

    assert response.status_code == 200, response.text
    row = await _vlcc_row(database, vlcc.id)
    # 09:30 is after this VLCC's morning end (09:00): Evening, at the real time (no delay)
    assert (row.collected_at, row.shift) == (datetime(2026, 11, 14, 9, 30, 5), CollectionShift.EVENING)
    # The next entry's form ticks from the server's clock, with the VLCC's morning end
    assert 'data-live-clock="2026-11-14T09:30:05"' in response.text
    assert 'data-morning-end="09:00"' in response.text
