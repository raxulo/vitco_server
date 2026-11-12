---
phase: 21
plan: 1
status: complete
commit: pending (one commit with Plan 20.3, after user approval)
---

# Plan 21.1 Summary: Collection Excel Export

## Done
- Job kinds `MCC_COLLECTION_EXPORT` (9) and `VLCC_COLLECTION_EXPORT` (10); PostgreSQL enum values in migration `0002`.
- `SubmitExportCommand.params` → `params.json` in the job folder, written before the job row exists
  (`ExchangeStorage.write_params` / `read_params`, atomic).
- `MccCollectionRepository` / `VlccCollectionRepository`: `count_export` and `export_page` reuse the list's
  `_list_conditions` (access scope + filters), drop deleted entries, keyset on `(collected_at, id)`.
- `collection_export.py`: `CollectionExportFilters` (params round-trip) and the two processors; rows are written
  while the next page is read; a Summary sheet with period, centre, milk type, search, entries and totals.
- `XlsxSheetWriter`: real Excel dates (`dd-mm-yyyy`) and `write_summary`.
- `collection_exchange.py` + `POST /api/v1/excel/mcc-collections/export` and `/vlcc-collections/export`
  (`CollectionExportRequest`, blank values = not set, 409 / 429 as other exports).
- Web: Export Excel button in both list headers (`ui.page_head(..., export_kind)`), `exportCollectionsToExcel`
  sends the page's URL filters and reuses the modal's progress, polling and download; JS cache version bumped.

## Columns
- MCC: Date, Time, Shift, Sample No, MCC Code, MCC Name, VLCC Code, VLCC Name, Milk Type, Cans, Quantity,
  FAT %, SNF %, CLR, Rate, Amount, Status, Payment Mode.
- VLCC: Date, Time, Shift, VLCC Code, VLCC Name, Farmer Code, Farmer Name, Milk Type, Quantity, FAT %, SNF %,
  Rate, Amount, Status, Payment Mode.

## Verification
- `tests/dataexchange/test_collection_export.py` (9 tests, real worker, page size 2): Sub Admin, MCC, VLCC and
  another Admin each get exactly their list's entries, no deleted ones, oldest first; milk type, shift range and
  VLCC filters; a foreign MCC filter gives an empty file; farmer 403; bad filter 422. Pass on SQLite and PostgreSQL.
- /verify on PostgreSQL through the web login (cookie + HX-Request): button on both list pages; Sub Admin MCC
  export with the COW filter, VLCC export without filters, MCC login export; files and Summary checked.
