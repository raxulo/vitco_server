"""
Farmer exchange through HTTP + a real ExchangeWorker on the same test database (Plan 2.3).
"""

from __future__ import annotations

import asyncio
import contextvars
import io
import os
import time
from pathlib import Path

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete

from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.dataexchange.application.farmer_export import FarmerExportProcessor
from app.modules.dataexchange.application.farmer_import import FarmerImportProcessor
from app.modules.dataexchange.domain.sheets import FARMER_SHEET
from app.modules.dataexchange.infrastructure.farmer_repository import FarmerExchangeRepository
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.worker.exchange import ExchangeWorker
from tests.dataexchange.factories import create_farmers, create_vlcc, unique_mobile

COLUMNS = FARMER_SHEET.import_columns()


@pytest.fixture(autouse=True)
async def _empty_job_table(database):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


@pytest.fixture
async def worker(database):
    """The real worker loop with the farmer processors, sharing the app's job folder."""
    instance = ExchangeWorker(
        database=database, repository=ExcelJobRepository(database),
        storage=ExchangeStorage(Path(os.environ["EXCHANGE_PATH"]), max_upload_bytes=10 ** 9, min_free_bytes=0),
        max_concurrent=2, poll_interval_ms=20, tx_budget_ms=250, max_batch_size=500, batch_pause_ms=0,
        max_memory_mb=4096, heartbeat_interval_s=1,
    )
    farmers = FarmerExchangeRepository(database)
    instance.register(FarmerExportProcessor(database=database, repository=farmers))
    instance.register(FarmerImportProcessor(database=database, repository=farmers, password_service=PasswordService()))
    task = asyncio.create_task(instance.run(), context=contextvars.Context())
    yield instance
    instance.stop()
    await asyncio.wait_for(task, timeout=10)


async def _poll(api, headers, job_id, timeout=60.0) -> dict:
    deadline = time.monotonic() + timeout
    while True:
        data = (await api.get(f"/api/v1/excel/jobs/{job_id}", headers=headers)).json()["data"]
        if data["poll_after_ms"] is None:
            return data
        assert time.monotonic() < deadline, f"job still {data['status']['name']}"
        await asyncio.sleep(0.05)


def _workbook(rows: list[dict]) -> bytes:
    buffer_path = Path(os.environ["EXCHANGE_PATH"]) / f"tmp-{time.time_ns()}.xlsx"
    buffer_path.parent.mkdir(parents=True, exist_ok=True)
    writer = XlsxSheetWriter(buffer_path, FARMER_SHEET, columns=COLUMNS)
    writer.write_rows([[row.get(column.key) for column in COLUMNS] for row in rows])
    writer.close()
    data = buffer_path.read_bytes()
    buffer_path.unlink()
    return data


async def _upload(api, headers, data: bytes) -> str:
    response = await api.post("/api/v1/excel/uploads/single", headers=headers,
                              files={"file": ("farmers.xlsx", data, "application/octet-stream")})
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


# =========================================================
# OPTIONS / SCOPE
# =========================================================

async def test_vlcc_login_gets_only_its_own_vlcc_locked(api, database, token_for):
    vlcc = await create_vlcc(database)
    await create_vlcc(database)                          # someone else's

    body = (await api.get("/api/v1/excel/options/vlccs", headers=token_for(vlcc.user_id, Role.VLCC))).json()

    assert body["locked"] is True and body["default_id"] == str(vlcc.id)
    assert [item["id"] for item in body["items"]] == [str(vlcc.id)] and body["total"] == 1


async def test_admin_sees_its_hierarchy_with_search_and_super_admin_sees_all(api, database, api_user, token_for):
    admin_id, admin_headers = await api_user(Role.ADMIN)
    mine = [await create_vlcc(database, created_by=admin_id) for _ in range(3)]
    other = await create_vlcc(database)
    super_id, super_headers = await api_user(Role.SUPER_ADMIN)

    admin_body = (await api.get("/api/v1/excel/options/vlccs", headers=admin_headers, params={"limit": 2})).json()
    searched = (await api.get("/api/v1/excel/options/vlccs", headers=admin_headers, params={"search": mine[1].code})).json()
    super_ids = {item["id"] for item in (await api.get(
        "/api/v1/excel/options/vlccs", headers=super_headers, params={"limit": 100, "search": other.code})).json()["items"]}

    assert admin_body["locked"] is False and admin_body["total"] == 3
    assert (len(admin_body["items"]), admin_body["has_more"], admin_body["next_page"]) == (2, True, 2)
    assert [item["id"] for item in searched["items"]] == [str(mine[1].id)]
    assert str(other.id) in super_ids


async def test_farmer_login_is_forbidden(api, api_user):
    _, headers = await api_user(Role.FARMER)

    response = await api.get("/api/v1/excel/options/vlccs", headers=headers)

    assert response.status_code == 403
    assert response.json()["error"]["code"] == "EXCEL_EXCHANGE_FORBIDDEN"


async def test_vlcc_login_cannot_export_another_vlcc(api, database, token_for):
    mine = await create_vlcc(database)
    other = await create_vlcc(database)

    response = await api.post("/api/v1/excel/farmers/export", headers=token_for(mine.user_id, Role.VLCC),
                              json={"vlcc_id": str(other.id)})

    assert response.status_code == 202
    assert response.json()["data"]["target_id"] == str(mine.id)      # forced to its own VLCC


async def test_admin_out_of_scope_vlcc_is_404_and_missing_vlcc_is_422(api, database, api_user):
    _, headers = await api_user(Role.ADMIN)
    stranger = await create_vlcc(database)

    out_of_scope = await api.post("/api/v1/excel/farmers/export", headers=headers, json={"vlcc_id": str(stranger.id)})
    missing = await api.post("/api/v1/excel/farmers/export", headers=headers, json={})

    assert out_of_scope.status_code == 404 and out_of_scope.json()["error"]["code"] == "EXCEL_TARGET_NOT_FOUND"
    assert missing.status_code == 422 and missing.json()["error"]["code"] == "EXCEL_TARGET_REQUIRED"


async def test_import_without_farmer_permission_is_403(api, database, token_for):
    vlcc = await create_vlcc(database, farmer_enabled=False)
    headers = token_for(vlcc.user_id, Role.VLCC)
    upload_id = await _upload(api, headers, _workbook([{"farmer_code": "F1", "name": "A", "mobile": unique_mobile()}]))

    response = await api.post("/api/v1/excel/farmers/import", headers=headers, json={"upload_id": upload_id})

    assert response.status_code == 403
    assert "Farmer permission is not enabled" in response.json()["error"]["message"]


async def test_second_export_while_one_is_queued_is_409_with_job_id(api, database, token_for):
    vlcc = await create_vlcc(database)
    headers = token_for(vlcc.user_id, Role.VLCC)

    first = await api.post("/api/v1/excel/farmers/export", headers=headers, json={})
    second = await api.post("/api/v1/excel/farmers/export", headers=headers, json={})

    assert first.status_code == 202
    assert second.status_code == 409 and second.headers["retry-after"] == "30"
    assert second.json()["error"]["details"]["job_id"] == first.json()["data"]["id"]


# =========================================================
# END TO END
# =========================================================

async def test_import_end_to_end_with_discarded_rows_report(api, database, token_for, worker):
    vlcc = await create_vlcc(database)
    headers = token_for(vlcc.user_id, Role.VLCC)
    mobile = unique_mobile()
    rows = [{"farmer_code": f"E{i:03d}", "name": f"Farmer {i}", "mobile": unique_mobile()} for i in range(50)]
    rows += [{"farmer_code": "DUP", "name": "A", "mobile": mobile}, {"farmer_code": "DUP2", "name": "B", "mobile": mobile},
             {"farmer_code": "BAD", "name": "C", "mobile": "123"}]
    upload_id = await _upload(api, headers, _workbook(rows))

    queued = await api.post("/api/v1/excel/farmers/import", headers=headers, json={"upload_id": upload_id})
    assert queued.status_code == 202, queued.text
    done = await _poll(api, headers, queued.json()["data"]["id"])
    report = await api.get(f"/api/v1/excel/jobs/{done['id']}/file", headers=headers)

    assert done["status"]["name"] == "COMPLETED"
    assert (done["inserted"], done["updated"], done["discarded"], done["processed_rows"]) == (51, 0, 2, 53)
    assert report.status_code == 200 and "discarded_rows" in report.headers["content-disposition"]
    lines = list(load_workbook(io.BytesIO(report.content), read_only=True)["Farmers"].iter_rows(min_row=2, values_only=True))
    assert [(line[0], line[-2], line[-1]) for line in lines] == [
        ("DUP2", 53, "Mobile repeats row 52"), ("BAD", 54, "Mobile: must be exactly 10 digits"),
    ]
    reused = await api.post("/api/v1/excel/farmers/import", headers=headers, json={"upload_id": upload_id})
    assert reused.status_code == 404                     # an upload is consumed by its import

    again = await api.post("/api/v1/excel/farmers/import", headers=headers,
                           json={"upload_id": await _upload(api, headers, _workbook(rows))})
    second = await _poll(api, headers, again.json()["data"]["id"])
    assert (second["inserted"], second["updated"], second["unchanged"], second["discarded"]) == (0, 0, 51, 2)


async def test_export_end_to_end_matches_the_database(api, database, token_for, worker):
    vlcc = await create_vlcc(database)
    farmers = await create_farmers(database, vlcc, 1200, prefix="X")
    headers = token_for(vlcc.user_id, Role.VLCC)

    queued = await api.post("/api/v1/excel/farmers/export", headers=headers, json={})
    done = await _poll(api, headers, queued.json()["data"]["id"])
    download = await api.get(f"/api/v1/excel/jobs/{done['id']}/file", headers=headers)

    assert done["status"]["name"] == "COMPLETED" and done["processed_rows"] == 1200 and done["progress"] == 100
    sheet = load_workbook(io.BytesIO(download.content), read_only=True)["Farmers"]
    codes = [row[0] for row in sheet.iter_rows(min_row=2, values_only=True)]
    assert codes == [farmer["farmer_code"] for farmer in farmers]


async def test_template_download(api, api_user):
    _, headers = await api_user(Role.ADMIN)

    response = await api.get("/api/v1/excel/farmers/template", headers=headers)

    assert response.status_code == 200 and response.headers["content-encoding"] == "identity"
    header = next(load_workbook(io.BytesIO(response.content), read_only=True)["Farmers"].iter_rows(max_row=1, values_only=True))
    assert header[:3] == ("Farmer Code *", "Milk Type", "Rate Chart Rank") and "Password" in header
