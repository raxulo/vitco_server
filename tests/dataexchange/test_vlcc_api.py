"""
VLCC exchange through HTTP + a real ExchangeWorker on the same test database (Plan 3.3).
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
from app.modules.dataexchange.application.vlcc_export import VlccExportProcessor
from app.modules.dataexchange.application.vlcc_import import VlccImportProcessor
from app.modules.dataexchange.domain.sheets import VLCC_SHEET
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.vlcc_repository import VlccExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.worker.exchange import ExchangeWorker
from tests.dataexchange.factories import create_full_vlccs, create_user, unique_mobile

COLUMNS = VLCC_SHEET.import_columns()


@pytest.fixture(autouse=True)
async def _empty_job_table(database):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


@pytest.fixture
async def worker(database):
    """The real worker loop with the VLCC processors."""
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
    vlccs = VlccExchangeRepository(database)
    instance.register(VlccExportProcessor(database=database, repository=vlccs))
    instance.register(VlccImportProcessor(database=database, repository=vlccs, password_service=PasswordService()))
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
    writer = XlsxSheetWriter(buffer_path, VLCC_SHEET, columns=COLUMNS)
    writer.write_rows([[row.get(column.key) for column in COLUMNS] for row in rows])
    writer.close()
    data = buffer_path.read_bytes()
    buffer_path.unlink()
    return data


async def _upload(api, headers, data: bytes) -> str:
    response = await api.post(
        "/api/v1/excel/uploads/single",
        headers=headers,
        files={"file": ("vlccs.xlsx", data, "application/octet-stream")},
    )
    assert response.status_code == 201, response.text
    return response.json()["data"]["id"]


# =========================================================
# OPTIONS & PERMISSIONS
# =========================================================

async def test_owner_options_for_admin_and_sub_admin(api, database, token_for):
    admin_id = await create_user(database, role=Role.ADMIN, name="Main Admin")
    sub_admin_id = await create_user(database, role=Role.SUB_ADMIN, name="Sub Admin 1", created_by=admin_id)
    other_admin = await create_user(database, role=Role.ADMIN, name="Other Admin")

    # Admin options: itself + its Sub Admin
    resp = await api.get("/api/v1/excel/vlccs/options", headers=token_for(admin_id, Role.ADMIN))
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] is True
    assert body["locked"] is False
    assert body["default_id"] == str(admin_id)
    ids = {item["id"] for item in body["items"]}
    assert str(admin_id) in ids
    assert str(sub_admin_id) in ids
    assert str(other_admin) not in ids

    # Sub Admin options: locked to itself
    resp2 = await api.get("/api/v1/excel/vlccs/options", headers=token_for(sub_admin_id, Role.SUB_ADMIN))
    body2 = resp2.json()
    assert body2["locked"] is True
    assert body2["default_id"] == str(sub_admin_id)
    assert len(body2["items"]) == 1
    assert body2["items"][0]["id"] == str(sub_admin_id)


async def test_owner_options_super_admin(api, database, token_for):
    sa_id = await create_user(database, role=Role.SUPER_ADMIN, name="Super User")
    admin_id = await create_user(database, role=Role.ADMIN, name="Admin User")

    resp = await api.get("/api/v1/excel/options/owners", headers=token_for(sa_id, Role.SUPER_ADMIN))
    assert resp.status_code == 200
    body = resp.json()
    assert body["locked"] is False
    ids = {item["id"] for item in body["items"]}
    assert str(sa_id) in ids
    assert str(admin_id) in ids


async def test_vlcc_and_farmer_roles_forbidden(api, database, token_for):
    vlcc_user_id = await create_user(database, role=Role.VLCC)
    farmer_user_id = await create_user(database, role=Role.FARMER)

    for uid, r in ((vlcc_user_id, Role.VLCC), (farmer_user_id, Role.FARMER)):
        headers = token_for(uid, r)
        res1 = await api.get("/api/v1/excel/vlccs/options", headers=headers)
        assert res1.status_code == 403
        res2 = await api.post("/api/v1/excel/vlccs/export", headers=headers, json={"owner_id": str(uid)})
        assert res2.status_code == 403


async def test_vlcc_template_download(api, database, token_for):
    admin_id = await create_user(database, role=Role.ADMIN)
    resp = await api.get("/api/v1/excel/vlccs/template", headers=token_for(admin_id, Role.ADMIN))
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert "vlccs_template" in resp.headers["content-disposition"]


# =========================================================
# END-TO-END WORKER FLOW
# =========================================================

async def test_vlcc_export_and_import_end_to_end(api, database, worker, token_for):
    admin_id = await create_user(database, role=Role.ADMIN, name="Boss Admin")
    headers = token_for(admin_id, Role.ADMIN)

    # 1. Pre-create 3 VLCCs for this Admin
    created = await create_full_vlccs(database, admin_id, 3, prefix="E2E")
    codes = [c["vlcc_code"] for c in created]

    # 2. Trigger Export
    exp_resp = await api.post("/api/v1/excel/vlccs/export", headers=headers, json={"owner_id": str(admin_id)})
    assert exp_resp.status_code == 202
    job_id = exp_resp.json()["data"]["id"]

    # 3. Poll until export completes
    job_data = await _poll(api, headers, job_id)
    assert job_data["status"]["name"] == "COMPLETED"
    assert job_data["total_rows"] == 3
    assert job_data["has_file"] is True

    # 4. Download exported file
    file_resp = await api.get(f"/api/v1/excel/jobs/{job_id}/file", headers=headers)
    assert file_resp.status_code == 200
    exported_bytes = file_resp.content

    # 5. Read exported workbook, add a new VLCC row and change contact_person of first
    wb = load_workbook(io.BytesIO(exported_bytes), data_only=True)
    sheet = wb["VLCCs"]
    rows = list(sheet.iter_rows(values_only=True))
    header = rows[0]
    data_rows = rows[1:]
    assert len(data_rows) == 3

    # Add 1 new VLCC row and modify 1 existing
    header_to_key = {col.display_header: col.key for col in VLCC_SHEET.export_columns()}
    new_mobile = unique_mobile()
    new_row = {
        "vlcc_code": "E2ENEW", "uic_code": "UICNEW", "vlcc_name": "New Center",
        "user_name": "New Operator", "mobile": new_mobile, "route_code": 999,
    }

    import_rows = []
    # Row 0: updated contact person
    r0 = {header_to_key[header[i]]: data_rows[0][i] for i in range(len(header)) if header[i] in header_to_key}
    r0["contact_person"] = "Updated Contact Person"
    import_rows.append(r0)
    # Row 1, 2: unchanged
    for r in data_rows[1:]:
        import_rows.append({header_to_key[header[i]]: r[i] for i in range(len(header)) if header[i] in header_to_key})
    # Row 3: new VLCC
    import_rows.append(new_row)


    # 6. Upload new file
    upload_bytes = _workbook(import_rows)
    upload_id = await _upload(api, headers, upload_bytes)

    # 7. Submit Import
    imp_resp = await api.post("/api/v1/excel/vlccs/import", headers=headers, json={
        "upload_id": upload_id,
        "owner_id": str(admin_id),
        "mode": "UPSERT",
    })
    assert imp_resp.status_code == 202
    imp_job_id = imp_resp.json()["data"]["id"]

    # 8. Poll until import completes
    imp_data = await _poll(api, headers, imp_job_id)
    assert imp_data["status"]["name"] == "COMPLETED"
    assert imp_data["inserted"] == 1
    assert imp_data["updated"] == 1
    assert imp_data["unchanged"] == 2
    assert imp_data["discarded"] == 0
