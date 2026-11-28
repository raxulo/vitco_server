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

## [DECISION-015] Remove legacy marketplace code, keep its tables, build on new `mkt_*` tables

**Date**: 2026-11-08
**Status**: Accepted (user decision, Phase 8)

### Decision
Old marketplace code, API and pages are deleted. Its tables (`animals`, `product_offers`,
`marketplace_orders` and the rest) stay untouched in existing databases. The new module uses only new
`mkt_*` tables. Dropping legacy tables is a separate, explicit step after the server data is checked.

### Why
- The server's data cannot be inspected from this workspace, so dropping tables could lose data for good.
- New table names let the new schema be designed freely; `create_all` never alters existing tables.

### Consequence
`animals`, `product_offers` and `marketplace_orders` reference `users` with `ON DELETE RESTRICT` and
SQLite runs with `foreign_keys=ON`. The Recycle Bin purge must keep deleting legacy rows, using table
definitions that do not depend on the removed models and that tolerate absent tables on fresh installs.

---

## [DECISION-016] Super Admin is the only seller now, with a seam for Admin / Sub Admin

**Date**: 2026-11-08
**Status**: Accepted (user decision, Phase 9)

### Decision
Every listing and order line stores `seller_user_id`. One `SellerPolicy` in the marketplace domain lists
the roles allowed to sell, currently only `SUPER_ADMIN`. Repository scope gives Super Admin every record
and any other seller only their own. Handlers call the policy and the scope; routers do not check seller
roles themselves.

### Why
The user wants Admin and Sub Admin able to sell later. Keeping that rule in one place means no schema
change and no rewrite. Tests run the scope with a non-Super-Admin seller so the seam stays proven.

---

## [DECISION-017] Animals are bought through enquiry, not the cart

**Date**: 2026-11-08
**Status**: Accepted (user decision, Phase 13)

### Decision
Animal detail pages offer Call, WhatsApp and an enquiry form. Animals never enter the cart or an order.
Enquiries are stored and worked in the Control Center; sold or reserved animals are controlled by listing status.

### Why
Buyers usually inspect an animal and negotiate before purchase.

---

## [DECISION-018] Guest checkout with Cash on Delivery first

**Date**: 2026-11-08
**Status**: Accepted (user decision, Phase 14)

### Decision
Orders need name, phone, address and pincode, with no account. Payment is COD. Orders store
`payment_method` and `payment_status`, and `buyer_user_id` stays nullable, so online payment and customer
accounts can be added later. The server computes prices and totals and ignores client amounts. Stock is
reduced with a guarded atomic `UPDATE ... WHERE stock >= quantity` inside the order transaction. Tracking
needs both the reference and the phone number.

### Why
This needs no SMS or payment provider now and leaves room for both later.

---

## [DECISION-019] Marketplace URLs are deny-by-default

**Date**: 2026-11-08
**Status**: Accepted (Phase 10)

### Decision
- Public storefront: `/marketplace/...`
- Public API: `/api/v1/marketplace/...`
- Control Center: `/admin/marketplace/...`
- Admin API: `/api/v1/admin/marketplace/...`

### Why
`AuthenticationMiddleware` treats `/marketplace` and `/api/v1/marketplace` as public prefixes through
`startswith`, so the old `/marketplace/setup` relied only on per-route checks, and a name like
`/marketplace-admin` would also be public. Admin routes live outside those prefixes and also enforce the role.

---

## [DECISION-020] Standalone storefront layout and design system

**Date**: 2026-11-08
**Status**: Accepted (Phase 12)

### Decision
The store gets its own `layouts/store.html` and token-based stylesheet instead of extending the dashboard
layout. It stays server-rendered with Jinja, HTMX and small vanilla JS modules, all self-hosted. Logged-in
users see the same store, with a link back to their dashboard.

### Why
A customer-facing shop needs its own navigation and visual language. No build step is added, and pages
do not depend on a CDN.

---

## [DECISION-021] Branch from the current work line, not `develop`

**Date**: 2026-11-08
**Status**: Accepted (user to confirm when reviewing the plan)

### Decision
`feature/marketplace-revamp` starts at commit `a345c6f`, the tip of `bugfix/static-asset-loading`.

### Why
`main` and `develop` are 35 commits behind that tip and lack recent work, including the Excel exchange and
Recycle Bin changes this milestone depends on. `develop` was not changed. Bringing it up to date stays the
user's decision.

---

## [DECISION-022] Marketplace images go through `MediaService`

**Date**: 2026-11-08
**Status**: Accepted (Phase 10)

### Decision
All marketplace images use the existing `MediaService` and `MediaCategory` values `PRODUCT`, `ANIMAL`,
`BANNER` and `CATEGORY`, not files under `static/uploads/`.

### Why
It already validates and stores files and serves them with long-lived cache headers, and it keeps user
uploads out of the source tree.

---

## [DECISION-023] No admin REST API in this milestone

**Date**: 2026-11-09
**Status**: Accepted (Phase 15)

### Decision
`/api/v1/admin/marketplace` from DECISION-019 is not built. The Control Center is a server-rendered website,
and sellers use nothing else. The URL stays reserved.

### Why
REQ-46 asks only for the public API, and no client needs an admin one. An unused admin API would be more to
secure with nothing gained.

---

## [DECISION-024] SQL statements stay out of the logs unless asked for

**Date**: 2026-11-09
**Status**: Accepted (Phase 15)

### Decision
`LoggerManager` sets the `sqlalchemy.*` loggers to WARNING unless `DATABASE_ECHO` is on. This applies to the whole app.

### Why
They were always at INFO, so every statement and its values reached the log files: buyer names, phones and
addresses, and password hashes. It also cost about 18 log records per store request. Database warnings and
errors are still logged.

---

## [DECISION-025] PostgreSQL is the default database; SQLite stays supported

**Date**: 2026-11-11
**Status**: Accepted (Phase 20)

### Decision
The default `DATABASE_URL` is PostgreSQL (`postgresql+asyncpg`). A `sqlite+aiosqlite` URL still works, so every
query must run on both. Postgres starts empty; SQLite data is not copied. Timestamp columns are naive on both, in IST.

### Why
The user asked for PostgreSQL. Keeping SQLite leaves the offline Windows exe and quick local runs working.
Naive timestamps keep the `now_naive_ist()` rule: `TIMESTAMPTZ` would read values back as UTC-aware and shift them.

---

## [DECISION-026] Alembic manages the schema, run at startup

**Date**: 2026-11-11
**Status**: Accepted (Phase 20)

### Decision
Migrations live in `app/core/database/migrations/`. Each process runs `alembic upgrade head` when it connects,
under a Postgres advisory lock. An existing SQLite database without `alembic_version` gets the old
`create_all` and column patches once and is then stamped at the baseline.

### Why
Startup `ALTER` patches only worked on SQLite and hid their errors. Versioned migrations work on both dialects
and can be reviewed. Running them at startup keeps setup to one step, as before.

---

## [DECISION-027] Excel scratch data in plain files, never sqlite3

**Date**: 2026-11-11
**Status**: Accepted (Phase 20; amends how DECISION-011 keeps dedupe on disk)

### Decision
The import's duplicate detector (`SeenKeys`) is an mmap hash table file of 128-bit BLAKE2b digests, and large
shared-string tables spill to a text file plus a fixed-size offset index. Both live in the job folder and are
deleted when the job ends. Only a SQLite `DATABASE_URL` uses `sqlite3`.

### Why
The server's Python 3.15 was built without `_sqlite3`, and the API would not even load because of these scratch
stores. The user chose files over temporary database tables: they work the same with either database, add no
database load during big imports, and keep memory flat (1M keys: 0.4 MB traced, 6.7 s vs 6.2 s with SQLite).

---

## [DECISION-028] Collection export as an Excel job with filters in the job folder

**Date**: 2026-11-12
**Status**: Accepted (Phase 21)

### Decision
MCC and VLCC collection exports are Excel jobs (`MCC_COLLECTION_EXPORT`, `VLCC_COLLECTION_EXPORT`), run by the
exchange worker like every other export. The list's filters are written to `params.json` in the job folder. The
worker reads collections as the requesting user through the list's own access scope, oldest first by keyset pages,
without deleted entries, and adds a Summary sheet with the filters and totals. Export only: collections are not
imported.

### Why
A collection list grows by thousands of rows a day, so the export must not run inside a web request
(DECISION-008). Keeping the filters in the job folder needs no `excel_jobs` column; only Postgres needs a
migration, for the two new enum values. Using the list's scope means the file can never show more than the list.

---

## [DECISION-029] MCC shift delay; the server stamps web collection entries

**Date**: 2026-11-14
**Status**: Accepted (Phase 22)

### Decision
Every MCC type (only MCCs, not VLCCs) has `shift_delay` ("HH:MM", 00:00 to 23:59, default "00:00"; user, 2026-11-14,
after first asking for FAT / SNF only). It is at most the MCC's morning shift start
time, compared as a whole time (user, 2026-11-14: 05:44 is allowed with a 06:00 start). The form types the ":"
itself and never lets hours pass 23 or minutes pass 59. A new collection entered on the web
is stamped by the server: entry time = now (IST) - the MCC's shift delay, which can fall on the previous day; for
VLCC collections there is no delay. The shift is taken from that time: Morning before the unit's morning shift end,
otherwise Evening (the dashboard's rule for the current shift); without settings the split is 12:00. Posted dates
and shifts are ignored, and an edit keeps the stored ones. The forms show both read-only, ticking from the server's
clock. Collections saved through the API keep the date and shift the app sends; sync gives the app
`mcc_info.shift_delay` so it applies the delay itself.

### Why
The user asked for it: an MCC receiving milk late records it at the time it was collected, and entry date / shift
must not be typed in. Stamping on the server means a wrong PC clock, time zone or edited form cannot change the
record; using the delayed time for the shift keeps late milk in the shift it was collected in.

---

## [DECISION-030] Per-user collection Excel column layout; deleted rows exported in red

**Date**: 2026-11-15
**Status**: Accepted (Phase 24, implemented and verified 2026-11-15)

### Decision
One combined catalogue of collection columns (`COLLECTION_COLUMNS`); the MCC and VLCC sheets each take the
columns that apply to them. Super Admin, Admin and Sub Admin each have one stored layout (order + visible) in
`excel_column_layouts` (unique per user and sheet group, JSON items); no row means the default, so nothing is
written when a user is created and later columns reach default users by themselves. Stored layouts are normalised
on read (unknown keys dropped, new catalogue keys inserted visible). The worker picks the layout: managers their
own; an MCC login its MCC's creator; a VLCC login its VLCC's creator, walked up to the MCC's creator when that is an
MCC user; anything else the default. Edits: self, Super Admin for any Admin / Sub Admin, Admin for its own Sub
Admins (user, 2026-11-15). Deleted entries are now exported (replaces that part of DECISION-028) with a red row
and Deleted = Yes; Summary totals still exclude them, as the list does.

### Why
The user wants every manager's downloads, and those of their MCCs / VLCCs, in the manager's chosen order, with one
list to maintain (user chose combined over per-sheet). Resolving in the worker keeps the API and mobile clients
unchanged. Keeping totals without deleted entries means the file still agrees with the list.

---

## [DECISION-031] Technical Support module: separate portal, team-owned roles, ticket per conversation

**Date**: 2026-11-18
**Status**: Accepted (planned in Phases 25 to 30; full design in `docs/TECHNICAL_SUPPORT_PLAN.md`)

### Decision
New module `app/modules/support/` (DDD + CQRS three layers). Support staff are rows in `users` with new `Role.SUPPORT = 8`
(1 to 7 unchanged); team, member and role data live in `support_*` tables. Only Super Admin creates a team, together
with its one Manager. Roles belong to a team and carry `support.*` permission strings; the Manager owns the team and may
do everything in it. Basic requester info, phone, device and app version are open to every member; dairy data is never
exposed. Requesters (MCC, VLCC, Farmer, VLCC_FARMER) use the mobile API only. The portal is a separate web area
(`/support`, `layouts/support.html`, `support.css` with `sp-` prefix) and never uses the dairy sidebar. Version 1 only:
SLA, auto-assign, availability, canned replies, CSAT, reports, voice notes and FAQ are later versions.

### Why
The user wants an independent support team structure with granular, manager-controlled permissions and a clean,
professional UI that has nothing to do with the dairy navigation. Reusing `users` keeps one login system; team-owned
roles let each manager shape their team without code changes.

---

## [DECISION-032] Redis for support realtime, with graceful fallback

**Date**: 2026-11-18
**Status**: Accepted (Phase 27)

### Decision
Redis (pub/sub, presence, unread cache) via `redis.asyncio`; production is one Linux instance. Redis is optional at
runtime: if it is down the app starts, events are delivered in-process, counts come from the database and the portal
polls. Configured with `REDIS_URL`; unset means the in-process fallback.

### Why
The user chose to add Redis now. Making it non-fatal keeps the dairy features (sync, collections) safe from a cache outage.

---

## [DECISION-033] Push notifications: backend now through an outbox, mobile later

**Date**: 2026-11-18
**Status**: Accepted (Phase 28)

### Decision
`support_device_tokens` and `support_notification_outbox`; a background sender calls FCM, retries, removes invalid
tokens, and skips users who are online. Without Firebase credentials it runs disabled and only logs. Mobile
registration and display are built later by the user.

### Why
Writing the event inside the ticket transaction and sending afterwards means a push failure never loses a reply.

---

## [DECISION-034] Push notifications are a shared module, not part of Technical Support

**Date**: 2026-11-22
**Status**: Accepted (user decision, Phase 28; refines DECISION-033)

### Decision
`app/modules/notification/` owns device tokens, the outbox, the FCM sender and the push worker, and knows no
feature. Any module queues a push with `NotificationService.notify(user_id, source, type, title, body,
reference_id, data, skip_if_online)` inside its own transaction. Tables are `notification_device_tokens` and
`notification_outbox` (no foreign key to feature tables); the app registers devices at `/api/v1/notifications/devices`
and routes a tapped push by `source`, `type` and `reference_id`. Skipping users who are online is per notification
(`skip_if_online`), checked against presence functions that modules register with the worker; support registers
its sockets. Technical Support keeps only its message texts (`support/application/push_messages.py`).

### Why
The user will send pushes from other modules later (payments, collections and others). One outbox, one sender and
one device list mean each new module only writes its texts, and the app has one registration call.

---

*Last updated: 2026-11-08*
