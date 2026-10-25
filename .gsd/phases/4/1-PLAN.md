---
phase: 4
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/dataexchange/domain/sheets.py
  - app/modules/dataexchange/infrastructure/prodata_repository.py
  - app/modules/dataexchange/application/prodata_export.py
  - app/modules/dataexchange/application/templates.py
  - tests/dataexchange/test_prodata_export.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "PRODATA_SHEET declares 9 columns in Section.RATE: row_number, fat_min, fat_max, snf_min, snf_max, fat_rate_per_kg, snf_rate_per_kg, snf_cutoff, snf_deduction; fat_min and fat_max are required"
    - "Export of one rate chart writes every row of that chart ordered by row_number ASC"
    - "Export uses keyset/chunked streaming and writes rows in worker threads"
    - "The Prodata template is built once and served from a cached file"
  artifacts:
    - "ProdataExportProcessor (kind PRODATA_EXPORT) usable by the exchange worker"
  key_links:
    - "Requirements: REQ-17; DECISIONS: 005, 007, 011, 012"
---

# Plan 4.1: Prodata Sheet Spec (9 Columns), Template & Export

<objective>
Declare the 9-column Prodata sheet spec, build the Prodata repository for export queries, implement the export processor, and add the cached Prodata template builder.

Output: `PRODATA_SHEET`, `ProdataExchangeRepository` (export queries; replacement in 4.2), `ProdataExportProcessor`, cached Prodata template.
</objective>

<context>
- .gsd/phases/4/RESEARCH.md
- .gsd/REQUIREMENTS.md (REQ-17)
- app/modules/dataexchange/domain/columns.py, domain/sheets.py
- app/modules/ratechart/infrastructure/models.py (RateChartModel, ProdataRateRowModel)
</context>

<tasks>

<task type="auto">
  <name>Prodata sheet specification (9 columns)</name>
  <files>
    app/modules/dataexchange/domain/sheets.py
  </files>
  <action>
    Define `PRODATA_SHEET` in `app/modules/dataexchange/domain/sheets.py` with 9 columns in order:
    1. `row_number` (INT, min_value=1, example="1", help="Row sequence number.")
    2. `fat_min` (FLOAT, min_value=0.0, max_value=20.0, required=True, example="3.0", help="Minimum FAT percentage.")
    3. `fat_max` (FLOAT, min_value=0.0, max_value=20.0, required=True, example="4.5", help="Maximum FAT percentage.")
    4. `snf_min` (FLOAT, min_value=0.0, max_value=20.0, example="7.0", help="Minimum SNF percentage (optional).")
    5. `snf_max` (FLOAT, min_value=0.0, max_value=20.0, example="9.0", help="Maximum SNF percentage (optional).")
    6. `fat_rate_per_kg` (FLOAT, min_value=0.0, example="350.0", help="Rate per kg FAT (in rupees).")
    7. `snf_rate_per_kg` (FLOAT, min_value=0.0, example="250.0", help="Rate per kg SNF (in rupees).")
    8. `snf_cutoff` (FLOAT, min_value=0.0, max_value=20.0, example="8.0", help="SNF threshold below which deduction applies.")
    9. `snf_deduction` (FLOAT, min_value=0.0, example="2.0", help="Deduction rate per unit below cutoff.")
    All columns under `Section.RATE`.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.domain.sheets import PRODATA_SHEET as s; print(len(s.columns), [c.key for c in s.columns if c.required])" -> `9 ['fat_min', 'fat_max']`</verify>
  <done>PRODATA_SHEET declared with 9 columns, constraints, examples, and help text.</done>
</task>

<task type="auto">
  <name>Prodata exchange repository and export processor</name>
  <files>
    app/modules/dataexchange/infrastructure/prodata_repository.py
    app/modules/dataexchange/application/prodata_export.py
  </files>
  <action>
    1. Create `app/modules/dataexchange/infrastructure/prodata_repository.py`:
       - `ProdataExchangeRepository` with:
         - `count_rows(chart_id: UUID) -> int`: Counts rows in `prodata_rate_rows` for this chart.
         - `stream_rows(chart_id: UUID, batch_size: int, after_row_number: int = 0) -> list[dict[str, Any]]`:
           Selects columns matching `PRODATA_SHEET` keys from `prodata_rate_rows` ordered by `row_number ASC`, where `row_number > after_row_number`, limit `batch_size`.
    2. Create `app/modules/dataexchange/application/prodata_export.py`:
       - `ProdataExportProcessor(ExchangeProcessor)`:
         - `kind = ExcelJobKind.PRODATA_EXPORT`.
         - Validates `target_id` is present on the job context (raises `JobFatalError` if missing).
         - Counts total rows via repository; sets `ctx.total = count`.
         - Streams rows in batches using `XlsxSheetWriter(PRODATA_SHEET)` in threadpool worker executor (`run_in_executor`).
         - Periodic heartbeat & cancellation checks via `ctx.check_cancelled()`.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.application.prodata_export import ProdataExportProcessor; print(ProdataExportProcessor.kind)" -> `ExcelJobKind.PRODATA_EXPORT`</verify>
  <done>ProdataExchangeRepository and ProdataExportProcessor implemented.</done>
</task>

<task type="auto">
  <name>Prodata template builder and export unit tests</name>
  <files>
    app/modules/dataexchange/application/templates.py
    tests/dataexchange/test_prodata_export.py
  </files>
  <action>
    1. Update `app/modules/dataexchange/application/templates.py`:
       - Add `prodata_template_path(storage: ExchangeStorage) -> Path` that calls `ensure_template_cached(storage, PRODATA_SHEET, "template_prodata.xlsx")`.
    2. Create `tests/dataexchange/test_prodata_export.py`:
       - Test template generation & caching.
       - Test export with 0 rows (empty chart).
       - Test export with multiple rows, verifying cell values and row ordering.
       - Test heartbeat and cancellation during export.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_prodata_export.py -v</verify>
  <done>Prodata template builder added and export tests passing.</done>
</task>

</tasks>
