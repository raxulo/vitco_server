---
phase: 2
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/modules/dataexchange/infrastructure/farmer_repository.py
  - app/modules/dataexchange/infrastructure/seen_keys.py
  - app/modules/dataexchange/application/farmer_import.py
  - tests/dataexchange/test_seen_keys.py
  - tests/dataexchange/test_farmer_import.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Upsert by farmer_code inside the target VLCC: match → update, else insert; CREATE_ONLY discards existing codes"
    - "Discard (row only, with a reason): parse errors; missing farmer_code; on insert missing name / mobile; code of a soft-deleted farmer; mobile / email used by another user (deleted users included); code / mobile / email repeated earlier in the file"
    - "Blank cell on update keeps the stored value; blank password on insert = Vitco@123 hashed once per job; blank email on insert = farmer_<code>_<hex6>@dairy.local"
    - "Each batch is written with one Core INSERT / UPDATE executemany per table; a batch that hits IntegrityError is retried row by row in savepoints and only clashing rows are discarded"
    - "Discarded rows go to discarded_rows.xlsx (same columns + Row No + Reason, password left blank) and the job counters show inserted / updated / discarded"
    - "dry_run validates everything and writes nothing"
    - "100,000-row import ≥ 1,500 farmers/s on the dev machine, worker RSS flat"
  key_links:
    - "Requirements: REQ-08, REQ-09, REQ-10, REQ-11, NFR-01, NFR-03, NFR-08; DECISION-003, 006"
---

# Plan 2.2: Farmer Import Pipeline

<objective>
Implement the farmer import processor: stream the file, validate, classify, pre-check against the DB in three indexed queries per batch, dedupe across the file, hash passwords in parallel, write with bulk SQL inside the lock budget, and report discarded rows.
</objective>

<context>
- .gsd/phases/2/RESEARCH.md (rules + levers), .gsd/phases/2/1-PLAN.md outputs
- app/modules/dataexchange/application/processor.py, batching.py; infrastructure/xlsx.py, seen_keys.py
- app/modules/auth/infrastructure/password.py (PasswordService.hash)
- app/core/validators.py (mobile_number)
</context>

<tasks>

<task type="auto">
  <name>Bulk write + pre-check queries; two-phase SeenKeys</name>
  <files>
    app/modules/dataexchange/infrastructure/farmer_repository.py
    app/modules/dataexchange/infrastructure/seen_keys.py
    tests/dataexchange/test_seen_keys.py
  </files>
  <action>
    1. FarmerExchangeRepository additions (all Core, one statement per call):
       - `existing_by_codes(vlcc_id, codes) -> dict[code, ExistingFarmer]` (farmer id / user id / address id / bank id / is_deleted + current user, address, bank values) — one joined query, deleted included;
       - `users_by_emails(lower_emails) -> dict[email, user_id]` using `lower(email) IN` (served by ix_users_email_lower), `users_by_mobiles(mobiles) -> dict[mobile, user_id]`;
       - `insert_many(users, addresses, banks, farmers)` and `update_many(users, farmers, addresses, banks)` — `Table.insert()` / `update(Table).where(Table.c.id == bindparam("b_id")).values(...)` executemany; chunk IN lists at 900 values.
    2. SeenKeys: add `find(keys) -> dict[(kind, value), first_row]` (no insert) and `add(keys)`; `check_and_add` stays (implemented with them). Tests: find does not register; add then find reports the row.
    AVOID: ORM `session.add` per row (~15 % slower and keeps objects in the identity map).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_seen_keys.py -q → green</verify>
  <done>Repository supports the three pre-checks and bulk insert / update; SeenKeys supports check-then-register.</done>
</task>

<task type="auto">
  <name>FarmerImportProcessor</name>
  <files>app/modules/dataexchange/application/farmer_import.py</files>
  <action>
    `FarmerImportProcessor(database, repository, password_service)`, kind FARMER_IMPORT. Per job: default hash once (`to_thread`); `XlsxSheetReader` + `SeenKeys` + report writer (lazy: created on the first discard) in the job folder; total = reader.estimated_rows.
    Pipeline: read batches of 500 in a thread, prefetching the next while the current is processed. Per batch:
    1. parse every cell (`parse_cell`), collect errors (first 3, "; "-joined);
    2. require farmer_code; look up existing farmers (one query); deleted → discard; CREATE_ONLY + exists → discard; insert requires name + mobile;
    3. contact checks: emails (lower) / mobiles that are new or changed → two queries; owned by another user → discard;
    4. in-file duplicates: `SeenKeys.find` for code / mobile / email (+ a dict for duplicates inside this batch); duplicates → discard "<Column> repeats row N"; `SeenKeys.add` only for accepted rows;
    5. build row dicts: insert (ids, generated email, default / custom hash, holder = name when bank given without holder, defaults) and update (merge onto stored values — blank keeps);
    6. custom passwords hashed in a `ThreadPoolExecutor(max_workers=min(4, cpu))` (argon2 releases the GIL) before the write;
    7. write in sub-batches of `ctx.batcher.size` with `ctx.run_batch` (skip when dry_run); on IntegrityError retry the sub-batch row by row in `database.transaction()` savepoints, discard rows that still fail ("Saved by someone else at the same time: …");
    8. counters + `checkpoint()`.
    Report: same columns + Row No + Reason; password cells blank; result `ProcessorResult(report_file="discarded_rows.xlsx")` when anything was discarded.
    AVOID: registering keys of discarded rows in SeenKeys; hashing passwords on the event loop; reading the whole file first.
  </action>
  <verify>covered by the next task</verify>
  <done>Processor implements every rule in must_haves.</done>
</task>

<task type="auto">
  <name>Import tests + throughput measurement</name>
  <files>tests/dataexchange/test_farmer_import.py</files>
  <action>
    Real DB rows; files written with XlsxSheetWriter (and one hand-made header order). Cases: insert new; update existing with blank-keeps; CREATE_ONLY; deleted code; mobile of another user (incl. a deleted user); email case-insensitive clash; in-file duplicate code / mobile / email ("repeats row N"); parse errors; missing name on insert but allowed blank on update; default password verifies with PasswordService, custom password too; generated email; bank holder default; dry_run writes nothing but counts; report file has Row No + Reason and blank passwords; IntegrityError fallback (pre-insert a clashing mobile between pre-check and write via a test hook) discards only that row; other VLCC's farmers untouched.
    Throughput: 100,000-row file → assert ≥ 1,500 rows/s and print rows/s + peak RSS (marked `slow`, still run in CI here).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_farmer_import.py -q -s → green, throughput line printed</verify>
  <done>All rule cases pass; measured throughput recorded in the SUMMARY.</done>
</task>

</tasks>

<verification>
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` green
- [ ] Throughput ≥ 1,500 farmers/s, peak worker RSS reported
</verification>

<success_criteria>
- [ ] All tasks verified; must-haves confirmed
</success_criteria>
