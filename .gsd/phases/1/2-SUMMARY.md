---
phase: 1
plan: 2
completed_at: 2026-10-25
---

# Summary: Column Specs & Streaming XLSX

## Results
- 2 tasks completed
- All verifications passed: 72 column tests + 15 xlsx tests (102 in the module suite with Plan 1.1)

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | Declarative column specs, header matching, cell parse / format | phase commit (pending) | ✅ |
| 2 | Streaming xlsx writer (xlsxwriter) and own expat reader | phase commit (pending) | ✅ |

## Deviations Applied
- **[Rule 4 - Architectural, approved by user] DECISION-012:** measurement showed openpyxl reads at 2,864 rows/s and loads all shared strings into memory, so the reader is now our own stdlib `zipfile` + `expat` streaming parser (15–18k rows/s, 8.3 MB peak). Shared strings spill to a scratch SQLite file above 100,000 entries. The writer is `xlsxwriter==3.3.0` `constant_memory` (7,604 rows/s vs 4,526). openpyxl moved to `requirements-dev.txt` (tests only); `defusedxml` dropped and uninstalled.
- [Rule 1 - Bug] `CODE` columns accepted `101.5` after a TEXT fix; codes now reject fractional numbers. Mobile `98765.5` now reports "must be exactly 10 digits" instead of a generic decimals message.
- [Rule 2 - Missing critical] TIME cells stored by Excel as a day fraction (`0.25`) are converted (`06:00`); cells longer than Excel's 32,767 characters are rejected (memory guard); damaged XML / non-zip files raise `InvalidExcelFileException` instead of library errors; long dropdown lists (> 255 chars) go to a hidden `Lists` sheet.
- [Test] openpyxl 3.1.5 writes inline strings only, so Excel-style shared-string workbooks are hand-built in the tests.
- Plan 1.3 task 2 updated: the openpyxl `DEFUSEDXML` assertion is replaced by an early `<!DOCTYPE` / `<!ENTITY` scan; the reader refuses them too.

## Files Changed
- `app/modules/dataexchange/domain/columns.py` — new: ColumnKind, Section, ColumnSpec, SheetSpec, HeaderMap, parse_cell, format_cell
- `app/modules/dataexchange/infrastructure/xlsx.py` — new: XlsxSheetWriter, XlsxSheetReader, ExtraColumn, RawRow
- `requirements.txt` — xlsxwriter 3.3.0 (replaces openpyxl + defusedxml)
- `requirements-dev.txt` — openpyxl 3.1.5
- `tests/dataexchange/test_columns.py`, `tests/dataexchange/test_xlsx.py` — new
- `.gsd/DECISIONS.md` — DECISION-012; DECISION-002 marked superseded

## Verification
- Header normalisation, reorder / unknown / missing / duplicate headers: ✅
- Every ColumnKind accepts a valid value and rejects an invalid one with a readable message; format → parse round trip for every kind: ✅
- Writer: `*` on required headers, section fills, freeze `A2`, AutoFilter, list validations, `@` on text cells, Instructions sheet, report columns, hidden `Lists` sheet (checked with openpyxl as an independent reader): ✅
- Reader: shared strings (in memory and spilled to disk), inline / rich text, formulas (cached value), booleans, rows without `r`, reordered columns: ✅
- Sheet split at `rows_per_sheet` with header on each sheet; reader reads every matching sheet and skips Instructions; `estimated_rows` from `<dimension>`: ✅ (NFR-10)
- Stops after 1,000 empty rows; `max_rows` limit; missing-header message: ✅ (NFR-09)
- DOCTYPE / ENTITY refused, damaged XML, non-zip and oversized cells rejected: ✅ (NFR-09)
- 100,000-row round trip: write peak **0.8 MB**, read peak **8.3 MB** (tracemalloc), 25 s including tracing overhead: ✅ (NFR-01)
