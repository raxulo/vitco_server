---
phase: 1
researched_at: 2026-10-25
discovery_level: 2
---

# Phase 1 Research — Exchange Foundation

## Objective
How do we run very large Excel imports / exports inside this FastAPI + async SQLAlchemy app without blocking the event loop, growing memory, or losing data — given the existing request-wide transaction?

## Discovery Level
**Level 2** — Standard research (new external library + background-execution design).

## Key Decisions

### Decision 1: Where the work runs
**Question:** Request, streaming response, or background job?
**Options Considered:**
1. Inside the request: one transaction for the whole file (`DatabaseMiddleware`), request timeouts, full rollback on failure.
2. `StreamingResponse`: the generator outlives the middleware transaction; the ContextVar still points at a closed session; no progress or retry.
3. In-process background job with a persisted job row: short requests, batch commits, progress, resumable downloads.

**Decision:** Option 3 — see DECISION-001.
**Confidence:** High

### Decision 2: Excel library
**Options Considered:**
1. `openpyxl 3.1.5`: read-only and write-only streaming modes, styles / data validation / freeze panes in write-only mode, pure Python (works on Python 3.14 in `.venv`).
2. `xlsxwriter` + `openpyxl`: faster writes, two dependencies.
3. `pandas`: whole sheet in memory.

**Decision:** Option 1 — see DECISION-002.
**Confidence:** High

### Decision 3: Test tooling
The repo has no runnable tests (`tests/` holds only `.pyc` files) and no pytest in `.venv`.
**Decision:** Add `requirements-dev.txt` with `pytest==9.1.1` and `pytest-asyncio==1.4.0`; tests use a temporary SQLite file database.
**Confidence:** High

## Findings

### Request transaction and ContextVars
- `app/bootstrap/middleware.py` → `DatabaseMiddleware.dispatch` wraps `call_next` in `database.transaction()`.
- `app/core/database/transaction.py` keeps the session in `_CURRENT_SESSION: ContextVar`; a nested `transaction()` becomes a SAVEPOINT on the current session.
- `asyncio.create_task(coro)` copies the current context, so a task started from a request would reuse the request session (closed when the request ends).
- **Fix:** `asyncio.create_task(coro, context=contextvars.Context())` gives the job an empty context; its `database.transaction()` then opens a brand-new session and commits on exit. Each batch is its own top-level transaction; `transaction()` calls inside the batch become savepoints (one per row).

### openpyxl streaming behaviour
- `load_workbook(path, read_only=True, data_only=True)` + `ws.iter_rows(values_only=True)` yields tuples lazily; memory stays flat. The worksheet `dimension` can be wrong for files written by other tools, so the row count for progress is an estimate (`ws.max_row`) and the real count comes from iteration.
- `Workbook(write_only=True)`: rows are appended and flushed to a temp file; cells can be `WriteOnlyCell` with `font`, `fill`, `number_format`. `ws.freeze_panes`, `ws.auto_filter.ref`, `ws.add_data_validation(...)` and `ws.column_dimensions[...]` work in write-only mode **if set before the first `append`**.
- Text format for long numbers: write the value as `str` and set `number_format = "@"`, otherwise Excel shows `9.87E+09` and drops digits after the 15th (account numbers).
- Read side: Excel may return a mobile as `int` or `float` (`9876543210.0`); the cell parser must normalise numbers back to digit strings.
- Data validation lists longer than 255 characters must reference a range on a hidden sheet; our lists are short, so inline lists are fine.

### Uploads
- `UploadFile` is a `SpooledTemporaryFile` (spills to disk above 1 MB). Copy it in 1 MB chunks with `aiofiles` into the job folder, counting bytes and stopping above the limit.
- An `.xlsx` is a ZIP: the first four bytes are `PK\x03\x04`. Reject anything else before the job starts.

### Password hashing
- `app/modules/auth/infrastructure/password.py` uses Argon2 `time_cost=3`, `memory_cost=65536` — synchronous and slow by design. Hash the default password once per job; hash custom passwords with `asyncio.to_thread`.

### Table creation
- No Alembic. `SQLiteDriver.connect` runs `Base.metadata.create_all`, so `excel_jobs` is created as long as its model module is imported before startup (importing the repository from `app/modules/configurator.py` does that).

### Scope & files
- Storage roots exist in `app/config/settings.py`: `STORAGE_PATH`, `TEMP_PATH`, `DOWNLOAD_PATH`. Job files go to `STORAGE_PATH / "exchange" / <job_id>/`.

### Hardening findings (added 2026-10-25 — rule: never freeze, lag or crash, whatever the size)
- **Single process:** `run_server.py` runs `uvicorn.run(app, workers=1)` and `run_on_background.sh` starts one process with `nohup`. A job in a thread of that process still shares the GIL (openpyxl and Argon2 are CPU-bound pure Python / C holding the GIL in parts), so API latency would rise during a job; an OOM would kill the API. → DECISION-008: separate worker process, started and supervised by the API lifespan.
- **SQLite locking:** `drivers/sqlite.py` sets `journal_mode=WAL`, `synchronous=NORMAL`, `busy_timeout=5000`. Two processes can share the DB (WAL: many readers + one writer), but any write transaction longer than 5 s makes waiting writers fail with "database is locked". → DECISION-010: ≤ 250 ms write transactions, adaptive batch size, a short pause between batches.
- **Connection pool:** `engine.py` creates SQLite engines without pool arguments (SQLAlchemy default queue pool, small size, 30 s timeout), and `DatabaseMiddleware` holds a session per request. Slow uploads inside the middleware transaction would exhaust it. → DECISION-009: upload paths skip the request transaction; resumable chunked uploads.
- **GZip:** Starlette 1.3.1 `GZipMiddleware` only skips responses that already carry `Content-Encoding` or are `text/event-stream` (checked in `.venv`). xlsx downloads would be re-compressed (wasted CPU, broken Range). → send `Content-Encoding: identity`.
- **Excel limits:** 1,048,576 rows × 16,384 columns per sheet. → split exports across sheets; read every matching sheet.
- **Hostile files:** xlsx is a ZIP of XML. Inspect the zip directory (sizes, ratios, member count) without extracting; `defusedxml` makes openpyxl refuse entity expansion (`openpyxl.xml.DEFUSEDXML`).
- **In-file duplicates:** keeping 1M+ keys in Python sets costs 100+ MB and grows with the file. A scratch SQLite DB with a `WITHOUT ROWID` primary key keeps memory flat.
- **Existing config:** `app/config/filesystem.py` already defines chunk / resume storage settings (`chunk_storage_config`, `resume_storage_config`) that nothing uses yet; the upload service may reuse the `.chunk` naming but needs no dependency on them.

## Patterns to Follow
- Module recipe from AGENTS.md / existing modules (`masters/units`, `farmer`): `domain/` (entities, enums, exceptions, `irepository.py`, dto), `infrastructure/` (models, repository, mapper), `application/` (command, handler).
- Exceptions subclass `app.core.exceptions.base.ApplicationException` with class attributes `code`, `message`, `status_code`.
- Timestamps via `app.core.clock.now_naive_ist()`.
- DI: repository in `ModuleConfigurator._repo_config`, handler via a `_dataexchange` classmethod in `_handler_config`, accessor `GetHandler.excel_handler(request)`.
- Envelopes: list `{status, code, message, items, limit, offset, total, pages, next_page, has_more}` with a local `_compute_pagination`; single `{status, code, message, data}`.

## Anti-Patterns to Avoid
- `asyncio.create_task` without `context=contextvars.Context()` — leaks the request session into the job.
- One transaction per file — one bad row or a crash loses everything; holds the SQLite write lock.
- `OFFSET` pagination for export — gets slower on every page; use keyset (`WHERE id > :last ORDER BY id`).
- Calling openpyxl or Argon2 on the event loop — freezes every other request.
- `pandas.read_excel` / `ws.iter_rows()` without `read_only=True` — loads the whole file into memory.
- `datetime.now()` — use `now_naive_ist()`.

## Dependencies Identified
| Package | Version | Purpose |
|---------|---------|---------|
| openpyxl | 3.1.5 | Streaming xlsx read / write (runtime, `requirements.txt`) |
| pytest | 9.1.1 | Tests (dev, `requirements-dev.txt`) |
| pytest-asyncio | 1.4.0 | Async tests (dev, `requirements-dev.txt`) |

## Risks
- **openpyxl write speed** (~20–40k rows/s plain, slower with styles): mitigated by styling only the header row and per-column number formats; Phase 5 load test decides whether to swap in `xlsxwriter`.
- **Multiple Uvicorn workers:** the semaphore and the per-user lock are per process. Mitigated by also checking for an active job row in the DB before creating a new one.
- **Restart during a job:** mitigated by startup recovery (`RUNNING`/`QUEUED` → `FAILED` with `processed` kept) and idempotent upserts.

## Recommendations for Planning
1. Wave 1: job domain + persistence (adds dependencies and settings for everything else).
2. Wave 2 (parallel, no shared files): column specs + streaming xlsx; file safety (storage, hostile-file guard, disk guard, duplicate store).
3. Wave 3: worker process engine (processor protocol, adaptive batching, memory guard, claim / heartbeat / cancel).
4. Wave 4: supervisor in the API lifespan, handler with backpressure, DI.
5. Wave 5: resumable uploads + job REST API.
6. Entity adapters (farmer, VLCC, prodata) plug into the `ExchangeProcessor` protocol and use `run_batch`, `checkpoint`, `SeenKeys`, `XlsxSheetReader/Writer`, so Phases 2–4 add no changes to the worker.
