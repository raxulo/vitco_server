"""
Collection Excel export through HTTP + a real ExchangeWorker (Plan 21.1, REQ-48, REQ-49).

The file must hold exactly the entries the user's list shows for the same filters:
nothing from another Admin's tree, no deleted entries, oldest first.
"""

from __future__ import annotations

import asyncio
import contextvars
import io
import os
import time
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, select

from app.modules.administration.domain.enums import Role
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from app.modules.collections.mcc_collection.infrastructure.models import MccCollectionModel
from app.modules.collections.mcc_collection.infrastructure.repository import MccCollectionRepository
from app.modules.collections.vlcc_collection.infrastructure.models import VlccCollectionModel
from app.modules.collections.vlcc_collection.infrastructure.repository import VlccCollectionRepository
from app.modules.dataexchange.application.collection_export import (
    MccCollectionExportProcessor,
    VlccCollectionExportProcessor,
)
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.mcc.domain.enums import MccType
from app.modules.mcc.infrastructure.models import MccModel
from app.modules.ratechart.domain.enums import MilkType
from app.worker.exchange import ExchangeWorker
from tests.dataexchange.factories import create_farmers, create_user, create_vlcc

MCC_EXPORT = "/api/v1/excel/mcc-collections/export"
VLCC_EXPORT = "/api/v1/excel/vlcc-collections/export"

DAY1_MORNING = datetime(2026, 1, 5, 7, 0)
DAY1_EVENING = datetime(2026, 1, 5, 18, 0)
DAY2_MORNING = datetime(2026, 1, 6, 7, 0)
DAY3_MORNING = datetime(2026, 1, 7, 7, 0)


@pytest.fixture(autouse=True)
async def _empty_job_table(database):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


@pytest.fixture
async def worker(database):
    storage = ExchangeStorage(Path(os.environ["EXCHANGE_PATH"]), max_upload_bytes=10 ** 9, min_free_bytes=0)
    instance = ExchangeWorker(
        database=database,
        repository=ExcelJobRepository(database),
        storage=storage,
        max_concurrent=2,
        poll_interval_ms=20,
        tx_budget_ms=250,
        max_batch_size=500,
        batch_pause_ms=0,
        max_memory_mb=4096,
        heartbeat_interval_s=1,
    )
    # A small page size so the keyset paging crosses several pages
    instance.register(MccCollectionExportProcessor(
        database=database, repository=MccCollectionRepository(database), storage=storage, page_size=2,
    ))
    instance.register(VlccCollectionExportProcessor(
        database=database, repository=VlccCollectionRepository(database), storage=storage, page_size=2,
    ))
    task = asyncio.create_task(instance.run(), context=contextvars.Context())
    yield instance
    instance.stop()
    await asyncio.wait_for(task, timeout=10)


# =========================================================
# SCENE
# =========================================================

async def _mcc(database, created_by: UUID) -> tuple[UUID, UUID]:
    user_id = await create_user(database, role=Role.MCC, created_by=created_by, name="MCC User")
    mcc_id = uuid4()
    async with database.transaction() as session:
        session.add(MccModel(
            id=mcc_id, user_id=user_id, code=str(uuid4().int)[:6], name=f"MCC {mcc_id.hex[:4]}",
            mcc_type=MccType.NORMAL, created_by=created_by,
        ))
    return user_id, mcc_id


async def _farmer_id(database, vlcc) -> UUID:
    await create_farmers(database, vlcc, 1, prefix=f"F{vlcc.code}")
    async with database.transaction() as session:
        return await session.scalar(select(FarmerModel.id).where(FarmerModel.vlcc_id == vlcc.id))


def _mcc_entry(mcc_id, vlcc_id, sample, at, shift, milk, qty, deleted=False) -> MccCollectionModel:
    return MccCollectionModel(
        id=uuid4(), mcc_id=mcc_id, vlcc_id=vlcc_id, sample_number=sample, can_count=1, shift=shift,
        milk_type=milk, quantity=Decimal(qty), fat_percent=Decimal("4.0"), snf_percent=Decimal("8.5"),
        rate_per_unit=Decimal("40"), total_amount=Decimal(qty) * 40, collected_at=at, is_deleted=deleted,
    )


def _vlcc_entry(vlcc_id, farmer_id, at, shift, qty, deleted=False) -> VlccCollectionModel:
    return VlccCollectionModel(
        id=uuid4(), vlcc_id=vlcc_id, farmer_id=farmer_id, milk_type=MilkType.COW, shift=shift,
        quantity=Decimal(qty), fat_percent=Decimal("4.2"), snf_percent=Decimal("8.5"),
        rate_per_unit=Decimal("40"), total_amount=Decimal(qty) * 40, collected_at=at, is_deleted=deleted,
    )


@pytest.fixture
async def scene(database):
    """
    Sub Admin S (under Admin A) with MCC m1, VLCC v1 (made by S) and VLCC v2 (made by m1's user).
    Another Admin O has MCC m2 and VLCC v3, which S must never see.
    """
    admin = await create_user(database, role=Role.ADMIN)
    sub = await create_user(database, role=Role.SUB_ADMIN, created_by=admin)
    other = await create_user(database, role=Role.ADMIN)
    m1_user, m1 = await _mcc(database, sub)
    _, m2 = await _mcc(database, other)
    v1 = await create_vlcc(database, created_by=sub)
    v2 = await create_vlcc(database, created_by=m1_user)
    v3 = await create_vlcc(database, created_by=other)
    f1, f2, f3 = [await _farmer_id(database, vlcc) for vlcc in (v1, v2, v3)]

    async with database.transaction() as session:
        session.add_all([
            _mcc_entry(m1, v1.id, 1, DAY1_MORNING, CollectionShift.MORNING, MilkType.COW, "10"),
            _mcc_entry(m1, v1.id, 2, DAY1_EVENING, CollectionShift.EVENING, MilkType.BUFFALO, "20"),
            _mcc_entry(m1, v1.id, 3, DAY2_MORNING, CollectionShift.MORNING, MilkType.COW, "30", deleted=True),
            _mcc_entry(m1, v2.id, 4, DAY3_MORNING, CollectionShift.MORNING, MilkType.COW, "40"),
            _mcc_entry(m2, v3.id, 1, DAY1_MORNING, CollectionShift.MORNING, MilkType.COW, "99"),
            _vlcc_entry(v1.id, f1, DAY1_MORNING, CollectionShift.MORNING, "5"),
            _vlcc_entry(v1.id, f1, DAY2_MORNING, CollectionShift.EVENING, "6"),
            _vlcc_entry(v1.id, f1, DAY2_MORNING, CollectionShift.MORNING, "7", deleted=True),
            _vlcc_entry(v2.id, f2, DAY3_MORNING, CollectionShift.MORNING, "8"),
            _vlcc_entry(v3.id, f3, DAY1_MORNING, CollectionShift.MORNING, "9"),
        ])
    return {"sub": sub, "other": other, "m1_user": m1_user, "m1": m1, "v1": v1, "v2": v2}


# =========================================================
# HELPERS
# =========================================================

async def _export(api, headers, path: str, filters: dict | None = None) -> tuple[list[dict], dict]:
    response = await api.post(path, json=filters or {}, headers=headers)
    assert response.status_code == 202, response.text
    job_id = response.json()["data"]["id"]

    deadline = time.monotonic() + 60
    while True:
        job = (await api.get(f"/api/v1/excel/jobs/{job_id}", headers=headers)).json()["data"]
        if job["poll_after_ms"] is None:
            break
        assert time.monotonic() < deadline, f"job still {job['status']['name']}"
        await asyncio.sleep(0.05)
    assert job["status"]["name"] == "COMPLETED", job.get("error_message")

    file = await api.get(f"/api/v1/excel/jobs/{job_id}/file", headers=headers)
    assert file.status_code == 200
    workbook = load_workbook(io.BytesIO(file.content), read_only=True)
    data_sheet, summary_sheet = workbook.worksheets[0], workbook["Summary"]
    header, *body = list(data_sheet.iter_rows(values_only=True))
    rows = [dict(zip(header, values)) for values in body]
    summary = {label: value for label, value, *_ in summary_sheet.iter_rows(min_row=3, values_only=True) if label}
    return rows, summary


# =========================================================
# MCC COLLECTIONS
# =========================================================

async def test_sub_admin_gets_its_line_without_deleted_oldest_first(api, token_for, scene, worker):
    rows, summary = await _export(api, token_for(scene["sub"], Role.SUB_ADMIN), MCC_EXPORT)

    assert [row["Quantity"] for row in rows] == [10, 20, 40]          # no deleted 30, no other Admin's 99
    assert [row["Sample No"] for row in rows] == [1, 2, 4]
    assert [row["Shift"] for row in rows] == ["Morning", "Evening", "Morning"]
    assert rows[1]["Milk Type"] == "Buffalo" and rows[1]["Amount"] == 800
    assert rows[0]["Date"] == datetime(2026, 1, 5)                   # a real Excel date
    assert rows[2]["VLCC Code"] == scene["v2"].code
    assert summary["Entries"] == 3
    assert summary["Total Quantity"] == 70
    assert summary["MCC"] == "All"


async def test_mcc_login_gets_only_its_own_centre(api, token_for, scene, worker):
    rows, _ = await _export(api, token_for(scene["m1_user"], Role.MCC), MCC_EXPORT)
    assert [row["Quantity"] for row in rows] == [10, 20, 40]


async def test_another_admin_never_sees_the_sub_admins_entries(api, token_for, scene, worker):
    rows, _ = await _export(api, token_for(scene["other"], Role.ADMIN), MCC_EXPORT)
    assert [row["Quantity"] for row in rows] == [99]


async def test_filters_match_the_list(api, token_for, scene, worker):
    headers = token_for(scene["sub"], Role.SUB_ADMIN)

    cow, _ = await _export(api, headers, MCC_EXPORT, {"milk_type": "0"})
    assert [row["Quantity"] for row in cow] == [10, 40]

    # Day 1 evening to day 1 evening: a shift with its date is a boundary of the range
    evening, summary = await _export(api, headers, MCC_EXPORT, {
        "date_from": "2026-01-05", "date_to": "2026-01-05", "start_shift": "1", "end_shift": "1",
    })
    assert [row["Quantity"] for row in evening] == [20]
    assert summary["From"] == "05-01-2026 Evening"

    one_vlcc, summary = await _export(api, headers, MCC_EXPORT, {"vlcc_id": str(scene["v2"].id), "search": ""})
    assert [row["Quantity"] for row in one_vlcc] == [40]
    assert summary["VLCC"].startswith(scene["v2"].code)


async def test_filters_outside_the_scope_give_an_empty_file(api, database, token_for, scene, worker):
    """Choosing another tree's MCC never widens the scope."""
    async with database.transaction() as session:
        foreign_mcc = await session.scalar(select(MccModel.id).where(MccModel.created_by == scene["other"]))
    rows, summary = await _export(api, token_for(scene["sub"], Role.SUB_ADMIN), MCC_EXPORT, {"mcc_id": str(foreign_mcc)})
    assert rows == []
    assert summary["Entries"] == 0


async def test_farmer_cannot_export_mcc_collections(api, token_for, database):
    farmer = await create_user(database, role=Role.FARMER)
    response = await api.post(MCC_EXPORT, json={}, headers=token_for(farmer, Role.FARMER))
    assert response.status_code == 403


async def test_bad_filter_values_are_rejected(api, token_for, scene):
    response = await api.post(MCC_EXPORT, json={"milk_type": "7"}, headers=token_for(scene["sub"], Role.SUB_ADMIN))
    assert response.status_code == 422


# =========================================================
# VLCC COLLECTIONS
# =========================================================

async def test_vlcc_collections_for_sub_admin_and_mcc(api, token_for, scene, worker):
    rows, summary = await _export(api, token_for(scene["sub"], Role.SUB_ADMIN), VLCC_EXPORT)
    assert [row["Quantity"] for row in rows] == [5, 6, 8]             # v1 + v2, no deleted 7, no v3
    assert rows[0]["Farmer Code"] and rows[0]["VLCC Code"] == scene["v1"].code
    assert summary["Entries"] == 3

    mcc_rows, _ = await _export(api, token_for(scene["m1_user"], Role.MCC), VLCC_EXPORT)
    assert [row["Quantity"] for row in mcc_rows] == [8]               # only the VLCC its user made


async def test_vlcc_login_gets_its_own_entries(api, token_for, scene, worker):
    rows, _ = await _export(api, token_for(scene["v1"].user_id, Role.VLCC), VLCC_EXPORT, {"vlcc_id": str(scene["v2"].id)})
    # The VLCC filter cannot reach another VLCC: the scope still applies
    assert rows == []
    own, _ = await _export(api, token_for(scene["v1"].user_id, Role.VLCC), VLCC_EXPORT)
    assert [row["Quantity"] for row in own] == [5, 6]
