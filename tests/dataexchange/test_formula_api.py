"""
Formula Rate-Chart Exchange HTTP API Tests with real ExchangeWorker (Plan 6.2).
"""

from __future__ import annotations

import asyncio
import contextvars
import io
import os
import time
from pathlib import Path
from uuid import UUID

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete, select

from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.application.formula_export import FormulaExportProcessor
from app.modules.dataexchange.application.formula_import import FormulaImportProcessor
from app.modules.dataexchange.domain.sheets import FORMULA_SHEET
from app.modules.dataexchange.infrastructure.formula_repository import FormulaExchangeRepository
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.modules.ratechart.domain.enums import MilkType, RateChartType
from app.modules.ratechart.infrastructure.models import RateChartModel, RateFormulaConfigModel
from app.worker.exchange import ExchangeWorker
from tests.dataexchange.factories import (
    create_formula_chart,
    create_formula_config,
    create_user,
)

COLUMNS = FORMULA_SHEET.import_columns()


@pytest.fixture(autouse=True)
async def _empty_job_table(database):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


@pytest.fixture
async def worker(database):
    """The real worker loop with Formula processors."""
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
    repo = FormulaExchangeRepository(database)
    instance.register(FormulaExportProcessor(database=database, repository=repo))
    instance.register(FormulaImportProcessor(database=database, repository=repo))
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
    buffer_path = Path(os.environ["EXCHANGE_PATH"]) / f"tmp-formula-{time.time_ns()}.xlsx"
    buffer_path.parent.mkdir(parents=True, exist_ok=True)
    writer = XlsxSheetWriter(buffer_path, FORMULA_SHEET, columns=COLUMNS)
    writer.write_rows([[row.get(column.key) for column in COLUMNS] for row in rows])
    writer.close()
    data = buffer_path.read_bytes()
    buffer_path.unlink()
    return data


async def _upload(api, headers, data: bytes) -> str:
    response = await api.post(
        "/api/v1/excel/uploads/single",
        headers=headers,
        files={"file": ("formula.xlsx", data, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


# =========================================================
# OPTIONS & TEMPLATE
# =========================================================

async def test_formula_options_endpoint(api, database, token_for):
    admin_a = await create_user(database, role=Role.ADMIN, name="Admin A")
    admin_b = await create_user(database, role=Role.ADMIN, name="Admin B")

    chart_a = await create_formula_chart(database, name="Formula Chart A", created_by=admin_a)
    chart_b = await create_formula_chart(database, name="Formula Chart B", created_by=admin_b)

    headers_a = token_for(admin_a, Role.ADMIN)
    resp = await api.get("/api/v1/excel/formula/options", headers=headers_a)
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] is True
    ids = {item["id"] for item in body["items"]}
    assert str(chart_a) in ids
    assert str(chart_b) not in ids  # Admin A cannot see Admin B's chart

    item_a = next(i for i in body["items"] if i["id"] == str(chart_a))
    assert item_a["can_modify"] is True
    assert item_a["name"] == "Formula Chart A"


async def test_formula_template_endpoint(api, database, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    resp = await api.get("/api/v1/excel/formula/template", headers=token_for(admin, Role.ADMIN))
    assert resp.status_code == 200
    assert "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" in resp.headers["content-type"]
    wb = load_workbook(filename=io.BytesIO(resp.content), read_only=True)
    assert "Formula Rate Chart" in wb.sheetnames
    assert "Instructions" in wb.sheetnames
    wb.close()


# =========================================================
# EXPORT
# =========================================================

async def test_formula_export_and_download(api, database, worker, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    chart_id = await create_formula_chart(database, name="Exportable Formula Chart", created_by=admin, milk_type=2)
    await create_formula_config(
        database,
        chart_id,
        cow_standard_fat=4.0,
        cow_standard_snf=8.5,
        cow_standard_rate=42.0,
        cow_fat_percentage=60.0,
        cow_snf_percentage=40.0,
        buffalo_standard_fat=6.5,
        buffalo_standard_snf=9.0,
        buffalo_standard_rate=68.0,
        buffalo_fat_percentage=60.0,
        buffalo_snf_percentage=40.0,
    )

    headers = token_for(admin, Role.ADMIN)
    resp = await api.post("/api/v1/excel/formula/export", json={"chart_id": str(chart_id)}, headers=headers)
    assert resp.status_code == 202
    job_id = resp.json()["data"]["id"]

    job = await _poll(api, headers, job_id)
    assert job["status"]["name"] == "COMPLETED", job.get("error_message")
    assert job["total_rows"] == 2
    assert job["processed_rows"] == 2

    # Download result file
    file_resp = await api.get(f"/api/v1/excel/jobs/{job_id}/file", headers=headers)
    assert file_resp.status_code == 200
    wb = load_workbook(filename=io.BytesIO(file_resp.content))
    assert "Formula Rate Chart" in wb.sheetnames

    sheet = wb["Formula Rate Chart"]
    rows = list(sheet.iter_rows(values_only=True))
    assert len(rows) == 3  # Header + COW + BUFFALO
    animals = {r[0] for r in rows[1:]}
    assert "COW" in animals
    assert "BUFFALO" in animals
    wb.close()


# =========================================================
# IMPORT
# =========================================================

async def test_formula_import_via_upload(api, database, worker, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    chart_id = await create_formula_chart(database, name="Import Target Formula Chart", created_by=admin, milk_type=2)
    await create_formula_config(
        database,
        chart_id,
        cow_standard_fat=3.5,
        cow_standard_snf=8.0,
        cow_standard_rate=35.0,
    )

    # Upload updated config rows
    sheet_data = _workbook([
        {
            "animal_type": "COW",
            "standard_fat": 4.2,
            "standard_snf": 8.6,
            "standard_rate": 45.0,
            "fat_percentage": 55.0,
            "snf_percentage": 45.0,
        },
        {
            "animal_type": "BUFFALO",
            "standard_fat": 7.0,
            "standard_snf": 9.2,
            "standard_rate": 72.0,
            "fat_percentage": 65.0,
            "snf_percentage": 35.0,
        },
    ])

    headers = token_for(admin, Role.ADMIN)
    upload_id = await _upload(api, headers, sheet_data)

    resp = await api.post(
        "/api/v1/excel/formula/import",
        json={"chart_id": str(chart_id), "upload_id": upload_id},
        headers=headers,
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["id"]

    job = await _poll(api, headers, job_id)
    assert job["status"]["name"] == "COMPLETED"
    assert job["inserted"] == 2
    assert job["discarded"] == 0

    # Verify updated DB values
    async with database.transaction() as session:
        cfg = await session.scalar(
            select(RateFormulaConfigModel).where(RateFormulaConfigModel.rate_chart_id == chart_id)
        )
        assert cfg is not None
        assert cfg.cow_standard_rate == 45.0
        assert cfg.cow_standard_fat == 4.2
        assert cfg.cow_fat_percentage == 55.0
        assert cfg.buffalo_standard_rate == 72.0
        assert cfg.buffalo_standard_fat == 7.0
        assert cfg.buffalo_fat_percentage == 65.0


async def test_formula_import_forbidden_if_not_modifiable(api, database, token_for):
    super_admin = await create_user(database, role=Role.SUPER_ADMIN, name="Super")
    sub_admin = await create_user(database, role=Role.SUB_ADMIN, name="Sub Admin", created_by=super_admin)

    chart_id = await create_formula_chart(database, name="Super Formula Chart", created_by=super_admin)

    headers = token_for(sub_admin, Role.SUB_ADMIN)
    resp = await api.post(
        "/api/v1/excel/formula/import",
        json={"chart_id": str(chart_id), "upload_id": str(super_admin)},
        headers=headers,
    )
    assert resp.status_code == 403
    assert "permission to modify" in resp.json()["error"]["message"].lower()


async def test_formula_import_creates_new_chart_from_excel(api, database, worker, token_for):
    admin = await create_user(database, role=Role.ADMIN)

    sheet_data = _workbook([
        {
            "animal_type": "COW",
            "standard_fat": 4.0,
            "standard_snf": 8.5,
            "standard_rate": 40.0,
            "fat_percentage": 60.0,
            "snf_percentage": 40.0,
        },
        {
            "animal_type": "BUFFALO",
            "standard_fat": 6.5,
            "standard_snf": 9.0,
            "standard_rate": 65.0,
            "fat_percentage": 60.0,
            "snf_percentage": 40.0,
        },
    ])

    headers = token_for(admin, Role.ADMIN)
    upload_id = await _upload(api, headers, sheet_data)

    resp = await api.post(
        "/api/v1/excel/formula/import",
        json={
            "chart_id": None,
            "chart_name": "Brand New Formula Chart",
            "milk_type": 2,  # MIXED
            "upload_id": upload_id,
        },
        headers=headers,
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["id"]

    job = await _poll(api, headers, job_id)
    assert job["status"]["name"] == "COMPLETED"
    assert job["inserted"] == 2
    assert job["discarded"] == 0

    target_id = job["target_id"]
    assert target_id is not None

    async with database.transaction() as session:
        chart = await session.scalar(select(RateChartModel).where(RateChartModel.id == UUID(target_id)))
        assert chart is not None
        assert chart.chart_name == "Brand New Formula Chart"
        assert chart.chart_type == RateChartType.FORMULA
        assert chart.milk_type == MilkType.MIXED

        cfg = await session.scalar(
            select(RateFormulaConfigModel).where(RateFormulaConfigModel.rate_chart_id == UUID(target_id))
        )
        assert cfg is not None
        assert cfg.cow_standard_rate == 40.0
        assert cfg.buffalo_standard_rate == 65.0


async def test_formula_import_validation_discarded_rows(api, database, worker, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    chart_id = await create_formula_chart(database, name="Validation Test Chart", created_by=admin)

    # Invalid row: fat_percentage 60 + snf_percentage 50 = 110 != 100
    sheet_data = _workbook([
        {
            "animal_type": "COW",
            "standard_fat": 4.0,
            "standard_snf": 8.5,
            "standard_rate": 40.0,
            "fat_percentage": 60.0,
            "snf_percentage": 50.0,  # Invalid! Sum is 110
        },
    ])

    headers = token_for(admin, Role.ADMIN)
    upload_id = await _upload(api, headers, sheet_data)

    resp = await api.post(
        "/api/v1/excel/formula/import",
        json={"chart_id": str(chart_id), "upload_id": upload_id},
        headers=headers,
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["id"]

    job = await _poll(api, headers, job_id)
    assert job["status"]["name"] == "COMPLETED"
    assert job["inserted"] == 0
    assert job["discarded"] == 1

    # Discard report should be available
    discard_resp = await api.get(f"/api/v1/excel/jobs/{job_id}/file", headers=headers)
    assert discard_resp.status_code == 200
    wb = load_workbook(filename=io.BytesIO(discard_resp.content), read_only=True)
    assert "Formula Rate Chart" in wb.sheetnames
    sheet = wb["Formula Rate Chart"]
    rows = list(sheet.iter_rows(values_only=True))
    assert len(rows) == 2  # Header + 1 discarded row
    assert "must sum to 100%" in str(rows[1][-1])
    wb.close()


async def test_formula_import_new_chart_dry_run_creates_nothing(api, database, worker, token_for):
    admin = await create_user(database, role=Role.ADMIN)
    headers = token_for(admin, Role.ADMIN)

    sheet_data = _workbook([
        {
            "animal_type": "COW",
            "standard_fat": 4.0,
            "standard_snf": 8.5,
            "standard_rate": 40.0,
            "fat_percentage": 60.0,
            "snf_percentage": 40.0,
        },
    ])
    upload_id = await _upload(api, headers, sheet_data)

    resp = await api.post(
        "/api/v1/excel/formula/import",
        json={
            "chart_id": None,
            "chart_name": "Dry Run Phantom Formula Chart",
            "dry_run": True,
            "upload_id": upload_id,
        },
        headers=headers,
    )
    assert resp.status_code == 202
    job_id = resp.json()["data"]["id"]

    job = await _poll(api, headers, job_id)
    assert job["status"]["name"] == "COMPLETED"
    assert job["inserted"] == 1

    # Verify no chart was created in the DB
    async with database.transaction() as session:
        chart = await session.scalar(
            select(RateChartModel).where(RateChartModel.chart_name == "Dry Run Phantom Formula Chart")
        )
        assert chart is None
