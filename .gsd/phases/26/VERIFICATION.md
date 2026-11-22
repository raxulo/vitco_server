# Phase 26 Verification: Tickets Core and Mobile Ticket API

**Date:** 2026-11-22 · **Branch:** `feature/support-foundation` (on top of 058cf5a, uncommitted)

## Automated
| Check | Result |
|---|---|
| `tests/support` on SQLite | 167 passed |
| `tests/support` + `tests/test_schema_migrations.py` on PostgreSQL (pgserver) | 171 passed — migration 0006 matches the models |
| Full suite on SQLite, without the 100k-row `large_import_throughput` benchmark | 1243 passed, 0 failed |

## Screens (headless Chrome, 1440 px and 390 px inside an iframe)
List, ticket detail (manager, viewer, Super Admin on a pool ticket), categories. Fixed after review: role names
(MCC / VLCC), "1 messages", unread dot placement, "0 KB", date filter width.

## Not done in a real server run
`/verify` against a live server was not run; the tests drive the full middleware stack in-process.

## Must-haves
- [x] Only MCC, VLCC, Farmer, VLCC_FARMER use the requester API; others 403
- [x] Requester sees only own tickets and public messages; internal notes never leave the handler
- [x] Status flow enforced in the domain; every change is a timeline event
- [x] Routing by category team, else unassigned pool; manual assign inside the team
- [x] Attachments: image / PDF, 10 MB, private downloads
- [x] Queues, detail, composer, categories, permission-based controls
- [ ] User visual sign-off
- [ ] Manager-managed routing rules (REQ-66 wording) — Super Admin only for now
