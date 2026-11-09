# Phase 8 Verification: Legacy Marketplace Removal

**Date:** 2026-11-09
**Verdict:** Pass

## Test suite

| Run | Result |
|-----|--------|
| Current branch, full | 336 passed + 2 failed (`test_large_import_throughput[100000]`, `test_owner_options_super_admin`) |
| Current branch, excluding throughput | 336 passed, 1 failed |
| `a345c6f` (before Phase 8), excluding throughput | 316 passed, 1 failed (the same test) |
| Throughput test alone | Fails on both: about 876 rows/s here, about 815 rows/s on `a345c6f`, limit 1000 |

Both failures exist without Phase 8. `test_owner_options_super_admin` fails only in a full run, because the
owner list in the shared test database grows past what the endpoint returns. Neither was changed by this phase.

## Runtime check

Real server on an isolated database, with a `marketplace_banners` row added before startup.

| Check | Result |
|-------|--------|
| Guest `/` | 302 to `/login` |
| Guest `/marketplace`, `/marketplace/setup` | 303 to `/login` |
| Guest `/api/v1/marketplace/orders` | 401 |
| Super Admin login, `/` | 302 to `/dashboard` |
| Dashboard | 200; no cart, `/marketplace` link or guest navbar; Recycle Bin in the sidebar |
| `/recycle-bin` | 200 |
| Logged-in old URLs | 404 |
| Old demo image | 404 |
| Legacy row after startup | Kept unchanged |
| Legacy tables recreated by startup | None |

## Must-haves

- [x] No old marketplace code, route, menu, cart or demo image remains
- [x] `/` redirects guests to `/login` and logged-in users to `/dashboard`
- [x] Legacy tables and rows are unchanged
- [x] Purge removes legacy rows of the tree; survivors' rows stay; absent tables are handled
- [x] Disabling the legacy purge makes the test fail with `FOREIGN KEY constraint failed`

## Not checked

- Visual check and console errors in a real browser. Checks were done on server responses and HTML.
- The server database and whether a mobile app calls the old API (STATE concern, Phase 15).

## Issue during execution

A test probe wrote two test users to the local development database. They were removed and the test guard was
tightened. Details are in [1-SUMMARY.md](1-SUMMARY.md).
