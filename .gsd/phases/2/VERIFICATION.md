---
phase: 2
verified_at: 2026-10-25
verdict: PASS
---

# Phase 2 Verification Report — Farmer Excel Exchange

## Summary
Every Phase 2 must-have was verified at runtime on an isolated uvicorn server (temp SQLite DB, temp storage). The real exchange worker ran as a subprocess. A VLCC user drove the whole flow over HTTP, logged in like the Flutter app (`POST /api/v1/auth/login`). The real dev DB was untouched (0 test users, no `excel_jobs` table).

## Must-Haves

### ✅ VLCC selection by role, enforced on the server (REQ-06)
- VLCC login: `GET /excel/options/vlccs` → `locked=True`, `default_id` = its VLCC, items `['V001']`.
- Super Admin (web login): sees `V001`, `locked=False`.
- `POST /excel/farmers/export {"vlcc_id": <random uuid>}` by the VLCC → 202 with `target_id` = its own VLCC.

### ✅ Template (REQ-04/05)
`GET /excel/farmers/template` → 200, `Content-Encoding: identity`, header `Farmer Code *, Milk Type, Rate Chart Rank, SMS Enabled, Active, Name *, …` (Password included).

### ✅ Import with upsert and discard rules (REQ-08 … REQ-11)
- Workbook saved by openpyxl with mobiles typed as numbers: 20,003 rows, 557 KB.
- Result: chunked upload → `POST /excel/farmers/import` 202 → poll → COMPLETED, **inserted 20,000, discarded 3, 9.2 s (2,175 rows/s)**.
- Report download `farmer_import_…_discarded_rows.xlsx`:
  - `DUPMOB, 20002, Mobile repeats row 7`
  - `BADMOB, 20003, Mobile: must be exactly 10 digits`
  - `None, 20004, Farmer Code is required`
- Same upload id again → 404 `EXCEL_UPLOAD_NOT_FOUND` (consumed).
- Re-import of the same file → inserted 0, updated 0, **unchanged 20,000**, discarded 3, 6.1 s, no writes.

### ✅ Export (REQ-07)
- 20,000 rows in 4.1 s; progress seen 0 → 5 → 40 → 75 → 100.
- File 1.17 MB, `Content-Encoding: identity`; codes equal the DB order.
- Mobile `'8000000000'` and account `'0000000000000000'` exported as text.

### ✅ Performance levers in place
- `ix_users_email_lower` built by the worker at startup (4 ms on an empty DB); the query plan is `SEARCH users USING INDEX ix_users_email_lower`.
- API while importing: the job-status endpoint stayed at ~25 ms over its 10 ms idle baseline.

## Findings
- `/healthz` takes ~300 ms even on an idle server. This was already the case before Phase 2 (outside this feature); worth a look for monitoring and load balancers.
- Throughput reference: 2,175 rows/s on a fresh DB in the live run, 1,032 rows/s in the test suite's shared DB with ~120k other rows. Both are SQLite commit-bound at the 250 ms fairness budget (see 2-SUMMARY).
- Two UX gaps were found on the live run and fixed before this verdict:
  - re-imports reported unchanged rows as "updated";
  - a mobile repeated from an earlier batch said "used by another user" instead of "repeats row N".

## Verdict
PASS
