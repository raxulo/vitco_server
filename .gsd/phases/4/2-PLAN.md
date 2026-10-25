---
phase: 4
plan: 2
wave: 2
depends_on:
  - 1
files_modified:
  - app/modules/dataexchange/infrastructure/prodata_repository.py
  - app/modules/dataexchange/application/prodata_import.py
  - app/worker/exchange.py
  - app/modules/dataexchange/infrastructure/ratechart_scope.py
  - app/modules/dataexchange/application/prodata_exchange.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - app/api/v1/schemas/excel.py
  - app/api/v1/routers/excel.py
  - tests/dataexchange/test_prodata_import.py
  - tests/dataexchange/test_prodata_api.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Prodata import validates every row before writing anything; if any row has fat_min > fat_max, snf_min > snf_max, negative rates, or overlapping ranges, the entire import is rejected and saves nothing (REQ-18, DECISION-005)"
    - "On successful validation, all existing rows of the chart are replaced in one atomic database transaction"
    - "A rejected import creates a discarded-rows file with the invalid rows plus Row No and Reason"
    - "ExchangeWorker registers both ProdataExportProcessor and ProdataImportProcessor"
    - "GET /api/v1/excel/prodata/options returns accessible Prodata charts with can_modify status"
    - "POST /api/v1/excel/prodata/export checks read permission (Hierarchy.shared_visible) and submits PRODATA_EXPORT job"
    - "POST /api/v1/excel/prodata/import checks write permission (Hierarchy.shared_modifiable) and submits PRODATA_IMPORT job"
  artifacts:
    - "ProdataImportProcessor registered in ExchangeWorker"
    - "RateChartScope, ProdataExchangeHandler wired in IoC container"
    - "/api/v1/excel/prodata/* REST endpoints"
  key_links:
    - "Requirements: REQ-17, REQ-18; DECISIONS: 005, 007, 008, 011"
---

# Plan 4.2: Prodata Import (Atomic Replace & Overlap Validation), Scope & APIs

<objective>
Implement all-or-nothing Prodata import validation and atomic replacement, register worker processors, implement `RateChartScope` and `ProdataExchangeHandler`, add REST API endpoints, and verify end-to-end.

Output: `ProdataImportProcessor`, `RateChartScope`, `ProdataExchangeHandler`, `/api/v1/excel/prodata/*` endpoints, and automated tests.
</objective>

<context>
- .gsd/phases/4/RESEARCH.md
- .gsd/phases/4/1-PLAN.md
- .gsd/REQUIREMENTS.md (REQ-17, REQ-18)
- app/modules/ratechart/infrastructure/models.py
- app/modules/dataexchange/infrastructure/owner_scope.py, vlcc_scope.py
</context>

<tasks>

<task type="auto">
  <name>Prodata repository replace_rows and import processor</name>
  <files>
    app/modules/dataexchange/infrastructure/prodata_repository.py
    app/modules/dataexchange/application/prodata_import.py
    app/worker/exchange.py
  </files>
  <action>
    1. In `app/modules/dataexchange/infrastructure/prodata_repository.py`:
       - Add `replace_rows(chart_id: UUID, rows: list[dict[str, Any]]) -> None`:
         In a transaction:
         - `DELETE FROM prodata_rate_rows WHERE rate_chart_id = :chart_id`
         - `INSERT INTO prodata_rate_rows (id, rate_chart_id, row_number, fat_min, fat_max, snf_min, snf_max, fat_rate_per_kg, snf_rate_per_kg, snf_cutoff, snf_deduction)` using Core bulk execute.
    2. Create `app/modules/dataexchange/application/prodata_import.py`:
       - `ProdataImportProcessor(ExchangeProcessor)`:
         - `kind = ExcelJobKind.PRODATA_IMPORT`.
         - Stream-reads all rows from source `.xlsx` via `XlsxSheetReader(PRODATA_SHEET)`.
         - Validates each row:
           - Required `fat_min` and `fat_max`.
           - `fat_min <= fat_max` (if not: "FAT Min ({fat_min}) exceeds FAT Max ({fat_max})").
           - `snf_min <= snf_max` if both present (if not: "SNF Min ({snf_min}) exceeds SNF Max ({snf_max})").
           - Rates not negative (`fat_rate_per_kg >= 0`, `snf_rate_per_kg >= 0`, `snf_cutoff >= 0`, `snf_deduction >= 0`).
         - Validates interval overlap across rows:
           - FAT interval overlap check: `max(r1.fat_min, r2.fat_min) < min(r1.fat_max, r2.fat_max)` or identical boundaries.
           - If both specify SNF: requires SNF overlap too. If either is None, FAT overlap alone is a conflict.
           - If overlap found: records error "Range overlaps with row {r1.row_no} (FAT {r1.fat_min}-{r1.fat_max})".
         - All-or-nothing replace:
           - If ANY error is found across any row:
             - Do NOT call `replace_rows`.
             - Generate discarded-rows report containing all failed rows + reasons (and original cells) using `XlsxSheetWriter(PRODATA_SHEET, extra_columns=[ExtraColumn("Row No", 10), ExtraColumn("Reason", 60)])`.
             - Set `ctx.inserted = 0, ctx.discarded = len(errors)`.
           - If ALL rows are valid:
             - Call `repository.replace_rows(target_id, valid_rows)`.
             - Set `ctx.inserted = len(valid_rows), ctx.discarded = 0`.
    3. Register `ProdataExportProcessor` and `ProdataImportProcessor` in `app/worker/exchange.py` inside `register_processors()`.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.application.prodata_import import ProdataImportProcessor; print(ProdataImportProcessor.kind)" -> `ExcelJobKind.PRODATA_IMPORT`</verify>
  <done>ProdataImportProcessor and atomic replace implemented and registered in worker.</done>
</task>

<task type="auto">
  <name>RateChartScope, ProdataExchangeHandler, and DI wiring</name>
  <files>
    app/modules/dataexchange/infrastructure/ratechart_scope.py
    app/modules/dataexchange/application/prodata_exchange.py
    app/modules/configurator.py
    app/modules/dependencies.py
  </files>
  <action>
    1. Create `app/modules/dataexchange/infrastructure/ratechart_scope.py`:
       - `RateChartOption(id, name, milk_type, calculation_type, can_modify)` dataclass.
       - `RateChartOptions(items, total)` dataclass.
       - `RateChartScope`:
         - `options(owner: CurrentUser, search: str | None, limit: int, offset: int) -> RateChartOptions`:
           Queries `rate_charts` where `chart_type == RateChartType.PRODATA` and `Hierarchy.shared_visible(owner, RateChartModel.created_by)`. Annotates `can_modify` using `Hierarchy.shared_modifiable`.
         - `resolve_for_export(owner: CurrentUser, chart_id: UUID) -> RateChartModel`:
           Verifies chart exists, is PRODATA, and visible (`Hierarchy.shared_visible`). Raises `ExcelTargetNotFoundException` or `ExcelExchangeForbiddenException`.
         - `resolve_for_import(owner: CurrentUser, chart_id: UUID) -> RateChartModel`:
           Verifies chart exists, is PRODATA, and modifiable (`Hierarchy.shared_modifiable`). Raises `ExcelTargetNotFoundException` or `ExcelExchangeForbiddenException`.
    2. Create `app/modules/dataexchange/application/prodata_exchange.py`:
       - `ProdataExchangeHandler`:
         - `chart_options(...)`
         - `export(owner, chart_id)` -> submits `PRODATA_EXPORT` job.
         - `import_(owner, source, chart_id, mode, dry_run)` -> submits `PRODATA_IMPORT` job.
    3. Wire `RateChartScope` and `ProdataExchangeHandler` into `app/modules/configurator.py` and `app/modules/dependencies.py`.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.infrastructure.ratechart_scope import RateChartScope; print(RateChartScope)"</verify>
  <done>RateChartScope and ProdataExchangeHandler registered in IoC container.</done>
</task>

<task type="auto">
  <name>REST API endpoints and tests</name>
  <files>
    app/api/v1/schemas/excel.py
    app/api/v1/routers/excel.py
    tests/dataexchange/test_prodata_import.py
    tests/dataexchange/test_prodata_api.py
  </files>
  <action>
    1. Update `app/api/v1/schemas/excel.py`:
       - Add `RateChartOptionResponse`, `RateChartOptionsResponse`, `ProdataExportRequest`, `ProdataImportRequest`.
    2. Update `app/api/v1/routers/excel.py`:
       - `GET /api/v1/excel/prodata/options`: Returns list of accessible Prodata rate charts.
       - `GET /api/v1/excel/prodata/template`: Downloads cached template.
       - `POST /api/v1/excel/prodata/export`: Submits `PRODATA_EXPORT` job.
       - `POST /api/v1/excel/prodata/import`: Accepts file or upload_id and submits `PRODATA_IMPORT` job.
    3. Create `tests/dataexchange/test_prodata_import.py`:
       - Test valid import replaces all rows atomically.
       - Test invalid row (`fat_min > fat_max`) rejects whole file and saves 0 rows.
       - Test overlapping ranges reject whole file and saves 0 rows.
       - Test discarded-rows report generation with Row No and Reason.
    4. Create `tests/dataexchange/test_prodata_api.py`:
       - Test options API with visible / modifiable charts.
       - Test template download endpoint.
       - Test export endpoint permissions (visible allowed, unshared forbidden).
       - Test import endpoint permissions (modifiable allowed, read-only forbidden).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_prodata_import.py tests/dataexchange/test_prodata_api.py -v</verify>
  <done>Prodata API endpoints implemented and automated tests passing.</done>
</task>

</tasks>
