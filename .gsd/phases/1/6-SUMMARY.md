---
phase: 1
plan: 6
completed_at: 2026-10-25
---

# Summary: Resumable Upload & Job REST API

## Results
- 3 tasks completed
- All verifications passed: 10 upload + 9 job API tests through the real app (182 in the module suite) + live server smoke test

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | `ExcelUploadService` (file-based sessions, chunks, resume status, sha256 join, single upload) + DatabaseMiddleware exemption | phase commit (pending) | ✅ |
| 2 | `schemas/excel.py`, `routers/excel.py` (5 upload + 5 job routes), router include | phase commit (pending) | ✅ |
| 3 | API tests through auth + DB + GZip middleware | phase commit (pending) | ✅ |

## Deviations Applied
- [Standards] `ORJSONResponse` is deprecated in FastAPI 0.141 (warning on every call). The router uses `JSONResponse(content=jsonable_encoder(...))`, which AGENTS.md §4C allows ("ORJSONResponse or jsonable_encoder"). Existing routers (e.g. `sync.py`) still use ORJSONResponse; that is out of scope here and noted for later.
- [Rule 3 - Blocking] `ExcelUploadService` registered in `ModuleConfigurator._dataexchange` and exposed as `GetHandler.excel_upload_service` (these files were not in the plan's file list; AGENTS.md §3 requires container access).
- [Rule 2 - Missing critical] The app's ApplicationException handler sets no `Retry-After`, so `excel_busy_response()` renders 429 / 409 in the same error shape plus `Retry-After`. The submit endpoints of Phases 2–4 use it; its test is a direct one because Phase 1 has no submit endpoint yet.
- [Rule 2 - Missing critical] New domain exceptions `ExcelUploadNotFoundException` (404, also for another user's upload) and `ExcelUploadIncompleteException` (409). The joined file lands atomically (`.part` → rename) and is checked by FileGuard before an upload counts as complete.
- [Finding] SQLAlchemy `AsyncSession` takes a connection only on the first query, so a route that never queries holds no connection even inside the middleware transaction. The exemption still matters (no session per chunk, no accidental DB use during uploads). It is tested directly: the transaction context is absent on upload paths and present elsewhere.
- [Test env] conftest sets `EXCHANGE_UPLOAD_CHUNK_MB=1` so chunk tests use ~2.5 MB files.
- [Not verified] `/docs` tag check skipped: docs are only served when `DEBUG` is on.
- [Pre-existing, not fixed] `LoggerManager.shutdown()` leaves its file handlers open (ResourceWarning), and its log directory is a hard-coded relative `logs/`, so test runs also write to the repo's `logs/`.

## Files Changed
- `app/modules/dataexchange/application/uploads.py` — new
- `app/modules/dataexchange/domain/exceptions.py` — upload exceptions
- `app/bootstrap/middleware.py` — `_NO_TRANSACTION_PREFIXES` for `/api/v1/excel/uploads`
- `app/api/v1/schemas/excel.py`, `app/api/v1/routers/excel.py` — new
- `app/api/v1/router.py` — includes `excel_router`
- `app/modules/configurator.py`, `app/modules/dependencies.py` — upload service DI
- `tests/conftest.py` — chunk size for tests
- `tests/dataexchange/conftest.py`, `test_uploads_api.py`, `test_jobs_api.py` — new

## Verification
- 2.5 MB workbook in 3 chunks out of order with one re-sent chunk → complete, stored file byte-identical: ✅ (NFR-05)
- Resume status lists received `[0, 2]` / missing `[1]`; early complete → 409: ✅
- Wrong sha256 → 422 "Checksum mismatch"; oversized chunk → 413; another user's upload → 404; `.csv` name → 422; 1 TB size → 413; zip bomb uploads but is rejected at complete (422); single upload: workbook 201, text 422; no token → 401: ✅ (NFR-05, NFR-09)
- DatabaseMiddleware: no transaction context on `/api/v1/excel/uploads/*`, transaction context on `/api/v1/excel/jobs`: ✅ (NFR-13)
- Jobs: 5 routes → 401 without token; list envelope with items 2 / total 3 / pages 2 / next_page 2 / has_more; enums as `{value, name}`; single envelope with `progress` 25 and `poll_after_ms` 1000; other user → 404 `EXCEL_JOB_NOT_FOUND`; unfinished file → 409; download: xlsx type, `content-encoding: identity` even with `Accept-Encoding: gzip`, byte-identical, opens in openpyxl; `Range: bytes=0-99` → 206 with the right `Content-Range`; cancel → CANCELLED, again → 409: ✅ (REQ-01, REQ-03, NFR-12, NFR-14)
- Busy response: 429 + `Retry-After: 30` + `EXCEL_JOB_QUEUE_FULL`: ✅ (NFR-04)
- **Live uvicorn smoke (temp DB, real token):** create 201 (5 MB chunks), 2 chunks with `missing` shrinking to `[]`, complete 200, jobs list envelope 200, no token 401, no worker left after a hard stop: ✅
- Whole suite: **182 passed**; `import app.main` OK: ✅
