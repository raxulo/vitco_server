# Phase 5 Research: Web Panel & Hardening

## Overview & Scope
Phase 5 is the final phase of Milestone v1.1.0 (Excel Data Exchange). It brings the background exchange engine, streaming xlsx reader/writer, and domain adapters (Farmer, VLCC, Prodata) to the web panel and subjects the system to load, chaos, and reliability hardening.

### Requirements & Objectives
- **REQ-19:** Farmer, VLCC, and Rate Chart list pages have Export / Import / Template actions, a selection dropdown (VLCC / Owner / Chart) that is locked when only 1 option is available, live progress polling (`poll_after_ms`), and a summary card upon completion with report download.
- **NFR-01:** Constant memory: worker peak RSS does not grow with file size (< 50 MB growth between 100k and 1M rows).
- **NFR-02:** No lag: other API endpoints keep p95 < 300 ms, event-loop lag < 100 ms during large jobs.
- **NFR-03:** No data loss: adaptive batch writes with savepoints; killing the worker loses at most uncommitted batch, never leaves orphaned records.
- **NFR-04 … NFR-07:** Backpressure (2 running, 20 queued, 429 Retry-After), safe uploads, supervisor auto-restart within 30s, stale job marking.
- **NFR-08:** Short DB locks (≤ 250 ms target per transaction); zero "database is locked" errors.
- **NFR-09 … NFR-11:** Hostile file rejection (zip bomb, XML bomb, empty row padding), 507 disk guard.
- **NFR-12 … NFR-14:** Cheap polling (PK read), connection efficiency, streaming uncompressed downloads (`Content-Encoding: identity`).

---

## Architectural Findings

### 1. Web Panel UI Architecture
- The web interface uses Jinja2 templates extending `layouts/dashboard.html` which extends `layouts/base.html`.
- Global libraries loaded: `htmx.js`, FontAwesome, Vanilla JS (`app.main.js`), and modern CSS variables.
- Modals are supported via `<div id="modal"></div>` in `layouts/dashboard.html`.
- Authentication in the web UI is cookie-based (`access_token` in `request.cookies`).
- **Key Insight:** `AuthenticationMiddleware` currently decodes cookie tokens only if `WebHelper.is_web(request)` returns True. For direct browser navigation (`<a href="/api/v1/excel/..." download>`) or `fetch()`, requests to `/api/v1/excel/` must also check `request.cookies.get('access_token')` so that authenticated web users can download templates, export files, and discarded reports directly without needing a custom Authorization header wrapper.

### 2. UI Component Design (REQ-19)
- **Reusable Excel Exchange Modal (`app/web/templates/components/excel_modal.html`):**
  - Works across all 3 modules (`farmers`, `vlccs`, `prodata`).
  - Target selection dropdown populated from `/api/v1/excel/{kind}/options`. If `total == 1` or `can_modify == false`, dropdown is pre-selected and disabled/locked.
  - File picker with drag-and-drop support (validates `.xlsx` extension).
  - Mode selector (`UPSERT`, `ADD_ONLY`, `UPDATE_ONLY` for Farmer/VLCC; hidden for Prodata which is atomic replace).
  - Dry run checkbox.
  - Chunked upload handling in browser JavaScript (`app/web/static/js/excel_exchange.js`) utilizing `/api/v1/excel/uploads` (for files > 5MB) or `/api/v1/excel/uploads/single` (for files ≤ 5MB).
  - Polling progress bar with percentage, status badges (`PENDING`, `RUNNING`, `COMPLETED`, `FAILED`), and dynamic interval using `poll_after_ms`.
  - Summary card showing `total_rows`, `inserted`, `updated`, `discarded`.
  - Conditional "Download Error Report" button if `discarded > 0` linking to `/api/v1/excel/jobs/{job_id}/file`.

### 3. Load & Hardening Strategy (NFR-01, NFR-02, NFR-08)
- Create `scripts/loadtest_excel.py`:
  - Generates 100k farmer rows.
  - Runs import while a simulated background traffic generator hits high-frequency endpoints (`/api/v1/excel/jobs/{id}`, `/health`).
  - Measures:
    - Peak RSS before, during, and after (verifying flat memory < 50MB growth).
    - Latency distribution (p50, p95, p99) of concurrent HTTP requests.
    - Verifies 0 occurrences of SQLite `database is locked`.
    - Measures overall rows/sec throughput.

### 4. Chaos & Robustness Testing (NFR-03, NFR-07, NFR-09, NFR-11)
- Automated tests in `tests/dataexchange/test_chaos.py`:
  - Kill worker process mid-batch: verify supervisor cleans up or reports failure, and database contains only committed batches with zero orphaned users or farmers.
  - Upload abort: cancel upload halfway, verify storage discard and no file leaks.
  - Hostile files: verify zip bomb rejection, XML bomb rejection, non-xlsx files.
  - Disk guard: verify 507 Insufficient Storage when free disk is below threshold.

### 5. Mobile & API Documentation
- Create `docs/EXCEL_EXCHANGE_API.md`:
  - Step-by-step integration guide for Android/iOS mobile apps and external consumers.
  - Covers single & chunked upload, job submission, status polling, error handling (409 conflict, 429 backpressure, Retry-After), and file download.
