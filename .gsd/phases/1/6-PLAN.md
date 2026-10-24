---
phase: 1
plan: 6
wave: 5
depends_on: [5]
files_modified:
  - app/modules/dataexchange/application/uploads.py
  - app/bootstrap/middleware.py
  - app/api/v1/schemas/excel.py
  - app/api/v1/routers/excel.py
  - app/api/v1/router.py
  - tests/dataexchange/test_uploads_api.py
  - tests/dataexchange/test_jobs_api.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "A file can be uploaded in ≤ 5 MB chunks, in any order, re-sending a chunk is harmless, and complete() verifies total size + sha256"
    - "After a simulated network drop, GET /excel/uploads/{id} lists the missing chunks and the upload can be finished without re-sending the rest"
    - "Upload requests never hold a database connection (exempt from DatabaseMiddleware's transaction)"
    - "GET /api/v1/excel/jobs returns the standard list envelope; GET /jobs/{id} the single envelope with poll_after_ms; other users' ids → 404; no token → 401"
    - "GET /jobs/{id}/file streams the xlsx with Content-Disposition, Content-Encoding: identity (not gzipped) and Range support (206)"
    - "POST /jobs/{id}/cancel cancels an active job; a finished job → 409"
  artifacts:
    - "/api/v1/excel/uploads* and /api/v1/excel/jobs* routes in api_v1_router, 'Excel Import / Export' tag in /docs"
  key_links:
    - "Requirements: REQ-01, REQ-03, NFR-05, NFR-12, NFR-13, NFR-14; DECISION-009, DECISION-011; AGENTS.md §4, §6"
---

# Plan 1.6: Resumable Upload & Job REST API

<objective>
Expose the shared REST surface for the web panel and the mobile app: resumable chunked uploads that never tie up DB connections, and job status / list / download / cancel endpoints. Entity endpoints (`/excel/farmers/...`, `/excel/vlccs/...`, `/excel/ratecharts/...`) are added by Phases 2–4 to the same router.

Purpose: mobile networks drop; big uploads must neither restart from zero nor freeze the API (NFR-13).
Output: upload service, middleware exemption, schemas, router, API tests.
</objective>

<context>
Load for context:
- .gsd/REQUIREMENTS.md (REQ-01, REQ-03, NFR-05, NFR-12..NFR-14, CON-10)
- .gsd/DECISIONS.md (DECISION-009, DECISION-011)
- AGENTS.md §4 (envelopes), §6 (CurrentUser / 401)
- app/bootstrap/middleware.py (DatabaseMiddleware, GZipMiddleware)
- app/api/v1/routers/unit_master.py (`_compute_pagination`, envelope style)
- app/api/v1/router.py
- app/modules/dataexchange/application/handler.py, dto.py (Plan 1.5); infrastructure/storage.py (Plan 1.3)
- how ApplicationException subclasses are rendered to JSON today (find the exception handler and follow it)
</context>

<tasks>

<task type="auto">
  <name>Upload session service and DatabaseMiddleware exemption</name>
  <files>
    app/modules/dataexchange/application/uploads.py
    app/bootstrap/middleware.py
  </files>
  <action>
    1. uploads.py — `ExcelUploadService` (`__slots__`), file-based, no DB: metadata in `uploads/<id>/upload.json` (owner id, file name, size, sha256, chunk size, created_at), written atomically (temp file + `os.replace`); chunks as `chunk_<n>.part`.
       - `create(owner, *, file_name, size, sha256)`: validates size ≤ EXCHANGE_MAX_UPLOAD_MB, `.xlsx` name, free disk (`ensure_free_space(size)`), returns id, chunk_size, total_chunks;
       - `async put_chunk(owner, upload_id, index, stream)`: owner check (404 otherwise), index range, streams through `storage.write_stream` with limit = chunk_size (last chunk exact remainder), writes to `.tmp` then renames (idempotent re-send);
       - `status(owner, upload_id)` → received / missing chunk indexes;
       - `complete(owner, upload_id)`: all chunks present → concatenate into `source.xlsx` in 1 MB blocks while hashing (`hashlib.sha256`), size + hash must match else delete the result and raise InvalidExcelFileException("Checksum mismatch"); run `FileGuard.inspect` via `asyncio.to_thread`; mark complete;
       - `async save_single(owner, upload)`: one-request path for files ≤ 10 MB (same checks, no client hash needed);
       - `take(owner, upload_id) -> Path` used by `ExcelJobHandler.submit_import` (complete + owner check).
    2. middleware.py: `DatabaseMiddleware` skips its transaction for paths starting with `/api/v1/excel/uploads` (a module-level tuple `_NO_TRANSACTION_PREFIXES`), passing straight to `call_next`.
    AVOID: keeping the transaction for upload paths, because a slow upload would hold a pooled connection for minutes and a few of them would starve the whole API (NFR-13).
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.application.uploads import ExcelUploadService; print(ExcelUploadService.__slots__)" → prints slots</verify>
  <done>Upload service handles create / put / status / complete / single without touching the DB; middleware skips upload paths only.</done>
</task>

<task type="auto">
  <name>Schemas and router for uploads and jobs</name>
  <files>
    app/api/v1/schemas/excel.py
    app/api/v1/routers/excel.py
    app/api/v1/router.py
  </files>
  <action>
    1. schemas/excel.py: Pydantic v2 request / response models — `CreateUploadRequest(file_name, size, sha256)`, `UploadResponse`, `ExcelJobResponse` (kind / status as `{value, name}` so the app does not hard-code numbers; includes poll_after_ms, rows_per_second, eta_seconds).
    2. routers/excel.py: `APIRouter(prefix="/excel", tags=["Excel Import / Export"])`; local `_compute_pagination(total, limit, offset)` copied from unit_master.py; `ORJSONResponse` + `jsonable_encoder`.
       Uploads: `POST /uploads` (201), `PUT /uploads/{upload_id}/chunks/{index}` (raw body streamed via `request.stream()`, 204), `GET /uploads/{upload_id}`, `POST /uploads/{upload_id}/complete`, `POST /uploads/single` (multipart, ≤ 10 MB).
       Jobs: `GET /jobs` + `POST /jobs/list` (kind, status, limit 1–100 default 20, offset ≥ 0; list envelope), `GET /jobs/{job_id}` (single envelope), `GET /jobs/{job_id}/file` (`FileResponse(path, filename=<kind>_<YYYYMMDD_HHMM>.xlsx, media_type=xlsx)` + header `Content-Encoding: identity`), `POST /jobs/{job_id}/cancel`.
       Every endpoint: `user: CurrentUser | None = getattr(request.state, "user", None)` → 401; 429 / 409 responses add the `Retry-After` header from the exception.
    3. router.py: include `excel_router`.
    AVOID: `await request.body()` for chunks, because it buffers the whole body; iterate `request.stream()`.
    AVOID: wrapping handlers in `except Exception -> 500` (legacy drift).
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.api.v1.router import api_v1_router; print(sorted(r.path for r in api_v1_router.routes if '/excel' in r.path))" → lists the 10 routes</verify>
  <done>Ten routes under /api/v1/excel with the documented envelopes and headers.</done>
</task>

<task type="auto">
  <name>API tests through the real app and middleware stack</name>
  <files>
    tests/dataexchange/test_uploads_api.py
    tests/dataexchange/test_jobs_api.py
  </files>
  <action>
    Real app lifespan on the test DB with `EXCHANGE_WORKER_ENABLED=0` (jobs are finished by calling the worker's `_execute` directly in the test) and `httpx.AsyncClient(transport=httpx.ASGITransport(app=app))`; tokens minted with the project's JWTService for real users A and B.
    Uploads: chunked upload of a real 12 MB workbook in 3 chunks out of order + one chunk re-sent → complete succeeds and the file is byte-identical; status after 2 of 3 chunks lists the missing index; wrong sha256 → 422; chunk larger than chunk_size → 413; B using A's upload id → 404; a zip bomb completes upload but is rejected at complete; while an upload is in progress, a burst of 50 concurrent `PUT` chunk requests does not raise pool timeouts on a parallel normal endpoint (NFR-13).
    Jobs: no token → 401 on every route; A's list with 3 jobs and limit=2 → items 2, total 3, pages 2, has_more true, next_page 2; A gets B's job → 404; file of a QUEUED job → 409; of a COMPLETED job → 200, xlsx content type, `content-encoding: identity`, filename in Content-Disposition, body opens with openpyxl; `Range: bytes=0-99` → 206 with 100 bytes; running job has poll_after_ms; cancel active → CANCELLED, cancel finished → 409; queue full → 429 with Retry-After.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange -q → whole Phase 1 suite green</verify>
  <done>All upload and job API cases pass through auth + DatabaseMiddleware + GZip.</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` is green (whole Phase 1)
- [ ] Dev server smoke with a real token: upload a workbook in chunks, `GET /api/v1/excel/jobs` returns the envelope
- [ ] `/docs` shows the "Excel Import / Export" tag
</verification>

<success_criteria>
- [ ] All tasks verified
- [ ] Must-haves confirmed
- [ ] Phase 1 must-haves in ROADMAP.md can be ticked → `/verify 1` → phase commit message (see STATE.md Session Context)
</success_criteria>
