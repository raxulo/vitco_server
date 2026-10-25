---
phase: 2
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/dataexchange/domain/sheets.py
  - app/modules/dataexchange/infrastructure/farmer_repository.py
  - app/modules/dataexchange/infrastructure/indexes.py
  - app/modules/dataexchange/application/farmer_export.py
  - app/modules/dataexchange/application/templates.py
  - tests/dataexchange/test_farmer_export.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "FARMER_SHEET declares 18 columns (farmer 5, user 4 incl. import-only password, address 4, bank 5); farmer_code, name, mobile are required"
    - "Export of one VLCC writes every non-deleted farmer of that VLCC (and no other VLCC's) ordered by farmer_code, with user / address / bank values, in FARMER_SHEET format"
    - "Export pages with keyset pagination (no OFFSET) and overlaps the next DB page with writing the previous one"
    - "ix_users_email_lower exists after ensure_indexes(); running it twice is harmless"
    - "The template is built once and served from a cached file"
  artifacts:
    - "FarmerExportProcessor (kind FARMER_EXPORT) usable by the worker"
  key_links:
    - "Requirements: REQ-06 (scope via target_id), REQ-07; RESEARCH levers 2, 4, 6, 7"
---

# Plan 2.1: Farmer Sheet, Bulk Repository & Export

<objective>
Declare the farmer sheet once, add the bulk-SQL repository the import and export share, and implement the export processor at full speed.

Output: `FARMER_SHEET`, `FarmerExchangeRepository` (export queries now; bulk writes in 2.2), `ensure_indexes`, `FarmerExportProcessor`, cached template builder.
</objective>

<context>
- .gsd/phases/2/RESEARCH.md
- .gsd/REQUIREMENTS.md (REQ-06, REQ-07, REQ-10), .gsd/DECISIONS.md (003, 007, 011, 012)
- app/modules/dataexchange/domain/columns.py, infrastructure/xlsx.py, application/processor.py
- app/modules/farmer/infrastructure/models.py, repository.py (FarmerAccessScope)
- app/modules/administration/infrastructure/models.py, common/address, common/bank models
- app/api/v1/routers/farmer.py (defaults), app/modules/farmer/domain/enums.py (MilkType)
</context>

<tasks>

<task type="auto">
  <name>Farmer sheet spec and email expression index</name>
  <files>
    app/modules/dataexchange/domain/sheets.py
    app/modules/dataexchange/infrastructure/indexes.py
  </files>
  <action>
    1. domain/sheets.py: `FARMER_SHEET = SheetSpec(name="Farmers", key_column="farmer_code", columns=(...))` in this order:
       - Farmer: Farmer Code* (CODE, max 30), Milk Type (ENUM COW/BUFFALO/MIXED, default note MIXED), Rate Chart Rank (INT 1–100), SMS Enabled (BOOL), Active (BOOL);
       - User: Name* (TEXT max 150), Mobile* (MOBILE), Email (EMAIL), Password (PASSWORD, import_only, min 6, max 128);
       - Address: Address Line (TEXT 255), City (TEXT 100), State (TEXT 100), Pincode (PINCODE);
       - Bank: Account Holder (TEXT 150), Bank Name (TEXT 150), Account Number (ACCOUNT_NUMBER), IFSC Code (IFSC), UPI ID (TEXT 100).
       Each column gets a short `help` and `example` for the Instructions sheet.
    2. infrastructure/indexes.py: `async ensure_indexes(database)` → `CREATE INDEX IF NOT EXISTS ix_users_email_lower ON users (lower(email))` in a short transaction (works on SQLite and PostgreSQL); logs how long it took.
    AVOID: putting the index in `UserModel.__table_args__` only — `create_all` never adds indexes to an existing table.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.domain.sheets import FARMER_SHEET as s; print(len(s.columns), [c.key for c in s.columns if c.required])"  → `18 ['farmer_code', 'name', 'mobile']`</verify>
  <done>Sheet spec importable from the domain layer; index helper idempotent.</done>
</task>

<task type="auto">
  <name>Bulk repository (export side) and export processor</name>
  <files>
    app/modules/dataexchange/infrastructure/farmer_repository.py
    app/modules/dataexchange/application/farmer_export.py
    app/modules/dataexchange/application/templates.py
  </files>
  <action>
    1. `FarmerExchangeRepository(database)` (`__slots__`, `_session` property): `export_page(vlcc_id, after: tuple[str, UUID] | None, limit) -> list[Row]` — Core `select` of farmer columns + user name/mobile/email + address line/city/state/pincode + bank holder/name/number/ifsc/upi; `JOIN users`, `LEFT JOIN addresses / bank_accounts` on primary keys; `WHERE vlcc_id = :v AND is_deleted = false AND (farmer_code, id) > (:code, :id)`, `ORDER BY farmer_code, id LIMIT :n`; `count_export(vlcc_id)`.
    2. `FarmerExportProcessor(database, repository, page_size=1000)`, kind FARMER_EXPORT: total = count; writer = `XlsxSheetWriter(job_dir / "result.xlsx", FARMER_SHEET, tmpdir=job_dir)`; loop: page N fetched in its own read transaction while page N-1 is written via `asyncio.to_thread(writer.write_rows, rows)` (run both with `asyncio.gather`); rows built with `format_cell` per column; `ctx.processed += len(page)`; `await ctx.checkpoint()` per page; finally `write_instructions()` + `close()` in a thread. Result `ProcessorResult(result_file="result.xlsx")`.
       The target VLCC is `ctx.job.target_id`; scope was checked at submit (Plan 2.3).
    3. templates.py: `template_path(storage) -> Path` builds `storage.root / "templates" / f"farmers-v{TEMPLATE_VERSION}.xlsx"` once (header + validations + Instructions, no rows) with a file lock-free atomic write (`.part` + `os.replace`) and reuses it afterwards.
    AVOID: OFFSET pagination (gets slower every page); one long read transaction across the whole export (holds a WAL snapshot open and blocks checkpointing).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_farmer_export.py -q → green</verify>
  <done>Export writes exactly the VLCC's non-deleted farmers in code order; template cached.</done>
</task>

<task type="auto">
  <name>Export tests on a real database</name>
  <files>tests/dataexchange/test_farmer_export.py</files>
  <action>
    Real users / VLCCs / farmers / addresses / banks inserted in the test DB. Run the processor through a real `JobContext` (repository, storage under tmp).
    Cases: two VLCCs with 2,500 + 3 farmers → export of VLCC A has 2,500 rows in code order, none from B; a soft-deleted farmer is excluded; a farmer without address / bank exports blank cells; mobile and account number come back as text (read the file with XlsxSheetReader → round trip equals DB values); password column absent; page size 1000 with 2,500 rows exercises three pages; ensure_indexes twice → index present once (`PRAGMA index_list(users)`); template built once (second call returns the same file, mtime unchanged).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_farmer_export.py -q → green</verify>
  <done>All export cases pass against real rows.</done>
</task>

</tasks>

<verification>
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` green
- [ ] Export file opens in openpyxl with Farmers + Instructions sheets
</verification>

<success_criteria>
- [ ] All tasks verified; must-haves confirmed
</success_criteria>
