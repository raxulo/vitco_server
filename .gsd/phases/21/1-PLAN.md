---
phase: 21
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/dataexchange/domain/enums.py
  - app/modules/dataexchange/domain/sheets.py
  - app/modules/dataexchange/application/command.py
  - app/modules/dataexchange/application/handler.py
  - app/modules/dataexchange/application/collection_exchange.py
  - app/modules/dataexchange/application/collection_export.py
  - app/modules/dataexchange/infrastructure/xlsx.py
  - app/modules/collections/mcc_collection/infrastructure/repository.py
  - app/modules/collections/vlcc_collection/infrastructure/repository.py
  - app/core/database/migrations/versions/20261112_0002_collection_export_kinds.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - app/worker/exchange.py
  - app/api/v1/routers/excel.py
  - app/api/v1/schemas/excel.py
  - app/web/static/js/excel_exchange.js
  - app/web/templates/components/excel_modal.html
  - app/web/templates/pages/mcc_collection/list.html
  - app/web/templates/pages/vlcc_collection/list.html
  - tests/dataexchange/test_collection_export.py
must_haves:
  - MCC and VLCC collection lists have an Export Excel button that exports the rows matching the current filters
  - The export holds exactly the rows the list would show for that user, without deleted entries
  - A Summary sheet repeats the filters and the totals shown above the list
  - Works on PostgreSQL and SQLite, for every role that can open the list
gap_closure: false
---

# Plan 21.1: Collection Excel Export

## Objective
Export MCC and VLCC collections to Excel from their list pages (REQ-48, REQ-49), using the existing Excel job
system so a large export never blocks the API (DECISION-008, DECISION-028).

## Decisions (DECISION-028)
- Export only. Collections are entered on devices and forms, not imported.
- Background job, like farmer and VLCC exports: new kinds `MCC_COLLECTION_EXPORT` and `VLCC_COLLECTION_EXPORT`.
- The filters go to the worker as `params.json` in the job folder, so `excel_jobs` needs no new column. Postgres
  needs one migration for the two new `exceljobkind` values.
- Scope: the worker uses the requesting user (as all jobs do) and the list's own access scope, so the export
  can never hold rows the list would hide.
- Deleted entries are left out, as in the list totals.
- Rows run oldest first (date, then shift order by time, then id), read by keyset pages.
- Codes and names, never UUIDs. A Summary sheet lists the filters and the totals.

## Tasks

<task type="auto">
  <name>Job kinds, params and export processors</name>
  <files>dataexchange domain / application / infrastructure, collection repositories, migration 0002, worker</files>
  <action>Add the two kinds and the migration. `SubmitExportCommand.params` is written to `params.json` in the job
  folder. Each collection repository gets `export_page(owner, filters, after, limit)` (keyset on
  collected_at, id; no deleted rows) and the processor writes rows with `XlsxSheetWriter` plus a Summary sheet.
  AVOID: offset pagination for export; reading the filters from anything the worker did not get from the job.</action>
  <verify>tests/dataexchange/test_collection_export.py on SQLite and Postgres</verify>
  <done>Exported rows equal the list rows for the same filters and user, per role.</done>
</task>

<task type="auto">
  <name>API and web</name>
  <files>excel router / schemas, excel_exchange.js, excel_modal.html, both list templates</files>
  <action>`POST /api/v1/excel/mcc-collections/export` and `/vlcc-collections/export` take the list's filters.
  The list pages get an Export Excel button that sends the current filters and reuses the modal's progress and
  download view.
  AVOID: a second polling implementation.</action>
  <verify>/verify: export from both lists as Sub Admin and MCC on Postgres; open the files</verify>
  <done>Downloaded files match the filtered lists.</done>
</task>
