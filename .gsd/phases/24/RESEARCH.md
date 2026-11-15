# Phase 24 Research: Collection Excel column order, deleted rows and new columns

**Requested by:** user, 2026-11-15
**Branch:** `feature/collection-export-column-order`, from `bugfix/report-member-page-break` (11777d4), the current
work line (`develop` is behind, DECISION-021).

## Request (user's words, summarised)
1. Collection Excel export (MCC and VLCC) writes its columns in a stored sequence. Only the collection export uses it.
2. Super Admin, every Admin and every Sub Admin has their own sequence. A new Admin / Sub Admin starts on the default;
   it can be changed any time.
3. An MCC or VLCC login exporting its collections gets its **owner's** (creator's) sequence. Super Admin, Admin and
   Sub Admin get their own.
4. Deleted entries are in the file, and a deleted row has a red background.
5. New columns: "Chart Rank" (R1, R2, R3 …), "Quantity Mode", "Measurement Mode".

## User answers (2026-11-15)
| Question | Answer |
|----------|--------|
| One sequence for both sheets, or one per sheet? | **One combined sequence**: one list of every collection column; a sheet skips the columns it does not have |
| Only order, or hide / show too? | **Order + hide / show** (at least one column stays visible) |
| VLCC created by an MCC user: whose sequence? | **The MCC's creator** (walk VLCC → MCC → its Admin / Sub Admin / Super Admin) |
| Who may edit whose sequence? | **Upward control**: everyone their own; Super Admin anyone's; Admin its own Sub Admins' |

## What exists
- `dataexchange/application/collection_export.py`: `MccCollectionExportProcessor` / `VlccCollectionExportProcessor`,
  keyset pages, Summary sheet (Phase 21, DECISION-028). Columns come from `MCC_COLLECTION_SHEET` /
  `VLCC_COLLECTION_SHEET` in `domain/sheets.py`.
- `XlsxSheetWriter(path, sheet, columns=...)` already takes an explicit column list, so a layout is just a reordered,
  filtered tuple of `ColumnSpec`. Rows are written in `constant_memory` mode, cell by cell, so a row format must be
  passed while writing (it cannot be applied afterwards).
- Collection tables already store everything needed, no new collection column:
  - `rank: int | None` → "Chart Rank" = `R{rank}`, blank when null.
  - `quantity_collection_mode: QuantityCollectionMode` (MANUAL / AUTOMATIC) → "Quantity Mode".
  - `measurement_mode: MeasurementMode` (MANUAL / AUTOMATIC) → "Measurement Mode".
  - `is_deleted: bool`.
- `export_page` / `count_export` drop deleted rows through `_export_conditions`; `totals` excludes deleted rows (as
  the list's totals do).
- VLCC collections have no Sample No, Cans or CLR; MCC collections have no Farmer Code / Name.
- Ownership: `MccModel.user_id` / `created_by`, `VlccModel.user_id` / `created_by`; a VLCC's creator can be an MCC
  user (`Hierarchy.vlcc_creators`). Admin → Sub Admin is `UserModel.created_by == admin.id & role == SUB_ADMIN`
  (`Hierarchy.managers`).
- Schema changes: Alembic migrations in `app/core/database/migrations/versions/` (last `0003`); SQLite dev path
  also runs `create_all`. Migrations must check before creating (adopted databases).
- Web: Admin / Sub Admin pages live in `app/web/sub_admin/` (`list.html`, `view.html`, `create_edit.html`);
  own profile in `app/web/auth/controller.py` (`profile.html`).

## Combined column catalogue (default order)
| # | Key | Header | MCC | VLCC |
|---|-----|--------|-----|------|
| 1 | date | Date | ✓ | ✓ |
| 2 | time | Time | ✓ | ✓ |
| 3 | shift | Shift | ✓ | ✓ |
| 4 | sample_number | Sample No | ✓ | |
| 5 | mcc_code | MCC Code | ✓ | |
| 6 | mcc_name | MCC Name | ✓ | |
| 7 | vlcc_code | VLCC Code | ✓ | ✓ |
| 8 | vlcc_name | VLCC Name | ✓ | ✓ |
| 9 | farmer_code | Farmer Code | | ✓ |
| 10 | farmer_name | Farmer Name | | ✓ |
| 11 | milk_type | Milk Type | ✓ | ✓ |
| 12 | can_count | Cans | ✓ | |
| 13 | quantity | Quantity | ✓ | ✓ |
| 14 | quantity_mode | Quantity Mode | ✓ | ✓ |
| 15 | fat_percent | FAT % | ✓ | ✓ |
| 16 | snf_percent | SNF % | ✓ | ✓ |
| 17 | clr_value | CLR | ✓ | |
| 18 | measurement_mode | Measurement Mode | ✓ | ✓ |
| 19 | chart_rank | Chart Rank | ✓ | ✓ |
| 20 | rate_per_unit | Rate | ✓ | ✓ |
| 21 | total_amount | Amount | ✓ | ✓ |
| 22 | status | Status | ✓ | ✓ |
| 23 | payment_mode | Payment Mode | ✓ | ✓ |
| 24 | deleted | Deleted | ✓ | ✓ |

The existing Phase 21 order is kept; the new columns sit next to the values they describe.

## Design (DECISION-030)
- **Storage:** new table `excel_column_layouts` (`id`, `user_id` FK users ON DELETE CASCADE, `sheet` String(40) =
  `"collections"`, `columns` JSON `[{"key": "...", "visible": true}, …]`, audit timestamps), unique
  `(user_id, sheet)`. **No row = default.** Nothing is written when an Admin / Sub Admin is created, so a column
  added in a later release reaches everyone on the default automatically.
- **Normalising** (domain, pure): unknown and repeated keys dropped; catalogue keys missing from a stored layout are
  inserted visible after their default predecessor; at least one visible column, else 422.
- **Whose layout an export uses** (resolved by the worker from the job's user):
  Super Admin / Admin / Sub Admin → self; MCC → its MCC's `created_by`; VLCC → its VLCC's `created_by`, and if that
  user is an MCC user → that MCC's `created_by`. Missing, deleted or non-manager owner → default.
- **Edit permission:** self (Super Admin / Admin / Sub Admin); Super Admin → any Admin / Sub Admin; Admin → Sub Admins
  it created. MCC, VLCC, Farmer: no access (403). Other targets: 404 (no existence leak).
- **Deleted rows:** included, in date order with the rest; every cell of the row (blank cells too) gets a light-red
  fill (`#FFC7CE`, dark-red text `#9C0006`), and the "Deleted" column says "Yes". Summary totals stay without
  deleted entries (they match the list); Summary adds "Deleted Entries" and a note "Red rows are deleted entries".
  This replaces the "no deleted rows" part of DECISION-028.

## Risks
- `constant_memory` writes rows in order only: the row format must be known when the row is written → pass a
  per-row flag to `write_rows`.
- Postgres JSON vs SQLite JSON: use `sqlalchemy.JSON` (works on both); never query inside it.
- Tests in `tests/dataexchange/test_collection_export.py` assert "no deleted rows" and fixed headers; they change with
  this phase.
