---
phase: 3
plan: 3
wave: 3
depends_on:
  - 1
  - 2
files_modified:
  - app/modules/dataexchange/infrastructure/owner_scope.py
  - app/modules/dataexchange/application/handler.py
  - app/api/v1/routers/excel.py
  - app/api/v1/schemas/excel.py
  - tests/dataexchange/test_vlcc_endpoints.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Owner options endpoint returns eligible owners, locked flag, and default_id based on CurrentUser role"
    - "Super Admin can pick any Admin or Sub Admin, or Self"
    - "Admin can pick any of its Sub Admins, or Self"
    - "Sub Admin and MCC are locked to their own ID"
    - "VLCC / Farmer gets 403 Forbidden"
    - "Server verifies submitted owner_id against role hierarchy regardless of client input"
    - "POST /api/v1/excel/vlccs/export and /import return 202 with job_id"
    - "GET /api/v1/excel/vlccs/template downloads cached template"
  artifacts:
    - "OwnerScopeService"
    - "VLCC exchange endpoints under /api/v1/excel/vlccs/*"
  key_links:
    - "Requirements: REQ-12, REQ-01, REQ-03, REQ-04; DECISION-004"
---

# Plan 3.3: Owner Scope, Options API & VLCC Endpoints

<objective>
Implement owner hierarchy scoping, options endpoint, and authenticated REST endpoints for VLCC export, import, template, and options, with full verification.

Output: `OwnerScopeService`, `/api/v1/excel/vlccs/*` endpoints, integration tests.
</objective>

<context>
- .gsd/phases/3/RESEARCH.md, .gsd/phases/3/1-PLAN.md, .gsd/phases/3/2-PLAN.md
- app/middleware/authentication.py (CurrentUser)
- app/modules/administration/infrastructure/hierarchy.py
- app/api/v1/routers/excel.py, app/api/v1/schemas/excel.py
</context>

<tasks>

<task type="auto">
  <name>Owner scope service & options schema</name>
  <files>
    app/modules/dataexchange/infrastructure/owner_scope.py
    app/api/v1/schemas/excel.py
  </files>
  <action>
    1. Create `OwnerScopeService(database)`:
       - `resolve_owner(user: CurrentUser, requested_owner_id: UUID | None) -> UUID`:
         Validates or forces owner ID based on user role (REQ-12, DECISION-004):
         - Super Admin: `requested_owner_id` must be an Admin, Sub Admin, or Super Admin self.
         - Admin: `requested_owner_id` must be Admin self or a Sub Admin created by Admin. Default is Admin self.
         - Sub Admin: Always `user.id` (ignores client input).
         - MCC: Always `user.id` (ignores client input).
         - Other roles: raises `ForbiddenError`.
       - `list_options(user: CurrentUser) -> OwnerOptionsResult`:
         Returns `{items: [{id, name, role}], locked: bool, default_id: UUID | None}`.
    2. Add schemas in `excel.py`:
       - `OwnerOptionItem`, `OwnerOptionsResponse`, `VlccExportRequest`, `VlccImportRequest`.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.infrastructure.owner_scope import OwnerScopeService; print(OwnerScopeService)"</verify>
  <done>Owner scope resolves and validates owner according to hierarchy rules.</done>
</task>

<task type="auto">
  <name>VLCC exchange REST endpoints</name>
  <files>
    app/api/v1/routers/excel.py
    app/modules/dataexchange/application/handler.py
  </files>
  <action>
    Add routes to `app/api/v1/routers/excel.py`:
    1. `GET /api/v1/excel/vlccs/options` -> Returns owner options for current user.
    2. `GET /api/v1/excel/vlccs/template` -> Downloads cached VLCC template.
    3. `POST /api/v1/excel/vlccs/export` -> Submits `VLCC_EXPORT` job with validated owner `target_id`, returns 202 `{job_id}`.
    4. `POST /api/v1/excel/vlccs/import` -> Submits `VLCC_IMPORT` job with validated owner `target_id` and uploaded file, returns 202 `{job_id}`.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.api.v1.routers.excel import router; print(router)"</verify>
  <done>Endpoints exposed and registered under /api/v1/excel/vlccs.</done>
</task>

<task type="auto">
  <name>Integration and security tests for VLCC exchange</name>
  <files>
    tests/dataexchange/test_vlcc_endpoints.py
  </files>
  <action>
    Add automated tests verifying:
    - Super Admin options contains Admins, Sub Admins, and Self; can export/import for any.
    - Admin options contains Sub Admins and Self; cannot export/import for another Admin.
    - Sub Admin and MCC options return `locked: True` and default to self.
    - VLCC and Farmer get 403 Forbidden.
    - Export endpoint creates QUEUED job and returns 202.
    - Import endpoint creates QUEUED job and returns 202.
    - End-to-end import run processes file and reports correct counts.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_vlcc_endpoints.py -q → green</verify>
  <done>All endpoint and security tests pass.</done>
</task>

</tasks>

<verification>
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` passes all tests
</verification>
