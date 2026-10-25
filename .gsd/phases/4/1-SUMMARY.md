---
phase: 4
plan: 1
completed_at: 2026-10-25
---

# Plan 4.1 Summary — Prodata Sheet Spec (9 Columns), Template & Export

## Outcomes
1. **Declared `PRODATA_SHEET` (9 columns)**:
   - Defined in `app/modules/dataexchange/domain/sheets.py` under `Section.RATE`.
   - Columns: `row_number`, `fat_min*`, `fat_max*`, `snf_min`, `snf_max`, `fat_rate_per_kg`, `snf_rate_per_kg`, `snf_cutoff`, `snf_deduction`.
   - Validation constraints: `fat_min` and `fat_max` are required floats in `[0.0, 20.0]`.
2. **Built `ProdataExchangeRepository`**:
   - Keyset pagination on `row_number ASC` for export (`export_page`, `count_export`).
   - Atomic replacement (`replace_rows`) using Core bulk delete and insert statements.
3. **Built `ProdataExportProcessor`**:
   - Handles `ExcelJobKind.PRODATA_EXPORT`.
   - Streams keyset pages into `XlsxSheetWriter(PRODATA_SHEET)` in worker threads with cancellation and progress checkpoints.
4. **Built Template Generator**:
   - `prodata_template_path(storage_root)` generates and caches `template_prodata.xlsx` containing the "Prodata Rate Chart" and "Instructions" sheets.
5. **Verified**:
   - 3/3 automated tests in `tests/dataexchange/test_prodata_export.py` passing:
     - `test_prodata_template_cached`
     - `test_export_empty_chart`
     - `test_export_multiple_rows_in_order`
