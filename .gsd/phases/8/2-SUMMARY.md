---
phase: 8
plan: 2
status: complete
commit: pending phase commit after user approval
---

# Plan 8.2 Summary: Remove the Old Marketplace

## Deleted
- `app/modules/marketplace/`, `app/web/marketplace/`, `app/web/templates/pages/marketplace/`
- `app/api/v1/routers/marketplace.py`, `app/api/v1/schemas/marketplace.py`
- `app/web/templates/partials/cart_drawer.html`
- `app/web/static/uploads/marketplace/` (19 tracked demo images), `app/web/static/js/marketplace/` (empty)
- `scratch/migrate_marketplace_products.py`

## Changed
- Dependency injection and routers: `configurator.py`, `dependencies.py`, `api/v1/router.py`, `web/router.py`.
- `/` now redirects logged-in users to `/dashboard` and guests to `/login`.
- `/marketplace` and `/api/v1/marketplace` are no longer public routes (`authentication.py`, `bootstrap/middleware.py`).
- The Marketplace menu group, the topbar cart button and the cart include are gone.
- `layouts/dashboard.html`: the guest navbar and guest-only inline styles are gone. Only the old marketplace
  rendered this layout for guests; error and login pages do not extend it, and all other pages are protected.

## Kept on purpose
- The `marketplace_orders.buyer_id` ALTER block in `sqlite.py`, because the legacy purge filters on that column.
- The Recycle Bin `marketplace_listings` count and label; Phase 9 extends them to the new tables.
- Leftover `.mp-*` rules in `app.min.css`; they are harmless and Phase 12 has its own stylesheet.

## Tests
`tests/test_marketplace_removal.py`. Its route test first asserted that the walk really saw routes. That assertion
caught `app.routes` not listing included routers on this FastAPI version, so the test now reads the OpenAPI paths.
Direct requests to the old URLs cover routes that may be hidden from the schema.
