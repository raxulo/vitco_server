# Phase 9 Verification: Marketplace Domain Foundation

**Date:** 2026-11-09
**Verdict:** Pass

## Test suite

Full suite without `test_large_import_throughput`: 385 passed, 1 failed. The failure is
`test_owner_options_super_admin`, which also fails on `a345c6f` (see Phase 8). The throughput test was excluded
because it takes about 2 minutes and already fails on this machine without any of this work; nothing in this phase
touches the import path.

Marketplace, Recycle Bin and removal tests: 86 passed.

## Negative proof

With `MarketplaceAccessScope` opened through a pytest plugin, 4 tests fail: seller sees only their own listings, another
seller's product and animal read as not found, and no viewer gets nothing. The temporary database was asserted first.

## Runtime check

Real server on an isolated database, started twice.

| Table | After first start | After second start |
|-------|-------------------|--------------------|
| `mkt_animal_types` | 4 | 4 |
| `mkt_animal_breeds` | 18 | 18 |
| `mkt_categories` | 4 | 4 |
| `mkt_home_sections` | 5 | 5 |
| `mkt_settings` | 1 | 1 |
| `mkt_products`, `mkt_animals`, `mkt_banners` | 0 | 0 |

`/healthz` returned 200 and `/` returned 302 on both starts, with no traceback in the logs. The development database
checksum did not change.

## Must-haves

- [x] Domain has no framework imports
- [x] 15 `mkt_` tables, no legacy name reused
- [x] Constraints enforced by the database, proven by tests
- [x] Seller scope proven with non-Super-Admin sellers
- [x] Seeder adds data once and removed masters stay removed, even when a whole table is emptied
- [x] Purge covers new tables without losing other users' history

## Limits

- REQ-47 stays In Progress. `SellerPolicy` exists and is tested, but no handler calls it until Phase 10.
- The `try/except` that keeps startup going when the seeder fails was reviewed, not exercised with a forced failure.
- On its next start, the local development database receives the starter data. That is the intended behaviour.
