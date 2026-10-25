"""
Prodata Rate-Chart Exchange HTTP API Tests with real ExchangeWorker (Plan 4.2).
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
from app.modules.dataexchange.application.prodata_export import ProdataExportProcessor
from app.modules.dataexchange.application.prodata_import import ProdataImportProcessor
from app.modules.dataexchange.domain.sheets import PRODATA_SHEET
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.prodata_repository import ProdataExchangeRepository
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.modules.ratechart.infrastructure.models import ProdataRateRowModel
from app.worker.exchange import ExchangeWorker
from tests.dataexchange.factories import create_prodata_chart, create_prodata_rows, create_user

COLUMNS = PRODATA_SHEET.import_columns()


@pytest.fixture(autouse=True)
async def _empty_job_table(database):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


@pytest.fixture
async def worker(database):
    """The real worker loop with Prodata processors."""
    instance = ExchangeWorker(
        database=database,
        repository=ExcelJobRepository(database),
        storage=ExchangeStorage(Path(os.environ["EXCHANGE_PATH"]), max_upload_bytes=10 ** 9, min_free_bytes=0),
        max_concurrent=2,
        poll_interval_ms=20,
        tx_budget_ms=250,
        max_batch_size=500,
        batch_pause_ms=0,
        max_memory_mb=4096,
        heartbeat_interval_s=1,
    )
    repo = ProdataExchangeRepository(database)
    instance.register(ProdataExportProcessor(database=database, repository=repo))
    instance.register(ProdataImportProcessor(database=database, repository=repo))
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
    writer = XlsxSheetWriter(buffer_path, PRODATA_SHEET, columns=COLUMNS)
    writer.write_rows([[row.get(column.key) for column in COLUMNS] for row in rows])
    writer.close()
    data = buffer_path.read_bytes()
    buffer_path.unlink()
    return data


async def _upload(api, headers, data: bytes) -> str:
    response = await api.post(
        "/api/v1/excel/uploads/single",
        headers=headers,
        files={"file": ("prodata.xlsx", data, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


# =========================================================
# OPTIONS & PERMISSIONS
# =========================================================

async def test_prodata_options_endpoint(api, database, token_for):
    admin_a = await create_user(database, role=Role.ADMIN, name="Admin A")
    admin_b = await create_user(database, role=Role.ADMIN, name="Admin B")

    chart_a = await create_prodata_chart(database, name="Chart A", created_by=admin_a)
    chart_b = await create_prodata_chart(database, name="Chart B", created_by=admin_b)

    headers_a = token_for(admin_a, Role.ADMIN)
    resp = await api.get("/api/v1/excel/prodata/options", headers=headers_a)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] is True
    ids = {item["id"] for item in body["items"]}
    assert str(chart_a) in ids
    assert str(chart_b) not in ids  # Admin A cannot see Admin B's chart

    item_a = next(i for i in body["items"] if i["id"] == str(chart_a))
    assert item_a["can_modify"] is True
    assert item_a["name"] == "Chart A"


async def test_prodata_template_endpoint(api, database, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    resp = await api.get("/api/v1/excel/prodata/template", headers=token_for(admin, Role.ADMIN))
    assert resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in resp.headers["content-type"]
    wb = load_workbook(filename=io.BytesIO(resp.content), read_only=True)
    assert "Prodata Rate Chart" in wb.sheetnames
    assert "Instructions" in wb.sheetnames
    wb.close()


async def test_prodata_export_and_download(api, database, worker, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    chart_id = await create_prodata_chart(database, name="Exportable Chart", created_by=admin)
    await create_prodata_rows(database, chart_id, [
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.0, "fat_rate_per_kg": 350.0},
        {"row_number": 2, "fat_min": 4.1, "fat_max": 5.0, "fat_rate_per_kg": 370.0},
    ])

    headers = token_for(admin, Role.ADMIN)
    resp = await api.post("/api/v1/excel/prodata/export", json={"chart_id": str(chart_id)}, headers=headers)
    assert resp.status_code == 202
    job_id = resp.json()["data"]["id"]

    job = await _poll(api, headers, job_id)
    assert job["status"]["name"] == "COMPLETED"
    assert job["total_rows"] == 2
    assert job["processed_rows"] == 2

    # Download result file
    file_resp = await api.get(f"/api/v1/excel/jobs/{job_id}/file", headers=headers)
    assert file_resp.status_code == 200
    wb = load_workbook(filename=io.BytesIO(file_resp.content), read_only=True)
    sheet = wb["Prodata Rate Chart"]
    rows = list(sheet.iter_rows(values_only=True))
    assert len(rows) == 3  # Header + 2 data rows
    assert rows[1][0] == 1
    assert rows[2][0] == 2
    wb.close()


async def test_prodata_import_via_upload(api, database, worker, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    chart_id = await create_prodata_chart(database, name="Import Target Chart", created_by=admin)

    # Prepare sheet with 2 rows
    sheet_data = _workbook([
        {"row_number": 1, "fat_min": 3.0, "fat_max": 4.0, "fat_rate_per_kg": 360.0},
        {"row_number": 2, "fat_min": 4.1, "fat_max": 5.0, "fat_rate_per_kg": 380.0},
    ])

    headers = token_for(admin, Role.ADMIN)
    upload_id = await _upload(api, headers, sheet_data)

    resp = await api.post(
        "/api/v1/excel/prodata/import",
        json={"chart_id": str(chart_id), "upload_id": upload_id},
        headers=headers,
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["id"]

    job = await _poll(api, headers, job_id)
    assert job["status"]["name"] == "COMPLETED"
    assert job["inserted"] == 2
    assert job["discarded"] == 0


async def test_prodata_import_forbidden_if_not_modifiable(api, database, token_for):
    super_admin = await create_user(database, role=Role.SUPER_ADMIN, name="Super")
    sub_admin = await create_user(database, role=Role.SUB_ADMIN, name="Sub Admin", created_by=super_admin)

    # Super Admin created this chart -> visible to Sub Admin, but not modifiable by Sub Admin
    chart_id = await create_prodata_chart(database, name="Super Chart", created_by=super_admin)

    headers = token_for(sub_admin, Role.SUB_ADMIN)
    resp = await api.post(
        "/api/v1/excel/prodata/import",
        json={"chart_id": str(chart_id), "upload_id": str(super_admin)},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "permission to modify" in resp.json()["error"]["message"].lower()
