---
phase: 8
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/recyclebin/infrastructure/repository.py
  - tests/test_recycle_bin.py
must_haves:
  - The recycle bin repository imports nothing from app.modules.marketplace
  - Purging a user who owns legacy animal, offer or order rows succeeds and removes those rows
  - Purge and impact work when the legacy tables do not exist
gap_closure: false
---

# Plan 8.1: Decouple Recycle Bin from Legacy Models

## Objective
Make the Recycle Bin independent of the old marketplace models before they are deleted. Legacy tables stay
in existing databases with `ON DELETE RESTRICT` foreign keys to `users`, so without this plan a permanent
delete would fail on any database that holds legacy rows (REQ-29, DECISION-015).

## Context
- .gsd/phases/8/RESEARCH.md
- .gsd/DECISIONS.md (DECISION-013, DECISION-015)
- app/modules/recyclebin/infrastructure/repository.py
- tests/test_recycle_bin.py
- app/core/database/drivers/sqlite.py

## Tasks

<task type="auto">
  <name>Replace legacy model use with guarded Core table definitions</name>
  <files>
    app/modules/recyclebin/infrastructure/repository.py
  </files>
  <action>
    Steps:
    1. Remove the `app.modules.marketplace.infrastructure.models` import.
    2. Add module-level `sqlalchemy.table()` definitions, with a short comment citing DECISION-015:
       - `animals` (`id`, `seller_user_id`)
       - `product_offers` (`id`, `seller_user_id`)
       - `marketplace_orders` (`id`, `buyer_id`)
    3. Add a private helper that returns the existing table names by calling
       `sqlalchemy.inspect` through `session.run_sync`.
    4. In the impact query, count legacy animals and offers only when the table exists.
    5. In `purge`, delete from each legacy table only when it exists, reusing `_delete_in` if it accepts Core
       tables; otherwise add a small `_delete_legacy` helper with the same batching behaviour.
    6. Keep the purge order: these deletes must still run before the users are deleted.

    AVOID: raw SQL strings built from values, because bound Core statements already handle this safely.
    AVOID: dropping or altering any legacy table, because DECISION-015 keeps them untouched.
    USE: the dialect-neutral inspector, because the code supports SQLite and PostgreSQL drivers.
  </action>
  <verify>
    .venv\Scripts\python.exe -m pytest tests/test_recycle_bin.py -q
  </verify>
  <done>
    `app.modules.marketplace` no longer appears in the repository, and existing recycle bin tests pass.
  </done>
</task>

<task type="auto">
  <name>Prove purge against real legacy rows and absent tables</name>
  <files>
    tests/test_recycle_bin.py
  </files>
  <action>
    Steps:
    1. Add a fixture that creates the three legacy tables with raw DDL on the real test database, including
       `REFERENCES users(id) ON DELETE RESTRICT`, and drops them in teardown. The session-scoped database must
       not keep them for other tests.
    2. Test: a soft-deleted user owns one row in each legacy table. The impact count includes the animal and
       offer, the purge succeeds, and those rows are gone.
    3. Test: a row owned by a surviving user stays after the purge.
    4. Test: with no legacy tables, the impact count is 0 and the purge succeeds.
    5. Run test 2 once with the legacy deletes temporarily disabled, confirm it fails with a foreign key error,
       then restore them. Record the result in the plan summary.

    AVOID: mocks, because the foreign key behaviour is the thing under test.
  </action>
  <verify>
    .venv\Scripts\python.exe -m pytest tests/test_recycle_bin.py -q
  </verify>
  <done>
    The new tests pass, including the survivor and absent-table cases, and the summary records that test 2
    fails with a foreign key error when the legacy deletes are disabled.
  </done>
</task>

## Must-Haves
- [ ] No import from `app.modules.marketplace` in the recycle bin module
- [ ] Legacy rows of a purged user are removed; other users' rows stay
- [ ] Works with and without the legacy tables

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] No regressions in `tests/test_recycle_bin.py`
