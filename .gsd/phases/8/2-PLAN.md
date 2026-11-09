---
phase: 8
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - app/api/v1/router.py
  - app/web/router.py
  - app/middleware/authentication.py
  - app/bootstrap/middleware.py
  - app/modules/dashboard/presentation/navigation.py
  - app/web/templates/layouts/dashboard.html
  - app/web/templates/partials/topbar.html
  - tests/test_marketplace_removal.py
files_deleted:
  - app/modules/marketplace/
  - app/web/marketplace/
  - app/web/templates/pages/marketplace/
  - app/web/templates/partials/cart_drawer.html
  - app/api/v1/routers/marketplace.py
  - app/api/v1/schemas/marketplace.py
  - app/web/static/uploads/marketplace/
  - app/web/static/js/marketplace/
  - scratch/migrate_marketplace_products.py
must_haves:
  - No marketplace route, menu item, cart button or module remains
  - Guests opening / reach /login; logged-in users reach /dashboard
  - Legacy database tables and rows are unchanged by startup
gap_closure: false
---

# Plan 8.2: Remove the Old Marketplace

## Objective
Delete the old marketplace completely so the new one starts clean, and keep every other part of the app
working (REQ-28). Legacy tables are not touched (DECISION-015).

## Context
- .gsd/phases/8/RESEARCH.md
- All files listed in the frontmatter

## Tasks

<task type="auto">
  <name>Unregister and delete the backend</name>
  <files>
    app/modules/configurator.py
    app/modules/dependencies.py
    app/api/v1/router.py
    app/web/router.py
    app/middleware/authentication.py
    app/bootstrap/middleware.py
    app/modules/dashboard/presentation/navigation.py
  </files>
  <action>
    Steps:
    1. Remove the repository registration, the `_marketplace` call and classmethod, and `GetHandler.marketplace_handler`.
    2. Remove the API and web router imports and includes.
    3. Change the `/` handler: logged-in users redirect to `/dashboard`, guests redirect to `/login`. Remove its
       query parameters and any imports left unused.
    4. Remove `/marketplace` and `/api/v1/marketplace` from `public_routes_startswith` and the four entries from
       `public_routes`. Keep `/` public.
    5. Remove the Marketplace `MenuGroup`. Keep `SUPER_ADMIN_ONLY`, which the Recycle Bin uses.
    6. Delete `app/modules/marketplace/`, `app/web/marketplace/`, `app/api/v1/routers/marketplace.py`,
       `app/api/v1/schemas/marketplace.py` and `scratch/migrate_marketplace_products.py`.

    AVOID: changing the `marketplace_orders` ALTER block in `sqlite.py`, because the legacy purge filters on that column.
    AVOID: compatibility stubs or alias modules, because the user wants the old code gone.
  </action>
  <verify>
    .venv\Scripts\python.exe -c "import app.modules.configurator, app.web.router, app.api.v1.router; print('imports ok')"
  </verify>
  <done>
    Imports succeed, and a search of `app/**/*.py` for `modules.marketplace`, `MarketplaceCommandHandler` and
    `marketplace_router` finds nothing.
  </done>
</task>

<task type="auto">
  <name>Remove pages, cart UI and demo assets</name>
  <files>
    app/web/templates/layouts/dashboard.html
    app/web/templates/partials/topbar.html
  </files>
  <action>
    Steps:
    1. Remove the cart button from `topbar.html` and the `cart_drawer.html` include from `dashboard.html`.
    2. Find which public routes still render `layouts/dashboard.html` for a guest. If none do, remove the guest
       navbar block and the guest-only inline styles. If any do, keep the navbar and remove only its cart and
       Marketplace links.
    3. Delete `pages/marketplace/`, `partials/cart_drawer.html`, `static/uploads/marketplace/` and `static/js/marketplace/`.
    4. Check templates and JS for `toggleCartDrawer`, `cart-badge-count` and `/marketplace`; remove what remains.
       The Recycle Bin's "Marketplace listings" label stays.

    AVOID: rebuilding `app.min.css`; leftover `.mp-*` rules are harmless and Phase 12 uses its own stylesheet.
  </action>
  <verify>
    Search `app/web` for `toggleCartDrawer`, `cart_drawer` and `/marketplace`; only the Recycle Bin label may refer to the marketplace.
  </verify>
  <done>
    The dashboard renders without template errors or browser console errors related to the cart.
  </done>
</task>

<task type="auto">
  <name>Lock the removal with tests and run everything</name>
  <files>
    tests/test_marketplace_removal.py
  </files>
  <action>
    Steps:
    1. Test: no registered route path of the real application contains `marketplace`.
    2. Test: a guest GET `/` returns 302 to `/login`, and a logged-in GET `/` returns 302 to `/dashboard`.
    3. Test: guests on an old URL such as `/marketplace/setup` get no store page, and `/api/v1/marketplace/orders` is not served.
    4. Test: `build_navigation` for every role contains no `/marketplace` link.
    5. Test: `importlib.util.find_spec("app.modules.marketplace")` is `None`.
    6. Test: rows in a legacy table survive a repeat `create_all`.
    7. Run the full suite and compare with the baseline in STATE history (304 passed, 2 pre-existing failures).
    8. Start the real app with the `/verify` flow on an isolated database copy. Check login, dashboard, sidebar
       and Recycle Bin in the running app.

    AVOID: treating any new failure as pre-existing without checking it against the parent commit.
  </action>
  <verify>
    .venv\Scripts\python.exe -m pytest -q
  </verify>
  <done>
    The new tests pass, the only failures are ones that also fail on commit `a345c6f`, and the runtime
    walkthrough is recorded in `.gsd/phases/8/VERIFICATION.md`.
  </done>
</task>

## Must-Haves
- [ ] No old marketplace code, route, menu, cart or demo image remains
- [ ] `/` redirects guests to `/login` and logged-in users to `/dashboard`
- [ ] Legacy tables and rows are unchanged
- [ ] All other pages keep working

## Success Criteria
- [ ] All tasks verified passing
- [ ] Must-haves confirmed
- [ ] No regressions in the full test suite
