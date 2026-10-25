---
phase: 3
plan: 2
wave: 2
depends_on:
  - 1
files_modified:
  - app/modules/dataexchange/infrastructure/vlcc_repository.py
  - app/modules/dataexchange/application/vlcc_import.py
  - app/worker/exchange.py
  - tests/dataexchange/test_vlcc_import.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "VLCC import matches by vlcc_code among the owner's VLCCs; matching row updates, non-matching row inserts"
    - "A new VLCC gets created_by = selected owner ID (from job.target_id), not the logged-in user"
    - "A row is discarded if its code conflicts with another record in the owner's hierarchy line via Hierarchy.code_conflict"
    - "A row is discarded if mobile or email is taken by another user (deleted included) or repeats earlier in the file"
    - "On update, blank cells keep existing values across VLCC, user, address, bank, settings, and milk quality"
    - "On insert, blank settings and milk quality take standard form defaults"
    - "Writes execute in adaptive batches respecting the 250ms DB lock budget"
    - "Worker registers VLCC_IMPORT and VLCC_EXPORT processors"
  artifacts:
    - "VlccImportProcessor (kind VLCC_IMPORT)"
  key_links:
    - "Requirements: REQ-14, REQ-15, REQ-16; DECISIONS: 003, 004, 006, 010, 011"
---

# Plan 3.2: VLCC Import Pipeline & Worker Registration

<objective>
Implement the streaming VLCC import pipeline with hierarchy code conflict checking, seen-keys deduplication, Argon2 password caching, and multi-table Core bulk upsert across 6 tables, registered in the exchange worker.

Output: `VlccExchangeRepository` (bulk upsert), `VlccImportProcessor`, worker registration.
</objective>

<context>
- .gsd/phases/3/RESEARCH.md, .gsd/phases/3/1-PLAN.md
- app/modules/dataexchange/domain/sheets.py (VLCC_SHEET)
- app/modules/dataexchange/infrastructure/vlcc_repository.py
- app/modules/dataexchange/infrastructure/seen_keys.py
- app/modules/administration/infrastructure/hierarchy.py (Hierarchy.code_conflict)
- app/worker/exchange.py
</context>

<tasks>

<task type="auto">
  <name>VLCC bulk repository (upsert side)</name>
  <files>
    app/modules/dataexchange/infrastructure/vlcc_repository.py
  </files>
  <action>
    Add methods to `VlccExchangeRepository`:
    1. Pre-check queries:
       - `get_owner_vlccs_by_codes(owner_id, codes)`: Returns existing VLCCs with user_id, address_id, bank_account_id, settings_id, milk_quality_config_id.
       - `check_code_conflicts(owner_id, codes)`: Checks if any of the given `codes` exist in `vlcc_master` where `Hierarchy.code_conflict` applies to the owner (excluding the owner's own active/deleted VLCCs).
       - `get_users_by_emails(emails)` and `get_users_by_mobiles(mobiles)`.
    2. Core bulk execution:
       - `bulk_insert(owner_id, rows_to_insert)`: Inserts into `users` (Role.VLCC), `addresses`, `bank_accounts`, `settings`, `milk_quality_configs`, and `vlcc_master` with `created_by = owner_id`.
       - `bulk_update(owner_id, rows_to_update)`: Updates modified fields in each table where value is not blank.
       - Row-by-row fallback with savepoints on IntegrityError.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.infrastructure.vlcc_repository import VlccExchangeRepository; print(VlccExchangeRepository)"</verify>
  <done>Repository supports multi-table Core bulk upsert and hierarchy conflict validation.</done>
</task>

<task type="auto">
  <name>VLCC import processor and worker registration</name>
  <files>
    app/modules/dataexchange/application/vlcc_import.py
    app/worker/exchange.py
  </files>
  <action>
    1. Implement `VlccImportProcessor(database, repository, batcher)`:
       - Registered with kind `VLCC_IMPORT`.
       - Streams rows using `XlsxSheetReader`.
       - Validates rows against `VLCC_SHEET`.
       - Deduplicates `vlcc_code`, `mobile`, `email` using `SeenKeys`.
       - Checks hierarchy code conflicts via `repository.check_code_conflicts`.
       - Hashes default password (`Vitco@123`) once; custom passwords hashed in threadpool.
       - Writes in adaptive batches via `JobContext.run_batch`.
       - Discards invalid/conflicting rows to `discarded.xlsx` with `Row No` and `Reason`.
       - Reports total, processed, inserted, updated, discarded counts.
    2. Register `VlccExportProcessor` and `VlccImportProcessor` in `app/worker/exchange.py`.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_vlcc_import.py -q → green</verify>
  <done>VLCC import pipeline processes batches and registers in exchange worker.</done>
</task>

<task type="auto">
  <name>VLCC import tests on a real database</name>
  <files>
    tests/dataexchange/test_vlcc_import.py
  </files>
  <action>
    Add automated tests verifying:
    - New VLCC insert creates records across all 6 tables with `created_by = target_id`.
    - Existing VLCC update updates records without overwriting omitted/blank cells.
    - Duplicate mobile or email in file or existing in DB rejects only that row.
    - Code conflict in hierarchy line rejects row with clear reason.
    - Blank settings and milk quality take correct defaults on insert.
    - Discarded file contains all original columns + `Row No` and `Reason`.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_vlcc_import.py -q → green</verify>
  <done>All import tests pass.</done>
</task>

</tasks>

<verification>
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange/test_vlcc_import.py -q` passes
</verification>
