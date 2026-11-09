---
phase: 8
plan: 1
status: complete
commit: pending phase commit after user approval
---

# Plan 8.1 Summary: Decouple Recycle Bin from Legacy Models

## What changed
- `app/modules/recyclebin/infrastructure/repository.py`: the marketplace model import is replaced by lightweight
  `sqlalchemy.table()` definitions of `animals`, `product_offers` and `marketplace_orders`. They reuse the UUID type
  of `users.id`. Each use first checks that the table exists, so fresh databases work too.
- `tests/test_recycle_bin.py`: two tests on the real SQLite test database. One covers legacy tables with restricted
  foreign keys, including rows of a surviving user. The other covers a database without legacy tables.
- `tests/conftest.py` (not in the plan): the database guard now requires the temporary test path. See the incident below.

## Evidence
- With the legacy deletes turned off through a pytest plugin, the test fails with
  `sqlite3.IntegrityError: FOREIGN KEY constraint failed`. With them on, it passes.
- The survivor's three legacy rows stay after the purge, and the impact count shows 2 (one animal, one offer).

## Incident during execution
The first version of that plugin imported `app` before `tests/conftest.py` set `DATABASE_URL`. A test run therefore
used the local development database, `storage/database/realtime_transfer.db`, and left two `Root` Super Admin rows
with `@test.local` emails. The old guard only checked that the URL started with `sqlite`, which the real database also does.

- Before the cleanup, the database was copied to the session scratchpad.
- The two rows were deleted by exact id and email. Only `admin@system.com` remains, `integrity_check` is ok and
  `foreign_key_check` is empty.
- The plugin now imports `app` after collection and asserts the temporary path.
- The guard in `tests/conftest.py` now fails unless the URL contains the temporary test path.
- The server database and `storage/backups/` were not involved.
