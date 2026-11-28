# Phase 29 Verification: Calls, Audit Views and My Activity

**Date:** 2026-11-22 · **Branch:** `feature/support-foundation` (uncommitted, on top of Phase 28)

## Automated
| Check | Result |
|---|---|
| `tests/support` + `tests/notification` + `tests/test_recycle_bin.py` + `tests/test_schema_migrations.py` on SQLite | 286 passed, 2 skipped (rollback tests, SQLite savepoint issue) |
| Same on PostgreSQL (pgserver) | 287 passed, 1 skipped (SQLite-only legacy test) — migration 0008 matches the models; date maths verified on both |
| Full suite on SQLite (without `large_import_throughput`) | 1338 passed, 2 skipped, 1 deselected (6 min 49 s) |

## Screens (headless Chrome, 1440 px and 390 px in an iframe)
My activity, team activity, audit log, ticket detail with the call prompt and history, home. Fixed after review:
stat cards two per row on phones.

## Not verified
- Dialling from a real phone (`tel:`).

## Must-haves
- [x] Number visible to every member; Call button only with `support.call.make` (Viewer and Chat Agent: none)
- [x] Call records intent, then outcome and note; events in the timeline and audit log
- [x] My Activity by period, cards by role, day-wise trend; Viewer gets an empty state
- [x] Manager sees each member and the team table; Super Admin all teams; members only themselves
- [x] Audit screen with filters for Manager and Super Admin only, read-only
- [x] Numbers from aggregate queries only
- [ ] User visual sign-off
