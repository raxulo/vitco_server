# DECISIONS.md — Architecture Decision Records

> **Purpose**: Log significant technical decisions and their rationale.
> **Milestone:** v1.1.0 — Excel Data Exchange

---

## Decisions

## [DECISION-001] Job-based processing for every export and import

**Date**: 2026-10-25
**Status**: Accepted — "in-process runner" part superseded by DECISION-008 (jobs run in a separate worker process)

### Context
`DatabaseMiddleware` (`app/bootstrap/middleware.py`) runs each request inside one transaction. An import of 100,000 rows inside a request would be one huge transaction: it would time out, hold the SQLite write lock, and roll back everything on any failure. A `StreamingResponse` export would outlive the request transaction, whose session closes when the middleware returns.

### Decision
Requests only create a job (`202 {job_id}`). A job runner executes the job in a fresh `contextvars.Context()` with its own sessions, commits in batches, persists progress in `excel_jobs`, and writes the result file to disk. Clients poll `GET /jobs/{id}` and download with `GET /jobs/{id}/file`.

### Rationale
The request stays short; memory stays bounded; a failure loses at most one batch; web and mobile share one flow; downloads are plain files (resumable, cacheable).

### Consequences
Clients must poll. Job files need cleanup (24 h). A restart interrupts running jobs (marked `FAILED`, safe to re-run).

### Alternatives Considered
- Synchronous request: rejected (timeouts, one giant transaction).
- `StreamingResponse` straight from the DB: rejected (session lifetime tied to the middleware transaction, no progress, no retry).
- External queue (Celery / RQ / Redis): rejected for now (new infrastructure; an in-process runner with a semaphore is enough for this deployment).

---

## [DECISION-002] openpyxl in read-only / write-only modes

**Date**: 2026-10-25
**Status**: Superseded by DECISION-012 (measured during Plan 1.2)

### Context
The project has no Excel library. Files can hold 100,000+ rows.

### Decision
Use `openpyxl==3.1.5` for both reading (`load_workbook(read_only=True, data_only=True)`) and writing (`Workbook(write_only=True)`). Parsing and writing run in a worker thread via `asyncio.to_thread`.

### Rationale
One pure-Python dependency covers both directions; both modes stream rows with constant memory; write-only mode still supports cell styles, number formats, freeze panes, AutoFilter and data validation.

### Consequences
openpyxl is CPU-bound pure Python, so it must stay off the event loop.

### Alternatives Considered
- `xlsxwriter` (write) + `openpyxl` (read): faster writes but two libraries. Can be swapped in later behind the same writer interface if the Phase 5 load test needs it.
- `pandas`: loads the whole sheet into memory — rejected.
- CSV only: loses dropdowns, colours and text formats that protect mobile / account numbers — rejected.

---

## [DECISION-003] Upsert keys and per-row discard policy

**Date**: 2026-10-25
**Status**: Accepted (user decision)

### Decision
- Farmers match by `farmer_code` within the selected VLCC; VLCCs match by `vlcc_code` within the selected owner. A match is updated, otherwise the row is inserted. An optional `create_only` mode discards existing codes instead of updating them.
- Mobile and email stay unique across all users. A row whose mobile or email belongs to another user, or repeats earlier in the file, is discarded alone; the import continues.
- On update, a blank cell keeps the stored value.

### Rationale
Re-uploading an edited export must be safe and idempotent; one bad row must not block thousands of good ones.

---

## [DECISION-004] Ownership selection by role

**Date**: 2026-10-25
**Status**: Accepted (user decision) — one open point

### Decision

| Login | Farmer exchange (pick VLCC) | VLCC exchange (pick owner) |
|-------|-----------------------------|----------------------------|
| Super Admin | any VLCC | any Admin / Sub Admin, required |
| Admin | VLCCs in its hierarchy | its Sub Admins; blank = itself |
| Sub Admin | VLCCs in its hierarchy | itself, locked |
| MCC | VLCCs it created | itself, locked |
| VLCC | itself, locked | not allowed |

Options endpoints return `{items, locked, default_id}`. The server re-checks every `vlcc_id` / `owner_id` against `Hierarchy` and forces the locked value whatever the client sends.

### Open point
Should Super Admin also be able to choose "Self" as the VLCC owner? Asked on 2026-10-25, not answered yet. Resolved by a `checkpoint:decision` in Plan 3.3.

### Assumption
MCC is treated like Sub Admin (own VLCCs, locked) because the code lets MCC users create VLCCs.

---

## [DECISION-005] Prodata import is an atomic replace

**Date**: 2026-10-25
**Status**: Accepted (user decision)

### Decision
The user picks an existing Prodata chart; the file's rows replace all of its rows in one transaction. Any invalid row rejects the whole file.

### Rationale
`save_prodata_rows` already has replace-all semantics; a half-replaced chart would price milk wrongly.

---

## [DECISION-006] Default password hashed once per job

**Date**: 2026-10-25
**Status**: Accepted (user decision)

### Decision
A blank password on insert becomes `Vitco@123` (the existing farmer API default). Its Argon2 hash is computed once per job and reused. Rows with their own password are hashed in a worker thread.

### Rationale
Argon2 costs ~50–100 ms per call and blocks the loop; 100,000 per-row hashes would take hours.

---

## [DECISION-007] Excel format: header-name matching, codes only

**Date**: 2026-10-25
**Status**: Accepted

### Decision
Row 1 is the header. Columns are matched by a normalised header name (case, spaces and a trailing `*` ignored), not by position; unknown columns are ignored. Export, template and import share one format. Files carry codes only, never UUIDs; passwords are never exported. The discarded-rows report repeats the columns plus `Row No` and `Reason`.

### Rationale
Users reorder or add columns in Excel; the same file must work across accounts; the error report can be fixed and re-uploaded directly.

---

## [DECISION-008] Jobs run in a separate, supervised worker process

**Date**: 2026-10-25
**Status**: Accepted (user requirement: "kitna bhi bada data ho, kabhi freeze, lag ya server crash na ho")

### Context
The server runs one Uvicorn process (`run_server.py`: `workers=1`). A thread in the same process still competes for the GIL, so openpyxl parsing / writing and Argon2 hashing would slow every API request; an out-of-memory error or a native crash inside a job would kill the whole API.

### Decision
- The API process never executes jobs. It only validates the request, stores the file and inserts a `QUEUED` row in `excel_jobs`.
- A dedicated worker process (`python -m app.worker.exchange`) claims jobs from the table with an atomic `UPDATE … WHERE status = QUEUED`, runs them, and writes heartbeat / progress rows.
- The API lifespan starts the worker as a child process (`multiprocessing` spawn context) and supervises it: if it dies it is restarted with back-off (1 s → 30 s); the worker exits on its own when its parent PID disappears. No change to the existing `nohup` / `run_server.py` deployment.
- The worker caps its own memory (Linux `resource.setrlimit(RLIMIT_AS)` = `EXCHANGE_WORKER_MAX_MEMORY_MB`, default 1024) and checks its RSS every batch; above the soft limit it shrinks the batch size, above the hard limit it fails the job cleanly instead of being OOM-killed.
- A watchdog in the API marks a `RUNNING` job `FAILED` when its heartbeat is older than `EXCHANGE_HEARTBEAT_TIMEOUT_S` (default 120 s), so a frozen worker never leaves a job stuck.

### Rationale
Process isolation is the only way to guarantee that a job cannot freeze, slow down or crash the API, whatever the file size. Polling the job table needs no new infrastructure (no Redis / Celery) and works the same on SQLite and PostgreSQL.

### Consequences
Two processes write to SQLite; WAL mode (already on) allows concurrent readers and one writer, so writes must stay short (DECISION-010). Job pickup latency is the poll interval (default 1 s).

### Alternatives Considered
- Thread in the API process: rejected (GIL contention → lag; a crash takes the API down).
- `ProcessPoolExecutor` per CPU step: rejected (pickling batches back and forth, the DB work still in the API process).
- Celery / RQ + Redis: rejected for now (new infrastructure to deploy and monitor on the server).

---

## [DECISION-009] Resumable chunked upload outside the request transaction

**Date**: 2026-10-25
**Status**: Accepted

### Context
`DatabaseMiddleware` holds a pooled DB connection for the whole request. A large upload over a slow mobile network would hold it for minutes; a handful of parallel uploads would exhaust the pool and freeze the API. A dropped network would also force a full re-upload.

### Decision
- Upload paths (`/api/v1/excel/uploads*`) are exempt from the request-wide transaction; their handlers open a short transaction only to write metadata.
- Large files use a resumable chunked protocol: `POST /excel/uploads` (size, sha256) → `PUT /excel/uploads/{id}/chunks/{n}` (≤ 5 MB each, idempotent) → `POST /excel/uploads/{id}/complete` (size + sha256 verified) → the import request references `upload_id`. Missing chunks can be re-sent after a network drop.
- Small files (≤ 10 MB) may still use a single multipart request on the same exempt path.

### Rationale
No request ever holds a DB connection while bytes are on the wire; mobile uploads survive network drops; integrity is verified before a job starts.

---

## [DECISION-010] Write-lock budget and adaptive batching

**Date**: 2026-10-25
**Status**: Accepted

### Context
SQLite has one writer at a time and `busy_timeout=5000`; any write transaction the worker holds makes API writes wait.

### Decision
- Each worker write transaction targets ≤ `EXCHANGE_TX_BUDGET_MS` (default 250 ms). The batch size adapts: start at 200 rows, halve when a transaction exceeds the budget, grow by 25% (max 500) when it is well under, never below 20.
- Between batches the worker yields (`await asyncio.sleep(EXCHANGE_BATCH_PAUSE_MS / 1000)`, default 20 ms) so waiting API writers get the lock.
- Exports read in keyset pages of 1,000 rows in short read transactions (WAL readers never block writers).
- Pre-checks for a batch run as one `IN (…)` query per unique key (≤ 500 values, below SQLite's parameter limit).

### Rationale
API writes wait at most one batch budget (~250 ms) instead of seconds; throughput self-tunes to the server.

---

## [DECISION-011] Bounded resources whatever the file size

**Date**: 2026-10-25
**Status**: Accepted

### Decision
- **Memory:** rows are streamed in and out; duplicate-in-file detection (codes, mobiles, emails) uses a disk-backed SQLite scratch database in the job folder with unique indexes (`INSERT OR IGNORE`), not Python sets; the discarded-rows report is streamed to its file.
- **Hostile files:** before parsing, the zip directory is inspected: reject when total uncompressed size > `EXCHANGE_MAX_UNCOMPRESSED_MB` (default 2048), any member's compression ratio > 100, or more than 10,000 members. `defusedxml` is installed so openpyxl refuses XML entity expansion.
- **Empty / padded sheets:** reading stops after 1,000 consecutive empty rows (sheets formatted down to row 1,048,576 do not cost a full scan).
- **Excel row limit:** exports split automatically into `Farmers`, `Farmers (2)`, … at 1,048,575 data rows per sheet; imports read every sheet whose header row matches the spec.
- **Limits are configurable, not hard-coded:** `EXCHANGE_MAX_UPLOAD_MB` (default 500), `EXCHANGE_MAX_ROWS` (default 5,000,000).
- **Disk:** before an upload or an export starts, free space must exceed `EXCHANGE_MIN_FREE_DISK_MB` (default 1024) plus the expected file size, else `507 Insufficient Storage`; the worker re-checks every 10,000 rows and fails the job cleanly when disk runs low.
- **Backpressure:** at most `EXCHANGE_MAX_QUEUED_JOBS` (default 20) queued jobs in total and 1 active job per user per kind; beyond that the API answers `429` with `Retry-After`.
- **Polling:** the job status response carries `poll_after_ms` (1,000 ms while running, grows to 5,000 ms for long jobs); the status endpoint is a single primary-key read.
- **Downloads:** sent with `Content-Encoding: identity` so `GZipMiddleware` skips them (xlsx is already compressed), streamed from disk with Range support.

### Rationale
"Any size" becomes "size only changes the duration": memory, DB lock time, CPU share and disk use are all bounded, and every limit fails with a clear message instead of a crash.

---

## [DECISION-012] Own expat streaming reader + xlsxwriter (replaces openpyxl at runtime)

**Date**: 2026-10-25
**Status**: Accepted (user decision during Plan 1.2, executor Rule 4)

### Context
Measured on the dev machine (Python 3.14, 100,000 rows × 21 farmer-like columns):

| Engine | Speed | Memory |
|--------|-------|--------|
| openpyxl `read_only` | 2,864 rows/s | loads the whole `sharedStrings.xml` into memory (Excel-saved files always use it) → grows with unique values |
| own reader on stdlib `xml.parsers.expat` | 15,649–18,130 rows/s | 7.5 MB peak, constant |
| openpyxl `write_only` | 4,526 rows/s | 0.7 MB |
| xlsxwriter 3.3.0 `constant_memory` | 7,604 rows/s | 0.8 MB |

openpyxl also ran without lxml (`openpyxl.xml.LXML = False`). Its write-only sheets have no `add_data_validation`; validations go through `ws.data_validations`.

### Decision
- **Read:** an own streaming reader in `infrastructure/xlsx.py` on stdlib `zipfile` + `xml.parsers.expat`. Shared strings stay in memory up to 100,000 entries, beyond that they move to a scratch SQLite file in the job folder (lookups per batch with a small LRU cache). The parser rejects DOCTYPE / entity declarations itself and caps a cell at Excel's 32,767 characters.
- **Write:** `xlsxwriter==3.3.0` with `constant_memory` and `tmpdir` = the job folder. Strings are written inline; formats are explicit per cell for text columns; validations, freeze panes, AutoFilter and column widths are set up front.
- **openpyxl** moves to `requirements-dev.txt`, used by the tests as an independent reader of our output. `defusedxml` is dropped (no runtime openpyxl XML parsing left).

### Rationale
The reader is 5–6× faster with flat memory whatever the number of unique values (NFR-01). The writer is 1.7× faster and mature. Fewer runtime dependencies.

### Consequences
We own ~300 lines of xlsx reading code, covered by tests against files written by xlsxwriter, by openpyxl and by hand-built XML (shared strings, inline / rich text, formulas, booleans, gaps). Excel features we do not read (styles, dates as serials) are not needed by our column specs; TIME cells stored as day fractions are converted.

---

## [DECISION-013] Recycle bin purge deletes the whole ownership tree and its data

**Date**: 2026-11-04
**Status**: Accepted (user decision, Phase 7)

### Context
Foreign keys are enforced (`PRAGMA foreign_keys=ON`). A soft-deleted Admin / MCC / VLCC is still the
`created_by` of other users and masters, and owns collections, payments, rate charts and advances.

### Decision
Permanently deleting a soft-deleted record removes the record, every user / MCC / VLCC / farmer below
it in the `created_by` tree (active ones too), and every row that references any of them. Super Admins
are never part of a tree. Rate charts created inside the tree are deleted only when no surviving user
is assigned to them; otherwise they stay with `created_by` NULL. Survivors' account balances are
corrected by reversing their ledger entries of deleted transfers.

### Consequences
One click can remove thousands of rows, so the confirm dialog shows the full impact and asks for the
record's code / name. The purge runs in one transaction; it cannot be undone.

---

## [DECISION-014] Admin / Sub Admin delete is a soft delete

**Date**: 2026-11-04
**Status**: Accepted (user decision, Phase 7)

### Decision
`UserHandler.delete` marks the user deleted (`is_deleted`, `deleted_at`, `deleted_by`, inactive) and
frees email / mobile with a `del_<hex6>_` prefix, like farmers. Deleted users are excluded from
`UserRepository.list`. Permanent removal happens only from the recycle bin.

---

*Last updated: 2026-10-25*
