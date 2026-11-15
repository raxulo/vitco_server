---
phase: 24
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/dataexchange/domain/sheets.py
  - app/modules/dataexchange/infrastructure/xlsx.py
  - app/modules/dataexchange/application/collection_export.py
  - app/modules/collections/mcc_collection/infrastructure/repository.py
  - app/modules/collections/vlcc_collection/infrastructure/repository.py
  - tests/dataexchange/test_collection_export.py
must_haves:
  - One combined collection column catalogue; MCC and VLCC sheets take their columns from it in its default order
  - Chart Rank (R1, R2 … ; blank when no rank), Quantity Mode and Measurement Mode (Manual / Automatic) in both exports
  - Deleted entries are exported, every cell of their row has a red background, and the Deleted column says Yes
  - Summary totals still exclude deleted entries; the Summary shows the deleted count and what red means
gap_closure: false
---

# Plan 24.1: Combined columns, new columns and deleted rows

## Objective
Change what the collection export writes (REQ-53, REQ-54), still in the default order. Plan 24.2 adds the per-user
order on top of the catalogue built here.

## Tasks

<task type="auto">
  <name>Combined catalogue and new columns</name>
  <files>dataexchange/domain/sheets.py, both collection repositories, collection_export.py</files>
  <action>Add `COLLECTION_COLUMNS` (the 24 columns in RESEARCH.md, each with the sheets it applies to) and build
  `MCC_COLLECTION_SHEET` / `VLCC_COLLECTION_SHEET` from it. `export_page` also selects `rank`,
  `quantity_collection_mode`, `measurement_mode`, `is_deleted`. `_format` writes `chart_rank = f"R{rank}"`,
  `quantity_mode` / `measurement_mode` as their labels, `deleted = "Yes"` or blank.
  AVOID: changing the collection tables; UUIDs in the file; a second catalogue per sheet.</action>
  <verify>test: both files carry the new headers in default order; R-prefixed rank; mode labels; null rank blank</verify>
  <done>Headers and values match RESEARCH.md for MCC and VLCC.</done>
</task>

<task type="auto">
  <name>Deleted rows in red</name>
  <files>infrastructure/xlsx.py, collection repositories, collection_export.py</files>
  <action>`count_export` / `export_page` stop dropping deleted entries (still scoped by the list's access and filters);
  `totals` keeps excluding them. `XlsxSheetWriter.write_rows` takes an optional per-row highlight flag and writes every
  cell, blanks included, with a red-fill format (text / date variants keep their number formats). Summary adds
  "Deleted Entries" and "Red rows are deleted entries".
  AVOID: post-processing the file (constant_memory); counting deleted rows in Total Quantity / Amount.</action>
  <verify>test: deleted entry present with red fill on every cell (read back with openpyxl), totals unchanged,
  deleted count right; existing role / filter tests still pass on SQLite and Postgres</verify>
  <done>A deleted entry appears in date order with a red row; totals match the list.</done>
</task>
