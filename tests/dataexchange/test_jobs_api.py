"""
Job status / list / download / cancel API through the real app (Plan 1.6).
"""

from __future__ import annotations

import io
import json
import os
from datetime import timedelta
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import delete

from app.api.v1.routers.excel import excel_busy_response
from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.dataexchange.domain.columns import ColumnKind, ColumnSpec, Section, SheetSpec
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus
from app.modules.dataexchange.domain.exceptions import ExcelJobCapacityException
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter

SHEET = SheetSpec(name="Farmers", key_column="code", columns=(
    ColumnSpec(key="code", header="Code", section=Section.ENTITY, kind=ColumnKind.CODE, required=True),
    ColumnSpec(key="name", header="Name", section=Section.USER, kind=ColumnKind.TEXT),
))


@pytest.fixture(autouse=True)
async def _empty_job_table(database):
    async with database.transaction() as session:
        await session.execute(delete(ExcelJobModel))
    yield


async def _job(database, user_id: UUID, *, kind=ExcelJobKind.FARMER_EXPORT, status=ExcelJobStatus.QUEUED, **fields) -> ExcelJob:
    job = ExcelJob(id=uuid4(), kind=kind, status=status, created_by=user_id, owner_role=int(Role.VLCC),
                   created_at=fields.pop("created_at", now_naive_ist()), **fields)
    async with database.transaction():
        await ExcelJobRepository(database).create(job)
    return job


def _result_file(job: ExcelJob, rows: int = 50) -> Path:
    folder = Path(os.environ["EXCHANGE_PATH"]) / "jobs" / str(job.id)
    folder.mkdir(parents=True, exist_ok=True)
    writer = XlsxSheetWriter(folder / "result.xlsx", SHEET)
    writer.write_rows([[f"F{i}", f"Farmer {i}"] for i in range(rows)])
    writer.close()
    return folder / "result.xlsx"


# =========================================================
# AUTH
# =========================================================

async def test_every_job_route_requires_a_token(api):
    job_id = uuid4()
    responses = [
        await api.get("/api/v1/excel/jobs"),
        await api.post("/api/v1/excel/jobs/list"),
        await api.get(f"/api/v1/excel/jobs/{job_id}"),
        await api.get(f"/api/v1/excel/jobs/{job_id}/file"),
        await api.post(f"/api/v1/excel/jobs/{job_id}/cancel"),
    ]

    assert [response.status_code for response in responses] == [401] * 5


# =========================================================
# LIST / GET
# =========================================================

async def test_list_uses_the_standard_envelope_with_pagination(api, api_user, database):
    user_id, headers = await api_user()
    for minutes in (3, 2, 1):
        await _job(database, user_id, kind=ExcelJobKind.FARMER_EXPORT,
                   created_at=now_naive_ist() - timedelta(minutes=minutes))
    other_id, _ = await api_user()
    await _job(database, other_id)

    response = await api.get("/api/v1/excel/jobs", headers=headers, params={"limit": 2, "offset": 0})
    body = response.json()

    assert response.status_code == 200
    assert (body["status"], body["code"], body["message"]) == (True, 200, "Records fetched successfully")
    assert len(body["items"]) == 2
    assert (body["limit"], body["offset"], body["total"], body["pages"]) == (2, 0, 3, 2)
    assert (body["next_page"], body["has_more"]) == (2, True)
    assert all(item["kind"] == {"value": 1, "name": "FARMER_EXPORT"} for item in body["items"])


async def test_get_returns_single_envelope_with_poll_hint(api, api_user, database):
    user_id, headers = await api_user()
    job = await _job(database, user_id, status=ExcelJobStatus.RUNNING, started_at=now_naive_ist(),
                     total_rows=1000, processed_rows=250)

    body = (await api.get(f"/api/v1/excel/jobs/{job.id}", headers=headers)).json()

    assert (body["status"], body["code"]) == (True, 200)
    data = body["data"]
    assert data["status"] == {"value": 1, "name": "RUNNING"}
    assert data["progress"] == 25
    assert data["poll_after_ms"] == 1000
    assert data["has_file"] is False


async def test_another_users_job_is_404_in_the_error_envelope(api, api_user, database):
    owner_id, _ = await api_user()
    _, stranger = await api_user()
    job = await _job(database, owner_id)

    response = await api.get(f"/api/v1/excel/jobs/{job.id}", headers=stranger)

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "EXCEL_JOB_NOT_FOUND"


# =========================================================
# DOWNLOAD
# =========================================================

async def test_file_of_unfinished_job_is_409(api, api_user, database):
    user_id, headers = await api_user()
    job = await _job(database, user_id)

    response = await api.get(f"/api/v1/excel/jobs/{job.id}/file", headers=headers)

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "EXCEL_JOB_FILE_NOT_READY"


async def test_download_streams_xlsx_without_gzip(api, api_user, database):
    user_id, headers = await api_user()
    job = await _job(database, user_id, status=ExcelJobStatus.COMPLETED, result_file="result.xlsx",
                     finished_at=now_naive_ist())
    expected = _result_file(job, rows=3000).read_bytes()

    response = await api.get(f"/api/v1/excel/jobs/{job.id}/file", headers={**headers, "Accept-Encoding": "gzip"})

    assert response.status_code == 200
    assert response.headers["content-type"] == "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    assert response.headers["content-encoding"] == "identity"          # GZipMiddleware skipped it
    assert "farmer_export_" in response.headers["content-disposition"]
    assert response.content == expected
    sheet = load_workbook(io.BytesIO(response.content), read_only=True)["Farmers"]
    assert next(sheet.iter_rows(min_row=2, max_row=2, values_only=True))[0] == "F0"


async def test_download_supports_range_for_resume(api, api_user, database):
    user_id, headers = await api_user()
    job = await _job(database, user_id, status=ExcelJobStatus.COMPLETED, result_file="result.xlsx",
                     finished_at=now_naive_ist())
    expected = _result_file(job).read_bytes()

    response = await api.get(f"/api/v1/excel/jobs/{job.id}/file", headers={**headers, "Range": "bytes=0-99"})

    assert response.status_code == 206
    assert response.content == expected[:100]
    assert response.headers["content-range"] == f"bytes 0-99/{len(expected)}"


# =========================================================
# CANCEL
# =========================================================

async def test_cancel_active_job_then_cancel_again_is_409(api, api_user, database):
    user_id, headers = await api_user()
    job = await _job(database, user_id)

    first = await api.post(f"/api/v1/excel/jobs/{job.id}/cancel", headers=headers)
    second = await api.post(f"/api/v1/excel/jobs/{job.id}/cancel", headers=headers)

    assert first.status_code == 200
    assert first.json()["data"]["status"]["name"] == "CANCELLED"
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "EXCEL_JOB_FINISHED"


# =========================================================
# BUSY RESPONSES (used by the submit endpoints of Phases 2-4)
# =========================================================

def test_busy_response_has_retry_after_and_the_standard_error_shape():
    response = excel_busy_response(ExcelJobCapacityException())

    assert response.status_code == 429
    assert response.headers["retry-after"] == "30"
    assert json.loads(response.body)["error"]["code"] == "EXCEL_JOB_QUEUE_FULL"
