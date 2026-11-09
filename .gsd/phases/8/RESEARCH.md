# Phase 8 Research: Legacy Marketplace Removal

**Discovery level:** 0 (internal removal, no new dependencies)
**Date:** 2026-11-08

## What exists

| Area | Paths | Size |
|------|-------|------|
| Module | `app/modules/marketplace/` | about 2,065 lines |
| Web | `app/web/marketplace/` | 522 lines |
| Pages | `app/web/templates/pages/marketplace/` | 2,713 lines |
| API | `app/api/v1/routers/marketplace.py`, `app/api/v1/schemas/marketplace.py` | 25 endpoints |
| Cart | `app/web/templates/partials/cart_drawer.html` | global, posts to `/marketplace/order/create` |
| Demo images | `app/web/static/uploads/marketplace/` | 19 tracked PNG files |
| Other | `app/web/static/js/marketplace/` (empty), `scratch/migrate_marketplace_products.py` | |

No test references the marketplace.

## Coupling that must be cut

| File | Coupling |
|------|----------|
| `app/modules/configurator.py` | repo registration (~208), `_marketplace` call (~255), classmethod (~327) |
| `app/modules/dependencies.py` | `marketplace_handler` (~179) |
| `app/api/v1/router.py` | import (17), include (39) |
| `app/web/router.py` | imports (33-34), guest `/` renders the store (46-56), include (85) |
| `app/middleware/authentication.py` | public prefixes (104) |
| `app/bootstrap/middleware.py` | public routes (135-138) |
| `app/modules/dashboard/presentation/navigation.py` | Marketplace menu group (287-306) |
| `app/web/templates/layouts/dashboard.html` | guest navbar with cart and store link (7-53), cart include (83) |
| `app/web/templates/partials/topbar.html` | cart button (27-31) |
| `app/modules/recyclebin/infrastructure/repository.py` | imports legacy models (37-41), impact count (292-293), purge (317-319) |

## Main risk: Recycle Bin purge

`AnimalModel`, `ProductOfferModel` and `MarketplaceOrderModel` have foreign keys to `users.id` with
`ON DELETE RESTRICT`. `app/core/database/drivers/sqlite.py:112` sets `PRAGMA foreign_keys=ON`.

If the models and these purge lines were simply removed, purging a user who owns a legacy row would fail
with a foreign key error on any database that still has those rows. `create_all` also will not create
these tables on a fresh install, so the purge cannot assume they exist.

**Approach:** lightweight `sqlalchemy.table()` definitions inside the recycle bin repository, plus a table
existence check through `inspect`. `product_inventory` is removed by its own `ON DELETE CASCADE` from `product_offers`.

## Keep unchanged

- The `marketplace_orders.buyer_id` ALTER block in `app/core/database/drivers/sqlite.py:74-81`. The legacy purge filters on this column.
- The `marketplace_listings` impact field and its confirm-dialog label. They remain accurate for legacy rows, and Phase 9 extends them to the new tables.
- `MediaCategory` values, used by the new module.
- The `/` public route, needed so guests can be redirected.

## Behaviour between Phase 8 and Phase 12

Guests opening `/` are redirected to `/login`. Logged-in users still go to `/dashboard`. Marketplace routes
are unregistered and their public prefixes removed, so guests hitting old URLs follow the normal
unauthenticated flow. Phase 12 adds the public prefix back for the new store.

## Data check

Read-only row counts on `storage/database/realtime_transfer.db` and `storage/backups/realtime_transfer.db`
on 2026-11-08: all 11 legacy tables are empty. The server database was not available to check.
