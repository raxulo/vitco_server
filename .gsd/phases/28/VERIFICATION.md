# Phase 28 Verification: Push Notification Backend

**Date:** 2026-11-22 · **Branch:** `feature/support-foundation` (uncommitted, on top of Phase 27)

## Automated
| Check | Result |
|---|---|
| `tests/notification` + `tests/support` + `tests/test_schema_migrations.py` on SQLite | 237 passed, 2 skipped (rollback tests: SQLite savepoint issue, pre-existing) |
| Same + `tests/test_recycle_bin.py` on PostgreSQL (pgserver) | 259 passed, 1 skipped (a SQLite-only legacy test) — migration 0007 matches the models, outbox rolls back with the change |
| Full suite on SQLite (without `large_import_throughput`) | 1310 passed, 2 skipped, 0 failed |

## Not verified
- A real Firebase project: the sender was tested against a fake Google endpoint that checks the signed JWT and the
  v1 message. The first real send needs the service-account JSON (setup in 1-SUMMARY.md).
- The mobile app side (registration, display, tap to open) is later work by design.

## Must-haves
- [x] Shared module for every feature (DECISION-034); support is one user of it
- [x] POST and DELETE devices (`/api/v1/notifications/devices`); many devices per user
- [x] Outbox rows written in the same transaction as the ticket change (PostgreSQL)
- [x] Background sender with retry and dead-token removal
- [x] Online users skipped when the notification asks for it (`skip_if_online`)
- [x] Without credentials: disabled, logs only, nothing else affected
- [x] Credential from environment or a file path, never the repository
- [x] Firebase setup note in the summary
