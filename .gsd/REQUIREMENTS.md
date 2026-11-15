---
milestone: Excel Data Exchange (v1.1.0)
updated: 2026-10-25T00:00:00+05:30
---

# Requirements

## Overview

Requirements derived from SPEC.md Goal 6 for traceability and coverage tracking.
Decisions behind them: [DECISIONS.md](DECISIONS.md).

---

## Functional Requirements

### Foundation (Phase 1)

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-01 | Every export / import runs as a background job: the request returns `202 {job_id}` at once, and `GET /api/v1/excel/jobs/{id}` returns status, progress and counts | Goal 6 | 1 | Pending |
| REQ-02 | Job state (status, total, processed, inserted, updated, discarded, file paths, error) is persisted in an `excel_jobs` table, so it survives restarts and is visible to any worker | Goal 6 | 1 | Pending |
| REQ-03 | A finished job's file (export result or discarded-rows report) downloads from `GET /api/v1/excel/jobs/{id}/file`, streamed from disk; only the job's creator (or Super Admin) may read or download it | Goal 6 | 1 | Pending |
| REQ-04 | One column-spec definition per entity drives the template, the export, the import validation and the Instructions sheet | Goal 6 | 1 | Pending |
| REQ-05 | Workbook format: row 1 is the header; data starts at row 2; header frozen with AutoFilter; required headers end with `*`; header fill colour per section; text format for mobile, account number, pincode, IFSC and code columns; dropdowns for enum and YES/NO columns; a second `Instructions` sheet | Goal 6 | 1 | Pending |

### Farmers (Phase 2)

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-06 | Farmer export / import first asks for a VLCC. VLCC login: its own VLCC, locked. MCC / Sub Admin / Admin: searchable VLCCs inside their hierarchy. Super Admin: all VLCCs | Goal 6 | 2 | Pending |
| REQ-07 | Farmer export returns every non-deleted farmer of the selected VLCC in the farmer sheet format (18 columns: farmer 5, user 4 incl. import-only password, address 4, bank 5) | Goal 6 | 2 | Pending |
| REQ-08 | Farmer import upserts by `farmer_code` inside the selected VLCC: a matching farmer is updated, otherwise one is inserted | Goal 6 | 2 | Pending |
| REQ-09 | A row is discarded (and the rest continue) when: a required cell is blank; a value has the wrong format; its mobile or email belongs to another user (deleted users included); its code / mobile / email repeats earlier in the same file; or its code belongs to a soft-deleted farmer | Goal 6 | 2 | Pending |
| REQ-10 | On update a blank cell keeps the stored value; a blank password on insert becomes `Vitco@123` | Goal 6 | 2 | Pending |
| REQ-11 | The import result shows total / inserted / updated / discarded, and the discarded-rows file has the same columns plus `Row No` and `Reason`, so it can be fixed and uploaded again as-is | Goal 6 | 2 | Pending |

### VLCCs (Phase 3)

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-12 | VLCC export / import first asks for an owner. Super Admin: all Admins and Sub Admins, required. Admin: its Sub Admins, blank = itself. Sub Admin: itself, locked. MCC: itself, locked | Goal 6 | 3 | Pending |
| REQ-13 | VLCC export returns the VLCCs whose `created_by` is the selected owner, in the VLCC sheet format (44 columns: VLCC, user, address, bank, settings, milk quality) | Goal 6 | 3 | Pending |
| REQ-14 | VLCC import upserts by `vlcc_code` among the owner's VLCCs; a new VLCC gets `created_by` = the selected owner, not the logged-in user | Goal 6 | 3 | Pending |
| REQ-15 | Besides the REQ-09 rules, a VLCC row is discarded when its code is already used in the owner's hierarchy line (`Hierarchy.code_conflict`) | Goal 6 | 3 | Pending |
| REQ-16 | Blank settings / milk quality cells on a new VLCC take the same defaults as the VLCC create form | Goal 6 | 3 | Pending |

### Prodata rate chart (Phase 4)

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-17 | Prodata export returns the rows of one chart the user can see, in row order | Goal 6 | 4 | Complete |
| REQ-18 | Prodata import replaces all rows of one chart the user may modify, in one transaction. Any invalid row (e.g. `fat_min > fat_max`, overlapping FAT/SNF ranges) rejects the whole file and saves nothing, with a report | Goal 6 | 4 | Complete |

### Web panel (Phase 5)

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-19 | The Farmer, VLCC and Rate Chart list pages have Export / Import / Template actions, a VLCC or owner dropdown (disabled when locked), live progress and a result summary card | Goal 6 | 5 | Complete |

### Formula rate chart (Phase 6)

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-20 | Formula export returns the formula configuration (Cow/Buffalo std FAT, SNF, Rate, FAT% / SNF%) plus an expanded calculated pricing matrix preview sheet (FAT x SNF grid) of one chart the user can see | Goal 6 | 6 | Pending |
| REQ-21 | Formula import validates and atomically updates the formula configuration of an existing chart, or creates a new Formula rate chart from the uploaded Excel file. Invalid formulas (non-positive standards, FAT% + SNF% != 100%) reject with a clear report | Goal 6 | 6 | Pending |


---

## Non-Functional Requirements

> Guiding rule (user, 2026-10-25): **"kitna bhi bada data ho, kabhi freeze, lag ya server crash na ho."**
> File size may only change how long a job takes, never memory, DB lock time, API latency or stability.

| ID | Requirement | Category | Phase | Status |
|----|-------------|----------|-------|--------|
| NFR-01 | **Constant memory:** worker peak RSS stays below `EXCHANGE_WORKER_MAX_MEMORY_MB` (default 1024) and does not grow with file size — measured at 100k, 1M and 5M rows (growth between 100k and 5M < 50 MB) | Performance | 1, 5 | Pending |
| NFR-02 | **No lag:** while a 1,000,000-row import or export runs, other API endpoints keep p95 < 300 ms and p99 < 1 s, and the API event-loop lag stays < 100 ms | Performance | 1, 5 | Pending |
| NFR-03 | **No data loss:** writes commit in adaptive batches (≤ 500 rows) with a savepoint per row; killing the worker at any moment loses at most the uncommitted batch, never leaves a half-written row (user without farmer, farmer without user); the job ends `FAILED` with `processed_rows`; re-running the same file is safe (idempotent upsert) | Reliability | 1, 2, 3 | Pending |
| NFR-04 | **Backpressure:** at most `EXCHANGE_MAX_CONCURRENT_JOBS` (2) running jobs, `EXCHANGE_MAX_QUEUED_JOBS` (20) queued jobs, 1 active job per user per kind; beyond that `429` + `Retry-After`, never a slowdown | Reliability | 1 | Pending |
| NFR-05 | **Safe uploads:** streamed to disk, resumable in ≤ 5 MB chunks with sha256 verification, rejected above `EXCHANGE_MAX_UPLOAD_MB` (500) or when the file is not a real `.xlsx` | Security | 1 | Pending |
| NFR-06 | Job files are deleted `EXCHANGE_FILE_TTL_HOURS` (24) after the job finishes | Operations | 1 | Pending |
| NFR-07 | **Crash isolation:** jobs never run in the API process; a worker crash, freeze or out-of-memory never stops the API; the supervisor restarts the worker within 30 s; a job with a heartbeat older than 120 s is marked `FAILED` | Reliability | 1 | Pending |
| NFR-08 | **Short DB locks:** every worker write transaction targets ≤ 250 ms (adaptive batch size); API writes during a job never fail with "database is locked" | Reliability | 1, 2, 3 | Pending |
| NFR-09 | **Hostile files are rejected before parsing:** zip bombs (uncompressed > 2 GB, ratio > 100, > 10,000 members), XML entity expansion (defusedxml), non-xlsx content; a sheet padded with empty rows stops after 1,000 empty rows | Security | 1 | Pending |
| NFR-10 | **Any row count:** exports above 1,048,575 rows split into numbered sheets; imports read every matching sheet; limit `EXCHANGE_MAX_ROWS` (5,000,000) is configurable | Scalability | 1 | Pending |
| NFR-11 | **Disk guard:** uploads and exports refuse to start with `507` when free disk < 1 GB + expected size; a running job fails cleanly when disk runs low | Reliability | 1 | Pending |
| NFR-12 | **Cheap polling:** job status is one primary-key read and returns `poll_after_ms`; 500 clients polling every second keep p95 < 50 ms for the status endpoint | Performance | 1, 5 | Pending |
| NFR-13 | **No connection hogging:** upload requests never hold a DB connection while receiving bytes (exempt from the request-wide transaction) | Reliability | 1 | Pending |
| NFR-14 | **Efficient downloads:** job files are not gzipped by `GZipMiddleware` (`Content-Encoding: identity`), stream from disk, and support Range / resume | Performance | 1 | Pending |

### Recycle Bin (Phase 7)

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-22 | A "Recycle Bin" page under General, visible and reachable only for Super Admin | User 2026-11-04 | 7 | Complete |
| REQ-23 | The page lists soft-deleted Admins, Sub Admins, MCCs, VLCCs and Farmers (tab per type, search, pagination) | User 2026-11-04 | 7 | Complete |
| REQ-24 | Each row has a permanent delete; the confirm dialog shows everything that will be removed | User 2026-11-04 | 7 | Complete |
| REQ-25 | Permanent delete removes the record, its whole ownership tree and all dependent data in one transaction; survivors' balances stay correct (DECISION-013) | User 2026-11-04 | 7 | Complete |
| REQ-26 | Deleting an Admin / Sub Admin from Managed Admins is a soft delete (DECISION-014) | User 2026-11-04 | 7 | Complete |
| REQ-27 | The bin shows who soft-deleted each record and when (list and confirm dialog) | User 2026-11-04 | 7 | Complete |

### Marketplace Revamp (v1.2.0, Phases 8–15)

**Legacy removal**

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-28 | All old marketplace UI, web routes, API, module code, cart and uploaded demo images are removed; the app starts and its tests pass without them | User 2026-11-08 | 8 | Complete |
| REQ-29 | Legacy marketplace tables and their rows are not altered or dropped by startup, and the Recycle Bin can still purge a user who owns legacy rows (DECISION-015) | User 2026-11-08 | 8 | Complete |

**Seller model**

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-47 | Only Super Admin can create or manage listings now. Every listing and order line records its seller, one policy decides which roles may sell, and repository scope limits non-Super-Admin sellers to their own records, so enabling Admin / Sub Admin needs no schema change (DECISION-016) | User 2026-11-08 | 9, 10 | Complete |

**Control Center**

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-30 | Super-Admin-only Control Center with an overview: listings, low stock, new orders, new enquiries | User 2026-11-08 | 10 | Complete |
| REQ-31 | Manage nested categories: name, slug, image, order, active | User 2026-11-08 | 10 | Complete |
| REQ-32 | Manage products: category, brand, description, specifications, gallery, variants (size, SKU, MRP, price, stock), draft / published / archived, featured and trending | User 2026-11-08 | 10 | Complete |
| REQ-33 | Manage animals: type, breed, price, negotiable flag, age, lactation number, milk litres per day, FAT %, pregnancy and calf details, health and vaccination notes, location, description, gallery, draft / published / reserved / sold, featured and trending; manage the animal type and breed masters | User 2026-11-08 | 10 | Complete |
| REQ-34 | Manage storefront content: scheduled banners, trending items, and the order and visibility of home sections | User 2026-11-08 | 11 | Complete |
| REQ-35 | Manage store settings: brand, contact and WhatsApp numbers, delivery charge, free-delivery threshold, minimum order, COD switch, serviceable pincodes, policy pages, store open or closed | User 2026-11-08 | 11 | Complete |
| REQ-36 | Manage enquiries (new / contacted / closed) and orders (placed → confirmed → packed → out for delivery → delivered, or cancelled, with stock restored on cancel) | User 2026-11-08 | 13, 14 | Complete |

**Storefront**

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-37 | Public home page: search, category navigation, banner carousel, trending, featured animals and products, all driven by the Control Center; empty sections hide themselves | User 2026-11-08 | 12 | Complete |
| REQ-38 | Product listing: search, category, price and availability filters, sorting, pagination | User 2026-11-08 | 13 | Complete |
| REQ-39 | Animal listing: search and filters for type, breed, price, milk litres per day, lactation and location; sorting and pagination; cards show price, lactation and milk litres per day | User 2026-11-08 | 13 | Complete |
| REQ-40 | Product detail page: gallery, variant selection, MRP, price and discount, stock state, description, specifications, related products | User 2026-11-08 | 13 | Complete |
| REQ-41 | Animal detail page: image gallery, price, lactation, milk litres per day, every specification, full description, seller location, similar animals | User 2026-11-08 | 13 | Complete |
| REQ-42 | Animals are not added to the cart; the detail page offers Call, WhatsApp with a prefilled message, and a validated enquiry form (DECISION-017) | User 2026-11-08 | 13 | Complete |
| REQ-43 | Cart: add, change quantity, remove, live totals; survives reload; revalidated against the server | User 2026-11-08 | 14 | Complete |
| REQ-44 | Guest COD checkout: name, phone, address and pincode validated; prices, totals and delivery charge are computed on the server; stock cannot go negative under concurrent orders (DECISION-018) | User 2026-11-08 | 14 | Complete |
| REQ-45 | Order confirmation with a reference; tracking requires both the reference and the phone number | User 2026-11-08 | 14 | Complete |
| REQ-46 | New `/api/v1/marketplace` REST API for browsing, enquiries, orders and tracking, using the standard envelopes; it replaces the old API | User 2026-11-08 | 15 | Complete |

**Collection export**

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-48 | MCC collections can be exported to Excel from their list, with the list's filters (search, MCC, VLCC, milk type, date and shift range); the file holds exactly the rows the list shows that user, without deleted entries, plus a Summary sheet with the filters and totals (DECISION-028) | User 2026-11-12 | 21 | Complete |
| REQ-49 | VLCC collections can be exported to Excel the same way, with the VLCC list's filters (farmer search, VLCC, milk type, date and shift range) (DECISION-028) | User 2026-11-12 | 21 | Complete |

**Collection entry time**

| ID | Requirement | Source | Phase | Status |
|----|-------------|--------|-------|--------|
| REQ-50 | Every MCC (any type) has a Shift Delay ("HH:MM", default 00:00, the ":" typed by the form, hours ≤ 23, minutes ≤ 59, at most the morning shift start time), set in the MCC form's Collection Shifts section and sent by sync as `mcc_info.shift_delay` (DECISION-029) | User 2026-11-14 | 22 | Complete |
| REQ-51 | An MCC collection entered on the web is saved at now - the MCC's shift delay (previous day when it crosses midnight); API collections are not changed (DECISION-029) | User 2026-11-14 | 22 | Complete |
| REQ-52 | On the MCC and VLCC collection forms, entry date and shift are read-only; a new entry's date and time follow the live clock, and its shift comes from the selected MCC's / VLCC's shift timings (DECISION-029) | User 2026-11-14 | 22 | Complete |
| REQ-53 | MCC and VLCC collection exports carry Chart Rank (`R{rank}`, blank without a rank), Quantity Mode and Measurement Mode (Manual / Automatic) (DECISION-030) | User 2026-11-15 | 24 | Complete |
| REQ-54 | Collection exports include deleted entries; each deleted row has a red background and Deleted = Yes; Summary totals still exclude them and show the deleted count (DECISION-030) | User 2026-11-15 | 24 | Complete |
| REQ-55 | Super Admin, each Admin and each Sub Admin has one collection column layout (order + hide / show, at least one visible) covering both exports; new users start on the default (DECISION-030) | User 2026-11-15 | 24 | Complete |
| REQ-56 | A collection export uses the layout of: the user itself for Super Admin / Admin / Sub Admin; the MCC's creator for an MCC login; the VLCC's creator for a VLCC login, or that MCC's creator when the VLCC was created by an MCC user (DECISION-030) | User 2026-11-15 | 24 | Complete |
| REQ-57 | A layout can be changed by its user, by Super Admin (any Admin / Sub Admin) and by an Admin (its own Sub Admins), on the website and through `/api/v1/excel/column-layouts/collections` (DECISION-030) | User 2026-11-15 | 24 | Complete |

**Marketplace quality**

| ID | Requirement | Category | Phase | Status |
|----|-------------|----------|-------|--------|
| NFR-15 | **Professional UI:** one design system; responsive from 360 px to desktop; keyboard usable with visible focus and WCAG AA contrast; loading, empty and error states everywhere; user sign-off on real pages | Usability | 12–15 | In Progress (audits pass; final user sign-off open) |
| NFR-16 | **Fast:** server-rendered pages; lazy, correctly sized images with no layout shift; no list query per card (no N+1); p95 under 300 ms for home and listing pages on a catalog of 1,000 listings | Performance | 12–15 | Complete (see Phase 15 verification for load limits) |
| NFR-17 | **Secure by default:** the Control Center and admin API are outside public URL prefixes and enforce the role on the server; public forms are validated and rate limited; images go through `MediaService` validation | Security | 10, 15 | Complete (no admin API exists, DECISION-023) |
| NFR-18 | **No CDN at runtime:** all fonts, icons and scripts are self-hosted like the rest of the app | Reliability | 12 | Complete |

---

## Constraints

| ID | Constraint | Source | Impact |
|----|------------|--------|--------|
| CON-01 | `DatabaseMiddleware` wraps every request in one transaction stored in a ContextVar; jobs must run in a fresh `contextvars.Context()` and open their own transactions | Technical | runner, all importers |
| CON-02 | SQLite allows one writer at a time; long write transactions block other writes, so batches stay small | Technical | batch size |
| CON-03 | No Alembic: new tables come from `Base.metadata.create_all` when the model module is imported | Technical | `excel_jobs` model import |
| CON-04 | Argon2 hashing (`time_cost=3`, 64 MB) costs ~50–100 ms per call and is synchronous | Technical | password handling |
| CON-05 | `users.email` is NOT NULL + unique and `users.mobile` is unique, including soft-deleted users; `farmer_master (vlcc_id, farmer_code)` is unique, including soft-deleted farmers | Technical | duplicate checks |
| CON-06 | Ownership rules come from `app/modules/administration/infrastructure/hierarchy.py` and must not be re-implemented | Technical | scope checks |
| CON-07 | Code follows AGENTS.md, `.agents/rules/code_standards.md` and `.gsd/STANDARDS.md` | Project | all code |
| CON-08 | The server runs a single Uvicorn process (`run_server.py`: `workers=1`; `run_on_background.sh` uses `nohup`) — anything CPU-heavy in it slows every request | Technical | worker process (DECISION-008) |
| CON-09 | SQLite runs with `journal_mode=WAL`, `busy_timeout=5000` (`app/core/database/drivers/sqlite.py`) — a writer waiting > 5 s gets "database is locked" | Technical | batch budget (DECISION-010) |
| CON-10 | `GZipMiddleware(minimum_size=1024)` compresses every response unless it already has `Content-Encoding` (only `text/event-stream` is excluded) | Technical | downloads |
| CON-11 | An Excel sheet holds at most 1,048,576 rows and 16,384 columns | Technical | export split, import multi-sheet |

---

## Traceability Matrix

| Requirement | Plans | Tests | Status |
|-------------|-------|-------|--------|
| REQ-01 | 1.4, 1.5, 1.6 | `tests/dataexchange/test_worker.py`, `test_jobs_api.py` | — |
| REQ-02 | 1.1, 1.4 | `tests/dataexchange/test_job_repository.py` | — |
| REQ-03 | 1.6 | `tests/dataexchange/test_jobs_api.py` | — |
| REQ-04 | 1.2 | `tests/dataexchange/test_columns.py` | — |
| REQ-05 | 1.2 | `tests/dataexchange/test_xlsx.py` | — |
| REQ-06 … REQ-11 | 2.1–2.3 | planned in `/plan 2` | — |
| REQ-12 … REQ-16 | 3.1–3.3 | planned in `/plan 3` | — |
| REQ-17, REQ-18 | 4.1–4.2 | `tests/dataexchange/test_prodata_api.py` | Complete |
| REQ-19 | 5.1 | `tests/dataexchange/test_web_ui.py` | Complete |
| REQ-20, REQ-21 | 6.1–6.2 | planned in `/plan 6` | — |
| NFR-01 | 1.2, 1.3, 1.4, 5.2 | `test_xlsx.py` (tracemalloc), `scripts/loadtest_excel.py` | — |
| NFR-02 | 1.4, 5.2 | `scripts/loadtest_excel.py` | — |
| NFR-03 | 1.4, 2.2, 3.2, 5.2 | `test_worker.py` (kill mid-batch), chaos run in 5.2 | — |
| NFR-04 | 1.5 | `test_supervisor_handler.py` | — |
| NFR-05 | 1.3, 1.6 | `test_storage.py`, `test_uploads_api.py` | — |
| NFR-06 | 1.5 | `test_supervisor_handler.py` | — |
| NFR-07 | 1.4, 1.5 | `test_supervisor_handler.py` (kill worker → restart, stale heartbeat) | — |
| NFR-08 | 1.4, 5.2 | `test_worker.py` (batch shrinks over budget), load test | — |
| NFR-09 | 1.2, 1.3 | `test_file_guard.py`, `test_xlsx.py` | — |
| NFR-10 | 1.2 | `test_xlsx.py` (sheet split / multi-sheet read) | — |
| NFR-11 | 1.3, 1.4 | `test_file_guard.py` | — |
| NFR-12 | 1.6, 5.2 | `test_jobs_api.py`, load test | — |
| NFR-13 | 1.6 | `test_uploads_api.py` | — |
| NFR-14 | 1.6 | `test_jobs_api.py` | — |
| REQ-28 | 8.2 | `tests/test_marketplace_removal.py` | Complete |
| REQ-29 | 8.1 | `tests/test_recycle_bin.py`, `tests/test_marketplace_removal.py` | Complete |
| REQ-30 … REQ-45, REQ-47 | Phases 9 to 14 | `tests/marketplace/` | Complete |
| REQ-46 | 15.1 | `tests/marketplace/test_store_api.py` | Complete |
| NFR-15 | 12 to 15 | axe-core and keyboard runs in `.gsd/phases/15/VERIFICATION.md` | In Progress |
| NFR-16 | 12 to 15 | Timing runs in `.gsd/phases/15/VERIFICATION.md` | Complete |
| NFR-17 | 10, 15 | `tests/marketplace/test_rate_limit.py`, `tests/test_logging_privacy.py` | Complete |
| NFR-18 | 12 | Source check in `.gsd/phases/15/VERIFICATION.md` | Complete |

---

## Status Definitions

| Status | Meaning |
|--------|---------|
| Pending | Not yet started |
| In Progress | Being implemented |
| Complete | Implemented and verified |
| Blocked | Cannot proceed |
| Deferred | Moved to later milestone |
