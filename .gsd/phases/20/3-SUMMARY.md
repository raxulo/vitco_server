---
phase: 20
plan: 3
status: complete
commit: pending (with Phase 21, on `feature/collection-excel-export`)
---

# Plan 20.3 Summary: Postgres Compatibility

Run on a local PostgreSQL 16 (portable `pgserver` build, timezone data added) after the user reported that
Sub Admin Excel import / export failed on PostgreSQL only.

## Found and fixed
- **Sub Admin / MCC Excel jobs failed: `operator does not exist: uuid = text`.**
  - The worker builds its owner from the job row; on PostgreSQL that id is asyncpg's own UUID class.
  - SQLAlchemy cannot type it, so `select(literal(owner.id))` in `Hierarchy` went out as an untyped parameter,
    which PostgreSQL reads as text inside a UNION / IN.
  - Admin was not affected: its `managers()` selects a real column.
  - Fix: `Hierarchy._self()` builds the literal as a typed UUID, and `JobContext` turns the job's ids into
    plain `uuid.UUID`. Without the fix 54 helper/role/id-type combinations failed on PostgreSQL; with it none.
- **Deleting a user or farmer failed: `value too long for type character varying(20)`.**
  - A soft delete stores `del_<6 hex>_` + the 10-digit mobile (21 chars) and `<code>__del_<6 hex>`.
  - Migration `0002`: `users.mobile` 20 → 32, `farmer_master.farmer_code` 30 → 50, PostgreSQL only (SQLite
    never enforces lengths, and changing one there would rebuild these tables).
- `test_recycle_bin.py` legacy-table test: skipped on PostgreSQL. Those tables only exist in upgraded SQLite
  databases; a PostgreSQL database always starts empty.

## Verification
- Full suite on PostgreSQL: 972 passed, 1 skipped, 1 failed (the known order-dependent
  `test_owner_options_super_admin`, which passes alone).
- Full suite on SQLite: 972 passed, the same known failure. `test_large_import_throughput[100000]` failed only
  while both suites ran at once and passes alone.
- `tests/test_hierarchy_id_types.py`: every Hierarchy helper for every role with a request id and a read-back id;
  5 fail on PostgreSQL without the fix.
- Real start on PostgreSQL (a database at `0001`): upgraded to `0002`, Sub Admin VLCC import with a new row
  inserted it, farmer export completed, an Admin deleted a Sub Admin from the web page, no errors in the logs.
- `docs/DATABASE.md` (Plan 20.2) already covers setup, SQLite and adding a migration.
