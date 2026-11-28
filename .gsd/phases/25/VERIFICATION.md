# Phase 25 Verification: Support Foundation

**Date:** 2026-11-18 · **Branch:** `feature/technical-support` (from 8f542e5)

## Automated
| Check | Result |
|---|---|
| `tests/support` on SQLite | 60 passed |
| `tests/support` + `tests/test_schema_migrations.py` on PostgreSQL 16 (pgserver) | 64 passed — migration 0005 builds the same schema as the models, `role` enum has `SUPPORT` |
| Full suite on SQLite, without the 100k-row `large_import_throughput` benchmark | 1136 passed, 0 failed |

PostgreSQL found one bug that SQLite cannot show: `autocommit_block()` fails inside `SchemaMigrator`'s single
transaction. Fixed by running `ALTER TYPE role ADD VALUE IF NOT EXISTS 'SUPPORT'` in the transaction (PostgreSQL 12+).

Two existing tests changed with the new rule (support staff have no dairy menu):
`test_navigation_has_no_marketplace_link` skips `Role.SUPPORT`, plus new `test_support_staff_get_no_dairy_menu`.
The root page handler reads `role_type` defensively (a test stub user has none).

## Runtime (isolated server, SQLite in the scratchpad, port 5601)
Driven through the real web forms:
1. Super Admin signs in → creates "Technical Support - North" (+ Manager Nisha) and "Field Support - South".
2. Duplicate code → form re-rendered with "A support team with this code already exists." and input kept.
3. Manager signs in → lands on `/support` → creates Asha (Technical Support), Ravi (Ticket Assigner), Meera (Chat Agent),
   Kabir (Viewer).
4. Asha signs in → `/support`; `/dashboard` → 303 `/support`. Kabir (Viewer) gets the read-only dashboard.

Screenshots (headless Chrome, 1440 px and 390 px inside an iframe) reviewed: team list, team detail, team form and
its error, kit, manager / viewer dashboards, members list, member form, roles, role editor. Fixed after review:
link colour overriding buttons and nav items, hidden live badge showing, hamburger visible on desktop, "1 permissions".

## Must-haves
- [x] Role 8 added without touching 1 to 7
- [x] Only Super Admin creates teams; one Manager per team, created with it
- [x] Manager creates / edits / disables members in its own team only
- [x] Five templates seeded per team; permissions and team scope checked on the server
- [x] Every write audited in the same transaction
- [x] Support users land on `/support`, never see dairy pages or API; others cannot open `/support`
- [x] Design system as reusable macros, no change to `app.min.css` or dairy layouts
- [ ] User visual sign-off
