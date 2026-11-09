---
phase: 9
plan: 2
status: complete
commit: pending phase commit after user approval
---

# Plan 9.2 Summary: Catalog Repository, Seller Scope, Seed & Recycle Bin

- Entities, `IMarketplaceRepository`, mapper and `MarketplaceRepository` with `MarketplaceAccessScope`. Domain uses a
  small `ListingViewer` protocol, so it does not import the auth middleware.
- Updating a product keeps existing variant ids, so order lines stay linked to variants that remain.
- `MarketplaceSeeder` runs from `lifespan.py` and adds masters, default home sections and settings.
- Recycle Bin deletes the new listings of a purged tree. Order lines and enquiries keep their snapshots with NULL links.
- `tests/test_marketplace_removal.py` now checks for legacy table models, since `app.modules.marketplace` exists again.

## Deviation from the plan

The plan seeded each table when it was empty. That would recreate categories if the Super Admin removed them all, so the
seeder now stops once the settings row exists. RESEARCH.md and the plan were updated.

## Later phases must update

`tests/test_marketplace_removal.py` asserts no `marketplace` route or `href="/marketplace` exists. Phases 10, 12 and 15
add new routes and links, and must narrow those tests to the old URLs at that point.
