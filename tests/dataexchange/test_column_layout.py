"""
Collection export column order (Plan 24.2, REQ-55, REQ-56, REQ-57, DECISION-030).

- the layout rules (normalise, request validation)
- who may read / change whose order through /api/v1/excel/column-layouts/collections
- which user's order each export follows, through a real ExchangeWorker
"""

from __future__ import annotations

import pytest
from sqlalchemy import update

from app.middleware.authentication import CurrentUser
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.dataexchange.domain.column_layout import ColumnLayout
from app.modules.dataexchange.domain.exceptions import ColumnLayoutInvalidException
from app.modules.dataexchange.domain.sheets import COLLECTION_COLUMN_KEYS, CollectionSheet, collection_columns
from app.modules.dataexchange.infrastructure.column_layout_repository import ColumnLayoutRepository
from tests.dataexchange.factories import create_user
from tests.dataexchange.test_collection_export import (  # noqa: F401  (fixtures)
    MCC_EXPORT,
    MCC_HEADERS,
    VLCC_EXPORT,
    VLCC_HEADERS,
    _empty_job_table,
    _export,
    scene,
    worker,
)

LAYOUT = "/api/v1/excel/column-layouts/collections"

# Deleted and Quantity first, Time / MCC Name / Farmer Name hidden, the rest in the default order
CUSTOM_KEYS = ["deleted", "quantity", *[
    key for key in COLLECTION_COLUMN_KEYS if key not in ("deleted", "quantity")
]]
HIDDEN = {"time", "mcc_name", "farmer_name"}
CUSTOM = [{"key": key, "visible": key not in HIDDEN} for key in CUSTOM_KEYS]


def _headers(sheet: CollectionSheet, keys: list[str] = CUSTOM_KEYS, hidden: set[str] = HIDDEN) -> list[str]:
    return [column.header for column in collection_columns(sheet, [key for key in keys if key not in hidden])]


# =========================================================
# LAYOUT RULES
# =========================================================

def test_normalise_drops_unknown_and_repeated_keys_and_restores_missing_ones():
    layout = ColumnLayout.normalise([
        {"key": "deleted"}, {"key": "nope"}, {"key": "date", "visible": False}, {"key": "date"}, "junk",
    ])
    keys = [item.key for item in layout.items]
    assert keys[:3] == ["deleted", "date", "time"]                # time comes back right after date
    assert sorted(keys) == sorted(COLLECTION_COLUMN_KEYS)       # every column exactly once
    assert not layout.items[1].visible                          # the first "date" wins
    assert not layout.is_default


def test_a_new_catalogue_column_lands_after_its_default_predecessor():
    stored = [{"key": key} for key in COLLECTION_COLUMN_KEYS if key != "chart_rank"][::-1]
    keys = [item.key for item in ColumnLayout.normalise(stored).items]
    assert keys[keys.index("measurement_mode") + 1] == "chart_rank"


def test_no_row_is_the_default():
    layout = ColumnLayout.normalise(None)
    assert layout.is_default and [item.key for item in layout.items] == list(COLLECTION_COLUMN_KEYS)
    assert [column.header for column in layout.columns_for(CollectionSheet.MCC)] == MCC_HEADERS
    assert [column.header for column in layout.columns_for(CollectionSheet.VLCC)] == VLCC_HEADERS


def test_request_rejects_unknown_repeated_and_empty_sheets():
    with pytest.raises(ColumnLayoutInvalidException):
        ColumnLayout.from_request([("date", True), ("hacker", True)])
    with pytest.raises(ColumnLayoutInvalidException):
        ColumnLayout.from_request([("date", True), ("date", False)])
    # Only a VLCC-only column visible: the MCC export would have no column
    only_farmer = [(key, key == "farmer_code") for key in COLLECTION_COLUMN_KEYS]
    with pytest.raises(ColumnLayoutInvalidException, match="MCC"):
        ColumnLayout.from_request(only_farmer)


# =========================================================
# API: WHO MAY CHANGE WHOSE ORDER
# =========================================================

@pytest.fixture
async def people(database):
    super_admin = await create_user(database, role=Role.SUPER_ADMIN)
    admin = await create_user(database, role=Role.ADMIN)
    sub = await create_user(database, role=Role.SUB_ADMIN, created_by=admin)
    other_admin = await create_user(database, role=Role.ADMIN)
    other_sub = await create_user(database, role=Role.SUB_ADMIN, created_by=other_admin)
    return {
        "super": super_admin, "admin": admin, "sub": sub,
        "other_admin": other_admin, "other_sub": other_sub,
    }


async def test_own_order_starts_default_and_round_trips(api, token_for, people):
    headers = token_for(people["sub"], Role.SUB_ADMIN)

    first = (await api.get(LAYOUT, headers=headers)).json()["data"]
    assert first["is_default"] is True and first["user_id"] == str(people["sub"])
    assert [column["key"] for column in first["columns"]] == list(COLLECTION_COLUMN_KEYS)
    sample = next(column for column in first["columns"] if column["key"] == "sample_number")
    assert sample["sheets"] == ["mcc"] and sample["header"] == "Sample No"

    saved = await api.put(LAYOUT, json={"columns": CUSTOM}, headers=headers)
    assert saved.status_code == 200, saved.text
    again = (await api.get(LAYOUT, headers=headers)).json()["data"]
    assert again["is_default"] is False
    assert [(column["key"], column["visible"]) for column in again["columns"]] == [
        (item["key"], item["visible"]) for item in CUSTOM
    ]

    reset = (await api.delete(LAYOUT, headers=headers)).json()["data"]
    assert reset["is_default"] is True
    assert (await api.get(LAYOUT, headers=headers)).json()["data"]["is_default"] is True


@pytest.mark.parametrize(("actor", "role", "target", "status"), [
    ("super", Role.SUPER_ADMIN, "admin", 200),
    ("super", Role.SUPER_ADMIN, "other_sub", 200),
    ("admin", Role.ADMIN, "sub", 200),
    ("admin", Role.ADMIN, "other_sub", 404),        # another Admin's Sub Admin
    ("admin", Role.ADMIN, "other_admin", 404),
    ("admin", Role.ADMIN, "super", 404),
    ("sub", Role.SUB_ADMIN, "admin", 404),          # never upwards
    ("other_sub", Role.SUB_ADMIN, "sub", 404),
])
async def test_who_may_manage_whom(api, token_for, people, actor, role, target, status):
    headers = token_for(people[actor], role)
    params = {"user_id": str(people[target])}

    assert (await api.get(LAYOUT, params=params, headers=headers)).status_code == status
    response = await api.put(LAYOUT, params=params, json={"columns": CUSTOM}, headers=headers)
    assert response.status_code == status
    assert (await api.delete(LAYOUT, params=params, headers=headers)).status_code == status
    if status == 200:
        assert response.json()["data"]["user_id"] == str(people[target])


async def test_a_manager_change_lands_on_the_target_not_on_itself(api, token_for, people):
    admin = token_for(people["admin"], Role.ADMIN)
    await api.put(LAYOUT, params={"user_id": str(people["sub"])}, json={"columns": CUSTOM}, headers=admin)

    assert (await api.get(LAYOUT, headers=admin)).json()["data"]["is_default"] is True
    sub = (await api.get(LAYOUT, headers=token_for(people["sub"], Role.SUB_ADMIN))).json()["data"]
    assert sub["is_default"] is False


@pytest.mark.parametrize("role", [Role.MCC, Role.VLCC, Role.FARMER])
async def test_mcc_vlcc_and_farmer_have_no_order_of_their_own(api, token_for, database, role):
    user = await create_user(database, role=role)
    headers = token_for(user, role)
    assert (await api.get(LAYOUT, headers=headers)).status_code == 403
    assert (await api.put(LAYOUT, json={"columns": CUSTOM}, headers=headers)).status_code == 403
    assert (await api.delete(LAYOUT, headers=headers)).status_code == 403


async def test_invalid_orders_are_422(api, token_for, people):
    headers = token_for(people["sub"], Role.SUB_ADMIN)
    all_hidden = [{"key": key, "visible": False} for key in COLLECTION_COLUMN_KEYS]
    assert (await api.put(LAYOUT, json={"columns": all_hidden}, headers=headers)).status_code == 422
    assert (await api.put(LAYOUT, json={"columns": [{"key": "nope"}]}, headers=headers)).status_code == 422
    assert (await api.put(LAYOUT, json={"columns": []}, headers=headers)).status_code == 422
    # Nothing was saved
    assert (await api.get(LAYOUT, headers=headers)).json()["data"]["is_default"] is True


# =========================================================
# EXPORTS FOLLOW THE OWNER'S ORDER
# =========================================================

async def test_every_export_in_the_sub_admins_line_follows_its_order(api, token_for, scene, worker):
    sub = token_for(scene["sub"], Role.SUB_ADMIN)
    assert (await api.put(LAYOUT, json={"columns": CUSTOM}, headers=sub)).status_code == 200
    mcc_headers, vlcc_headers = _headers(CollectionSheet.MCC), _headers(CollectionSheet.VLCC)

    # The Sub Admin itself
    rows, _ = await _export(api, sub, MCC_EXPORT)
    assert list(rows[0]) == mcc_headers
    assert "Time" not in rows[0] and "MCC Name" not in rows[0]
    assert rows[2]["Deleted"] == "Yes" and rows[2]["Quantity"] == 30          # cells follow their header
    rows, _ = await _export(api, sub, VLCC_EXPORT)
    assert list(rows[0]) == vlcc_headers

    # Its MCC (created by the Sub Admin)
    rows, _ = await _export(api, token_for(scene["m1_user"], Role.MCC), MCC_EXPORT)
    assert list(rows[0]) == mcc_headers
    # Its VLCC (created by the Sub Admin)
    rows, _ = await _export(api, token_for(scene["v1"].user_id, Role.VLCC), VLCC_EXPORT)
    assert list(rows[0]) == vlcc_headers
    # A VLCC created by the MCC's user follows the MCC's creator
    rows, _ = await _export(api, token_for(scene["v2"].user_id, Role.VLCC), VLCC_EXPORT)
    assert list(rows[0]) == vlcc_headers

    # Another Admin keeps the default
    rows, _ = await _export(api, token_for(scene["other"], Role.ADMIN), MCC_EXPORT)
    assert list(rows[0]) == MCC_HEADERS


async def test_reset_brings_the_default_back_to_the_exports(api, token_for, scene, worker):
    sub = token_for(scene["sub"], Role.SUB_ADMIN)
    await api.put(LAYOUT, json={"columns": CUSTOM}, headers=sub)
    await api.delete(LAYOUT, headers=sub)
    rows, _ = await _export(api, token_for(scene["m1_user"], Role.MCC), MCC_EXPORT)
    assert list(rows[0]) == MCC_HEADERS


async def test_layout_owner_walk(database, scene):
    layouts = ColumnLayoutRepository(database)

    async def owner_of(user_id, role):
        async with database.transaction():
            return await layouts.layout_owner(CurrentUser(id=user_id, role=role))

    assert await owner_of(scene["sub"], Role.SUB_ADMIN) == scene["sub"]
    assert await owner_of(scene["m1_user"], Role.MCC) == scene["sub"]
    assert await owner_of(scene["v1"].user_id, Role.VLCC) == scene["sub"]
    assert await owner_of(scene["v2"].user_id, Role.VLCC) == scene["sub"]       # VLCC -> MCC user -> Sub Admin
    assert await owner_of(scene["v1"].user_id, Role.FARMER) is None

    # A deleted owner -> the default layout
    async with database.transaction() as session:
        await session.execute(update(UserModel).where(UserModel.id == scene["sub"]).values(is_deleted=True))
    assert await owner_of(scene["m1_user"], Role.MCC) is None
