"""
Resumable upload API through the real app (Plan 1.6).
"""

from __future__ import annotations

import hashlib
import os
import zipfile
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
from starlette.applications import Starlette
from starlette.responses import JSONResponse
from starlette.routing import Route

from app.bootstrap.middleware import DatabaseMiddleware
from app.core.database.transaction import _CURRENT_SESSION

MB = 1024 * 1024
BASE_PARTS = {
    "[Content_Types].xml": b'<?xml version="1.0"?><Types/>',
    "xl/workbook.xml": b'<?xml version="1.0"?><workbook/>',
}


def _workbook(path: Path, padding: int) -> bytes:
    """A workbook-shaped zip of a chosen size (stored, so the size is exact and the guard passes)."""
    with zipfile.ZipFile(path, "w", zipfile.ZIP_STORED) as archive:
        for name, data in BASE_PARTS.items():
            archive.writestr(name, data)
        archive.writestr("xl/media/padding.bin", os.urandom(padding))
    return path.read_bytes()


def _zip_bomb(path: Path) -> bytes:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, data in BASE_PARTS.items():
            archive.writestr(name, data)
        archive.writestr("xl/worksheets/sheet1.xml", b"\0" * (50 * MB))
    return path.read_bytes()


async def _start(api, headers, data: bytes, *, sha: str | None = None) -> dict:
    response = await api.post("/api/v1/excel/uploads", headers=headers, json={
        "file_name": "farmers.xlsx", "size": len(data), "sha256": sha or hashlib.sha256(data).hexdigest(),
    })
    assert response.status_code == 201, response.text
    return response.json()["data"]


async def _put(api, headers, upload_id, index, body: bytes) -> httpx.Response:
    return await api.put(f"/api/v1/excel/uploads/{upload_id}/chunks/{index}", headers=headers, content=body)


def _chunks(data: bytes, size: int) -> list[bytes]:
    return [data[start:start + size] for start in range(0, len(data), size)]


# =========================================================
# CHUNKED
# =========================================================

async def test_chunked_upload_out_of_order_with_resend_completes_byte_identical(api, api_user, tmp_path):
    _, headers = await api_user()
    data = _workbook(tmp_path / "big.xlsx", padding=int(2.5 * MB))
    upload = await _start(api, headers, data)
    parts = _chunks(data, upload["chunk_size"])

    assert upload["chunk_size"] == MB and upload["total_chunks"] == len(parts) == 3
    for index in (2, 0, 1, 0):                               # out of order, chunk 0 sent twice
        response = await _put(api, headers, upload["id"], index, parts[index])
        assert response.status_code == 200, response.text
    done = await api.post(f"/api/v1/excel/uploads/{upload['id']}/complete", headers=headers)

    assert done.status_code == 200, done.text
    body = done.json()
    assert body["status"] is True and body["data"]["completed"] is True and body["data"]["missing"] == []
    stored = Path(os.environ["EXCHANGE_PATH"]) / "uploads" / upload["id"] / "source.xlsx"
    assert stored.read_bytes() == data


async def test_status_lists_missing_chunks_for_resume(api, api_user, tmp_path):
    _, headers = await api_user()
    data = _workbook(tmp_path / "resume.xlsx", padding=int(2.5 * MB))
    upload = await _start(api, headers, data)
    parts = _chunks(data, upload["chunk_size"])
    await _put(api, headers, upload["id"], 0, parts[0])
    await _put(api, headers, upload["id"], 2, parts[2])

    status = (await api.get(f"/api/v1/excel/uploads/{upload['id']}", headers=headers)).json()["data"]
    early = await api.post(f"/api/v1/excel/uploads/{upload['id']}/complete", headers=headers)

    assert status["received"] == [0, 2] and status["missing"] == [1]
    assert early.status_code == 409
    assert early.json()["error"]["code"] == "EXCEL_UPLOAD_INCOMPLETE"


async def test_wrong_checksum_is_rejected_at_complete(api, api_user, tmp_path):
    _, headers = await api_user()
    data = _workbook(tmp_path / "sha.xlsx", padding=100_000)
    upload = await _start(api, headers, data, sha="0" * 64)
    await _put(api, headers, upload["id"], 0, data)

    response = await api.post(f"/api/v1/excel/uploads/{upload['id']}/complete", headers=headers)

    assert response.status_code == 422
    assert "Checksum mismatch" in response.json()["error"]["message"]


async def test_chunk_larger_than_announced_is_413(api, api_user, tmp_path):
    _, headers = await api_user()
    data = _workbook(tmp_path / "sized.xlsx", padding=int(1.5 * MB))
    upload = await _start(api, headers, data)

    response = await _put(api, headers, upload["id"], 0, data[: upload["chunk_size"]] + b"extra")

    assert response.status_code == 413


async def test_another_users_upload_is_not_found(api, api_user, tmp_path):
    _, headers_a = await api_user()
    _, headers_b = await api_user()
    data = _workbook(tmp_path / "mine.xlsx", padding=10_000)
    upload = await _start(api, headers_a, data)

    put = await _put(api, headers_b, upload["id"], 0, data)
    get = await api.get(f"/api/v1/excel/uploads/{upload['id']}", headers=headers_b)

    assert put.status_code == 404 and get.status_code == 404


async def test_zip_bomb_uploads_but_is_rejected_at_complete(api, api_user, tmp_path):
    _, headers = await api_user()
    data = _zip_bomb(tmp_path / "bomb.xlsx")
    upload = await _start(api, headers, data)
    for index, part in enumerate(_chunks(data, upload["chunk_size"])):
        assert (await _put(api, headers, upload["id"], index, part)).status_code == 200

    response = await api.post(f"/api/v1/excel/uploads/{upload['id']}/complete", headers=headers)

    assert response.status_code == 422
    assert "suspiciously" in response.json()["error"]["message"]


async def test_create_rejects_non_xlsx_names_and_bad_sizes(api, api_user):
    _, headers = await api_user()

    wrong_type = await api.post("/api/v1/excel/uploads", headers=headers,
                                json={"file_name": "farmers.csv", "size": 10, "sha256": "a" * 64})
    too_big = await api.post("/api/v1/excel/uploads", headers=headers,
                             json={"file_name": "farmers.xlsx", "size": 10 ** 12, "sha256": "a" * 64})

    assert wrong_type.status_code == 422
    assert too_big.status_code == 413


# =========================================================
# SINGLE REQUEST
# =========================================================

async def test_single_upload_accepts_small_workbook_and_rejects_text(api, api_user, tmp_path):
    _, headers = await api_user()
    data = _workbook(tmp_path / "small.xlsx", padding=1000)

    good = await api.post("/api/v1/excel/uploads/single", headers=headers,
                          files={"file": ("small.xlsx", data, "application/octet-stream")})
    bad = await api.post("/api/v1/excel/uploads/single", headers=headers,
                         files={"file": ("notes.xlsx", b"name,mobile\n", "application/octet-stream")})

    assert good.status_code == 201 and good.json()["data"]["completed"] is True
    assert bad.status_code == 422


async def test_uploads_require_a_token(api):
    responses = [
        await api.post("/api/v1/excel/uploads", json={"file_name": "a.xlsx", "size": 1, "sha256": "a" * 64}),
        await api.get("/api/v1/excel/uploads/00000000-0000-0000-0000-000000000000"),
        await api.put("/api/v1/excel/uploads/00000000-0000-0000-0000-000000000000/chunks/0", content=b"x"),
    ]

    assert [response.status_code for response in responses] == [401, 401, 401]


# =========================================================
# NO REQUEST TRANSACTION ON UPLOAD PATHS (NFR-13)
# =========================================================

async def test_database_middleware_skips_the_transaction_for_upload_paths_only(database):
    async def probe(request):
        return JSONResponse({"in_transaction": _CURRENT_SESSION.get() is not None})

    app = Starlette(routes=[
        Route("/api/v1/excel/uploads/{rest:path}", probe, methods=["PUT", "POST", "GET"]),
        Route("/api/v1/excel/jobs", probe),
    ])
    app.add_middleware(DatabaseMiddleware)
    app.state.application = SimpleNamespace(container=SimpleNamespace(database=database))

    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://probe") as client:
        upload = (await client.put("/api/v1/excel/uploads/abc/chunks/0", content=b"x")).json()
        jobs = (await client.get("/api/v1/excel/jobs")).json()

    assert upload == {"in_transaction": False}
    assert jobs == {"in_transaction": True}
