---
phase: 2
plan: 3
completed_at: 2026-10-25
---

# Summary: VLCC Scope, Farmer Endpoints & End-to-End

## Results
- 3 tasks completed; 10 API / end-to-end tests; module suite 215 passed (+ the slow throughput test)

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | `VlccScope` (options, resolve, farmer permission), `FarmerExchangeHandler`, 409 `details.job_id`, 3 exceptions | phase commit (pending) | ✅ |
| 2 | `/excel/options/vlccs`, `/excel/farmers/template`, `/excel/farmers/export`, `/excel/farmers/import`; DI; worker registers both processors and runs `ensure_indexes` at startup | phase commit (pending) | ✅ |
| 3 | HTTP + real `ExchangeWorker` tests | phase commit (pending) | ✅ |

## Deviations Applied
- [Rule 1 - Bug] The template used the export columns, so it had no Password column. A template is filled in and imported, so it now uses the import columns. A `_LAYOUT_VERSION` in the cache signature makes already-cached files rebuild.
- [Design] `default_id` is also set when a non-VLCC user has exactly one VLCC in scope, so the app can pre-select it.
- [Design] An upload is consumed by its import: re-using the `upload_id` returns 404.
- [Design] The scope check reuses `FarmerRepository.can_manage_farmers` (the farmer API's rule) through `VlccScope`; it is not re-implemented.
- [Rule 1 - Bug, found in live verification] Re-importing an unchanged file reported every row as "updated". `updated` now counts only rows that changed, and the API exposes `unchanged` = processed − inserted − updated − discarded for imports (no schema change).
- [Rule 1 - UX, found in live verification] A mobile / email already saved by an *earlier batch of the same file* was reported as "already used by another user". The contact check now consults SeenKeys and says "Mobile repeats row N".

## Files Changed
- `app/modules/dataexchange/infrastructure/vlcc_scope.py`, `application/farmer_exchange.py` — new
- `app/modules/dataexchange/domain/exceptions.py` — target required / not found / forbidden
- `app/modules/dataexchange/application/handler.py` — 409 carries the active job id
- `app/modules/dataexchange/application/templates.py` — import columns + layout version
- `app/api/v1/schemas/excel.py`, `app/api/v1/routers/excel.py` — 4 farmer routes
- `app/modules/configurator.py`, `app/modules/dependencies.py` — DI + `GetHandler.farmer_exchange_handler`
- `app/worker/exchange.py` — farmer processors + `ensure_indexes`
- `tests/dataexchange/test_farmer_api.py` — new; `test_farmer_export.py` checks Password in the template

## Verification
- Options: VLCC → only its own, locked, default_id; Admin → its 3 VLCCs, paginated (has_more, next_page), searchable; Super Admin → includes other trees; Farmer → 403: ✅ (REQ-06)
- VLCC sending another VLCC id → job targets its own VLCC; Admin out of scope → 404; no VLCC → 422; import without farmer permission → 403: ✅ (DECISION-004)
- Second export while one is queued → 409 + `Retry-After: 30` + `details.job_id` = the first job: ✅
- E2E import (53 rows) through the real worker loop → COMPLETED 51 inserted / 2 discarded; report download lists "Mobile repeats row 52" and the mobile format error; upload consumed: ✅ (REQ-08, REQ-09, REQ-11)
- E2E export of 1,200 farmers → progress 100, codes in the file equal the DB order: ✅ (REQ-07)
- Template download → identity encoding, header with Password: ✅
