---
phase: 24
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/modules/dataexchange/domain/column_layout.py
  - app/modules/dataexchange/domain/irepository.py
  - app/modules/dataexchange/domain/exceptions.py
  - app/modules/dataexchange/infrastructure/models.py
  - app/modules/dataexchange/infrastructure/column_layout_repository.py
  - app/modules/dataexchange/application/command.py
  - app/modules/dataexchange/application/column_layout_handler.py
  - app/modules/dataexchange/application/collection_export.py
  - app/core/database/migrations/versions/20261115_0004_excel_column_layouts.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - app/worker/exchange.py
  - app/api/v1/routers/excel.py
  - app/api/v1/schemas/excel.py
  - tests/dataexchange/test_column_layout.py
must_haves:
  - Super Admin, each Admin and each Sub Admin has their own collection column layout (order + visible); no row = default
  - The export uses the layout of the right user (self for managers, the MCC's / VLCC's owner for MCC / VLCC logins, walking an MCC-created VLCC up to the MCC's creator)
  - Edit rules - self; Super Admin any Admin / Sub Admin; Admin its own Sub Admins; anyone else 403 / 404
  - Works on PostgreSQL and SQLite (migration 0004)
gap_closure: false
---

# Plan 24.2: Per-user column layout and its API

## Objective
Store each manager's collection column layout and apply it to every collection export (REQ-55, REQ-56, REQ-57,
DECISION-030).

## Tasks

<task type="auto">
  <name>Domain, table and repository</name>
  <files>domain/column_layout.py, irepository.py, exceptions.py, infrastructure/models.py,
  column_layout_repository.py, migration 0004</files>
  <action>Domain: `ColumnLayoutItem(key, visible)`, `ColumnLayout` with `default()`, `normalise(stored)` (drop
  unknown / repeated keys, insert missing catalogue keys visible after their default predecessor) and
  `columns_for(sheet)`; `ColumnLayoutEmpty` (422) when nothing is visible. Model `ExcelColumnLayoutModel(Base,
  UUIDMixin, AuditMixin)` on `excel_column_layouts`, unique (user_id, sheet), JSON `columns`. Repository: `get(user_id)`,
  `save(user_id, items)` (upsert), `delete(user_id)` (reset), `layout_owner(user)` (VLCC → MCC → creator walk) and
  `can_manage(actor, target_id)`. Migration 0004 creates the table only when missing.
  AVOID: writing a row when an Admin / Sub Admin is created; querying inside the JSON; framework imports in domain.</action>
  <verify>unit tests for normalise; repository tests for owner walk (MCC, VLCC by manager, VLCC by MCC user,
  deleted owner → default) on SQLite and Postgres; `alembic upgrade head` on both</verify>
  <done>Layouts round-trip and the owner walk returns the expected user in every case.</done>
</task>

<task type="auto">
  <name>Handler, API and export wiring</name>
  <files>application/command.py, column_layout_handler.py, collection_export.py, configurator.py, dependencies.py,
  worker/exchange.py, routers/excel.py, schemas/excel.py</files>
  <action>`ColumnLayoutHandler` (`__slots__`, writes in a transaction): `get`, `update`, `reset`, each checking
  `can_manage`. REST, standard `data` envelope:
  `GET /api/v1/excel/column-layouts/collections[?user_id=]` (items with key, header, visible, sheets; plus
  `is_default`), `PUT` same path (full ordered list), `DELETE` same path (back to default). The export processors
  resolve `layout_owner(ctx.owner)` and pass `layout.columns_for(sheet)` to `XlsxSheetWriter(columns=...)`;
  `_format` follows those columns.
  AVOID: trusting `user_id` without `can_manage`; resolving the layout in the API process instead of the worker.</action>
  <verify>tests/dataexchange/test_column_layout.py: own / Super Admin → Admin / Admin → own Sub Admin allowed;
  Admin → other Admin's Sub Admin 404; Sub Admin → its Admin 404; MCC / VLCC / Farmer 403; empty layout 422;
  MCC and VLCC exports follow the owner's layout (hidden columns absent); reset returns the default</verify>
  <done>Exports follow the stored layout for every role; API enforces the edit rules.</done>
</task>
