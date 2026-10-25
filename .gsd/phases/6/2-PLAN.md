---
phase: 6
plan: 2
wave: 2
depends_on:
  - 1-PLAN.md
---

# Plan 6.2: Formula Import Engine, Endpoints, UI Modal & Tests

## Objective
Implement the `FormulaImportProcessor` with strict validation rules, extend `RateChartScope` to resolve and create Formula rate charts, expose REST API endpoints for formula export/import/template, integrate the web modal, and verify end-to-end with automated test coverage.

## Context
- `.gsd/SPEC.md`
- `.gsd/REQUIREMENTS.md` (REQ-21)
- `.gsd/phases/6/1-PLAN.md`
- `app/modules/dataexchange/infrastructure/ratechart_scope.py`
- `app/modules/dataexchange/application/prodata_exchange.py` (pattern)
- `app/api/v1/routers/excel.py`
- `app/web/templates/components/excel_modal.html`
- `app/web/static/js/excel_exchange.js`

## Tasks

<task type="auto">
  <name>Task 1: Formula Import Processor with Validation</name>
  <files>
    app/modules/dataexchange/application/formula_import.py
    app/modules/configurator.py
  </files>
  <action>
    1. Create `app/modules/dataexchange/application/formula_import.py`:
       - `FormulaImportProcessor(ExchangeProcessor)`:
         - Handles `ExcelJobKind.FORMULA_IMPORT`.
         - Reads `Formula Config` sheet (or first sheet).
         - Invariant checks:
           - Animal type must be `COW` or `BUFFALO`.
           - `standard_fat > 0`, `standard_snf > 0`, `standard_rate > 0`.
           - `fat_percentage + snf_percentage` must sum to `100.0` (tolerance 0.05).
         - Rejection report: if any invariant fails, writes discarded report with row numbers and exact reasons; discards entire file (all-or-nothing).
         - Dry run: if `ctx.job.dry_run`, validates completely without DB writes.
         - Atomic save: on valid file, updates or creates `RateFormulaConfigModel` in a single transaction.
    2. In `app/modules/configurator.py`:
       - Register `FormulaImportProcessor` in `ExchangeWorker`.
  </action>
  <verify>
    .venv\Scripts\python.exe -c "from app.modules.dataexchange.application.formula_import import FormulaImportProcessor; print('Formula import processor imports cleanly')"
  </verify>
  <done>
    `FormulaImportProcessor` implements atomic validation, error reporting, dry-run safety, and is registered in the worker.
  </done>
</task>

<task type="auto">
  <name>Task 2: RateChart Scope Support & Application Handler</name>
  <files>
    app/modules/dataexchange/infrastructure/ratechart_scope.py
    app/modules/dataexchange/application/formula_exchange.py
    app/modules/configurator.py
    app/modules/dependencies.py
  </files>
  <action>
    1. In `app/modules/dataexchange/infrastructure/ratechart_scope.py`:
       - Add `formula_options(...) -> RateChartOptions` returning visible `RateChartType.FORMULA` charts.
       - Update `resolve_for_export` and `resolve_for_import` to accept `chart_type: RateChartType`.
       - Update `create_chart_for_import` to support `chart_type: RateChartType = RateChartType.PRODATA` (allowing `RateChartType.FORMULA`).
    2. Create `app/modules/dataexchange/application/formula_exchange.py`:
       - `FormulaExchangeHandler`:
         - `template() -> Path`
         - `chart_options(owner, ...) -> RateChartOptions`
         - `export(owner, chart_id) -> ExcelJobDto`
         - `import_(owner, upload_id, chart_id, chart_name, milk_type, effective_from, dry_run) -> ExcelJobDto`
    3. In `app/modules/configurator.py` and `app/modules/dependencies.py`:
       - Register `FormulaExchangeHandler` in IoC container and add `GetHandler.formula_exchange_handler`.
  </action>
  <verify>
    .venv\Scripts\python.exe -c "from app.modules.dataexchange.application.formula_exchange import FormulaExchangeHandler; print('FormulaExchangeHandler ready')"
  </verify>
  <done>
    `RateChartScope` supports Formula charts, handler registered in container and dependency accessors.
  </done>
</task>

<task type="auto">
  <name>Task 3: REST API Endpoints, UI Modal Integration & Automated Tests</name>
  <files>
    app/api/v1/schemas/excel.py
    app/api/v1/routers/excel.py
    app/web/templates/components/excel_modal.html
    app/web/static/js/excel_exchange.js
    app/web/templates/pages/ratechart/list.html
    tests/dataexchange/test_formula_api.py
  </files>
  <action>
    1. In `app/api/v1/schemas/excel.py`:
       - Add `FormulaExportRequest(chart_id: UUID)`.
       - Add `FormulaImportRequest(upload_id: UUID, chart_id: UUID | None, chart_name: str | None, milk_type: int | str, effective_from: date | None, dry_run: bool)`.
    2. In `app/api/v1/routers/excel.py`:
       - `GET /excel/formula/template`
       - `GET /excel/formula/options`
       - `POST /excel/formula/export`
       - `POST /excel/formula/import`
    3. In `app/web/templates/components/excel_modal.html` and `excel_exchange.js`:
       - Add `formula` to `KIND_CONFIG`:
         - Title: "Formula Rate-Chart Excel Exchange"
         - Subtitle: "Export formula parameters & preview grid, or import formula configuration"
       - Connect "Formula Export" and "Formula Import" buttons on `ratechart/list.html`.
    4. Create `tests/dataexchange/test_formula_api.py`:
       - Test options endpoint for formula charts.
       - Test template download.
       - Test export (including preview matrix generation).
       - Test import updating existing chart.
       - Test import creating brand new Formula chart from Excel.
       - Test validation failure (e.g., FAT% + SNF% != 100%) produces rejected report.
       - Test dry run does not modify DB.
  </action>
  <verify>
    .venv\Scripts\python.exe -m pytest tests/dataexchange/test_formula_api.py -v
  </verify>
  <done>
    End-to-end API, UI modal, and automated tests passing with 100% green status.
  </done>
</task>

## Success Criteria
- [ ] `POST /excel/formula/export` generates valid workbook with configuration and preview grid.
- [ ] `POST /excel/formula/import` updates existing chart or creates new Formula rate chart.
- [ ] Invariant validations (100% ratio sum, positive numbers) verified.
- [ ] Web modal opens seamlessly for Formula rate charts.
- [ ] All tests in `tests/dataexchange/test_formula_api.py` pass.
