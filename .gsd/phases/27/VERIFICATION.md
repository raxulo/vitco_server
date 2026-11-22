# Phase 27 Verification: Realtime and Live Chat

**Date:** 2026-11-22 · **Branch:** `feature/support-foundation` (uncommitted, on top of Phase 26)

## Automated
| Check | Result |
|---|---|
| `tests/support` on SQLite | 200 passed |
| `tests/support` + `tests/test_schema_migrations.py` on PostgreSQL (pgserver) | 202 passed |
| Full suite on SQLite (without `large_import_throughput`) | 1273 passed, 1 failed (a test helper bug, fixed after the run began; the file then passed 28 of 28) |

## Real server + real Chrome (DevTools driven)
13 of 13 checks passed: Live badge, new ticket row without refresh (0.4 s), highlight, count, title and badge,
live requester message and internal note, typing indicator, badge off Live when the socket drops, missed event
replayed after reconnect (1.2 s), badge back to Live.

## Must-haves
- [x] Redis optional: unset, down or faked, the app and tickets keep working
- [x] Events published after commit, never for rolled-back work
- [x] Audience decided on the server from permission and team scope
- [x] Both sockets authenticate (cookie same-origin, or token within the timeout)
- [x] Reconnect with `last_event_id` replays; too old asks for a reload
- [x] Live badge, backoff, polling fallback
- [ ] Verified against a real Redis server (none available here)
- [ ] User visual sign-off
