---
phase: 24
plan: 2
status: complete
verified: 2026-11-15
---

# Plan 24.2 Summary: Per-user column layout and its API

## Delivered (REQ-55, REQ-56, REQ-57, DECISION-030)
- Domain `column_layout.py`: `ColumnLayoutItem`, `ColumnLayout` (`default`, `normalise`, `from_request`,
  `ensure_visible`, `columns_for`), `LayoutUser`. Normalise drops unknown / repeated keys and puts missing catalogue
  keys back, visible, after their default predecessor. A request with an unknown or repeated key, or one that
  leaves the MCC or the VLCC export without a visible column, is 422 (`ColumnLayoutInvalidException`).
- Table `excel_column_layouts` (`ExcelColumnLayoutModel`: user_id FK CASCADE, sheet, JSON columns, audit; unique
  (user_id, sheet)), migration `0004` (creates it only when missing). No row = default.
- `ColumnLayoutRepository` (`IColumnLayoutRepository`): get / save (upsert) / delete, `layout_owner` (manager self;
  MCC -> MCC creator; VLCC -> VLCC creator, or that MCC's creator when an MCC user made it; deleted owner or other
  roles -> default), `manageable_user` (self; Super Admin -> any Admin / Sub Admin; Admin -> own Sub Admins).
- `ColumnLayoutHandler` (get / update / reset / can_manage) registered in the configurator; `GetHandler.column_layout_handler`.
- REST: `GET / PUT / DELETE /api/v1/excel/column-layouts/collections[?user_id=]`, `data` envelope with
  user, `is_default` and the columns (key, header, visible, sheets). MCC / VLCC / Farmer 403, outside the line 404.
- Export processors resolve the layout per job in the worker (`layout_for_export`) and pass its columns to the
  writer; the column list is no longer kept on the shared processor (two jobs can run at once).

## Verification
- `tests/dataexchange/test_column_layout.py`: 21 passed on SQLite and PostgreSQL (rules, every edit-rule case,
  422s, the Sub Admin's order followed by its own, its MCC's, its VLCC's and the MCC-made VLCC's exports, other
  Admin on default, reset, owner walk incl. deleted owner).
- `tests/test_schema_migrations.py` on both databases (head = 0004, models match).
