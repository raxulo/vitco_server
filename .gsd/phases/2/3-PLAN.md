---
phase: 2
plan: 3
wave: 3
depends_on: [1, 2]
files_modified:
  - app/modules/dataexchange/infrastructure/vlcc_scope.py
  - app/modules/dataexchange/application/farmer_exchange.py
  - app/modules/dataexchange/domain/exceptions.py
  - app/modules/dataexchange/application/handler.py
  - app/api/v1/schemas/excel.py
  - app/api/v1/routers/excel.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - app/worker/exchange.py
  - tests/dataexchange/test_farmer_api.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "GET /api/v1/excel/options/vlccs: VLCC login → its own VLCC, locked=true; MCC / Sub Admin / Admin → VLCCs in their hierarchy (search by code / name, paginated); Super Admin → all; Farmer → 403"
    - "POST /api/v1/excel/farmers/export {vlcc_id} and /import {upload_id, vlcc_id, mode, dry_run} return 202 with the job; a VLCC login always uses its own VLCC whatever it sends; a VLCC outside the scope → 404; import without farmer permission → 403"
    - "409 for an already-running job carries details.job_id; 409 / 429 carry Retry-After"
    - "GET /api/v1/excel/farmers/template returns the cached xlsx"
    - "End to end through the API and a real worker: upload → import → poll → report download; export → poll → download equals the DB"
  key_links:
    - "Requirements: REQ-06, REQ-08, REQ-11; DECISION-004; Flutter flow in the mobile guide"
---

# Plan 2.3: VLCC Scope, Farmer Endpoints & End-to-End

<objective>
Expose farmer exchange to the web panel and the Flutter app with server-enforced VLCC selection, register the processors in the worker, and prove the whole flow end to end.
</objective>

<context>
- .gsd/DECISIONS.md (004), .gsd/REQUIREMENTS.md (REQ-06)
- app/modules/administration/infrastructure/hierarchy.py, app/modules/farmer/infrastructure/repository.py (can_manage_farmers)
- app/api/v1/routers/excel.py (Phase 1), application/handler.py, uploads.py
- app/worker/exchange.py (register_processors)
</context>

<tasks>

<task type="auto">
  <name>VLCC scope + farmer exchange use cases</name>
  <files>
    app/modules/dataexchange/infrastructure/vlcc_scope.py
    app/modules/dataexchange/application/farmer_exchange.py
    app/modules/dataexchange/domain/exceptions.py
    app/modules/dataexchange/application/handler.py
  </files>
  <action>
    1. `VlccScope(database)`: `options(owner, search, limit, offset) -> (items, total, locked, default_id)` — VLCC → own (by `VlccModel.user_id == owner.id`); others `Hierarchy.vlcc_ids(owner)` (None = all), not deleted, `vlcc_code / name ilike`, ordered by `vlcc_code`; `resolve(owner, requested) -> VlccRef` (VLCC → own, ignores requested; missing requested → ExcelTargetRequiredException 422; outside scope / deleted → ExcelTargetNotFoundException 404; FARMER → ExcelExchangeForbiddenException 403); `can_manage_farmers(owner)` delegating the farmer rule (VLCC needs `farmer_enabled`).
    2. `FarmerExchangeHandler(job_handler, scope, uploads)` (`__slots__`): `export(owner, vlcc_id)`, `import_(owner, vlcc_id, upload_id, mode, dry_run)` (scope + permission → `uploads.take` → `job_handler.submit_import` → `uploads.discard`), `options(...)`.
    3. ExcelJobHandler: `ExcelJobConflictException(details={"job_id": ...})` for the active job.
  </action>
  <verify>covered by the API tests</verify>
  <done>Scope rules match DECISION-004 and are enforced server-side.</done>
</task>

<task type="auto">
  <name>Endpoints, DI and worker registration</name>
  <files>
    app/api/v1/schemas/excel.py
    app/api/v1/routers/excel.py
    app/modules/configurator.py
    app/modules/dependencies.py
    app/worker/exchange.py
  </files>
  <action>
    Router: `GET /excel/options/vlccs` (list envelope + `locked`, `default_id`), `GET /excel/farmers/template` (FileResponse, identity encoding), `POST /excel/farmers/export` (`{vlcc_id?}` → 202 single envelope), `POST /excel/farmers/import` (`{upload_id, vlcc_id?, mode: "UPSERT"|"CREATE_ONLY", dry_run}` → 202). 409 / 429 rendered by `excel_busy_response` (Retry-After).
    DI: register `VlccScope`, `FarmerExchangeHandler`; accessor `GetHandler.farmer_exchange_handler`.
    Worker: `register_processors` adds FarmerExportProcessor and FarmerImportProcessor (deps resolved from the container), and `ensure_indexes` runs once at worker startup.
  </action>
  <verify>live: the routes answer through the running app (next task)</verify>
  <done>Four routes live; worker has both processors.</done>
</task>

<task type="auto">
  <name>API and end-to-end tests</name>
  <files>tests/dataexchange/test_farmer_api.py</files>
  <action>
    Through the real app + an in-process ExchangeWorker on the same test DB:
    options per role (VLCC locked, Admin hierarchy, Super Admin all, Farmer 403, search); export with VLCC login sending another VLCC id → still own VLCC; Admin export of an out-of-scope VLCC → 404; import without farmer permission → 403; second export while one runs → 409 with details.job_id + Retry-After; full flows: upload (chunks) → import → poll until finished → counters match → download discarded rows; export → poll → download → rows equal DB; template download.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange -q → green</verify>
  <done>All scope and flow cases pass through HTTP.</done>
</task>

</tasks>

<verification>
- [ ] Whole suite green
- [ ] `/verify` on the live server: upload → import → poll → report; export → download
</verification>

<success_criteria>
- [ ] Phase 2 must-haves in ROADMAP ticked → `/verify 2` → phase commit message
</success_criteria>
