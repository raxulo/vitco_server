---
phase: 24
plan: 1
status: complete
verified: 2026-11-15
---

# Plan 24.1 Summary: Combined columns, new columns and deleted rows

## Delivered (REQ-53, REQ-54, DECISION-030)
- `sheets.py`: `CollectionSheet` (mcc / vlcc), `COLLECTION_CATALOGUE` (24 columns, each with the sheets that have
  it), `COLLECTION_COLUMNS` / `COLLECTION_COLUMN_KEYS`, `collection_columns(sheet, keys)`. `MCC_COLLECTION_SHEET`
  (22 columns) and `VLCC_COLLECTION_SHEET` (19 columns) are built from it.
- New columns: Quantity Mode then Measurement Mode right after FAT % / SNF % / CLR (user, 2026-11-15; first built
  with Quantity Mode after Quantity), Chart Rank `R{rank}` (blank
  without a rank), Deleted ("Yes" / blank, last).
- Both repositories: `count_export` / `export_page` use the list's own conditions (deleted entries included) and
  select `quantity_collection_mode`, `measurement_mode`, `rank`, `is_deleted`. `totals` unchanged (already left
  deleted entries out and counted them apart).
- `XlsxSheetWriter.write_rows(rows, highlight)`: a highlighted row gets every cell, blanks included, in light red
  `#FFC7CE` with dark red text; text and date columns keep `@` / `dd-mm-yyyy`.
- Summary: Entries = active entries, new "Deleted Entries" and a note that red rows are deleted and not in the totals.

## Verification
- `tests/dataexchange/test_collection_export.py`: 11 passed on SQLite and PostgreSQL (headers in default order,
  R1 / R12 / blank rank, mode labels, red fill on every cell of the deleted row read back with openpyxl, totals
  70 with 1 deleted).
