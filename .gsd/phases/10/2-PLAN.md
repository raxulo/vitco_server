---
phase: 10
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/framework/formatting.py
  - app/web/mount.py
  - app/web/router.py
  - app/web/marketplace_admin/__init__.py
  - app/web/marketplace_admin/router.py
  - app/web/marketplace_admin/controller.py
  - app/modules/marketplace/presentation/__init__.py
  - app/modules/marketplace/presentation/requests.py
  - app/modules/dashboard/presentation/navigation.py
  - app/web/static/css/marketplace-admin.css
  - app/web/static/js/marketplace-admin.js
  - app/web/templates/pages/marketplace_admin/
  - tests/marketplace/test_control_center_web.py
  - tests/test_marketplace_removal.py
must_haves:
  - Only sellers reach the panel; only Super Admin reaches masters
  - Validation errors keep the entered values and name the field
  - The panel is usable on a phone and by keyboard
gap_closure: false
---

# Plan 10.2: Control Center Pages

## Objective
Give the Super Admin a clean, complete panel for the catalog: overview, products, animals, categories and animal masters (REQ-30 to REQ-33, NFR-15, NFR-17).

## Context
- .gsd/phases/10/RESEARCH.md
- .gsd/phases/10/1-PLAN.md
- app/web/recycle_bin/

## Tasks

<task type="auto">
  <name>Shell, overview and masters</name>
  <files>
    app/web/marketplace_admin/
    app/web/templates/pages/marketplace_admin/
    app/web/static/css/marketplace-admin.css
    app/web/static/js/marketplace-admin.js
    app/modules/dashboard/presentation/navigation.py
    app/web/framework/formatting.py
    app/web/mount.py
  </files>
  <action>
    1. Sidebar group "Marketplace" with "Control Center", for seller roles only.
    2. Shared shell with section tabs and one design-token stylesheet.
    3. Overview tiles, low stock list and quick actions. Tiles with zero show the zero, not a blank.
    4. Categories and animal types with breeds: list, add, edit, image, order, active, guarded delete.
    5. `inr` Jinja filter with Indian digit grouping.

    AVOID: inline styles and per-page style blocks, because one stylesheet keeps the panel consistent.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_control_center_web.py -q -k "access or overview or master"</verify>
  <done>Guest goes to `/login`; Admin, VLCC and Farmer get 403; Super Admin sees real counts; refused delete shows the reason on the page.</done>
</task>

<task type="auto">
  <name>Product and animal forms</name>
  <files>
    app/web/marketplace_admin/controller.py
    app/modules/marketplace/presentation/requests.py
    app/web/templates/pages/marketplace_admin/
    app/web/static/js/marketplace-admin.js
    tests/marketplace/test_control_center_web.py
    tests/test_marketplace_removal.py
  </files>
  <action>
    1. Lists with search, status filter and pagination; mobile card layout.
    2. Product form: details, variants table, specifications, gallery with add, remove and reorder, status, flags.
    3. Animal form: type and dependent breed, price and negotiable, age, lactation, milk litres per day, FAT, pregnancy,
       calf, health, vaccination, location, description, gallery, status, flags.
    4. Narrow `tests/test_marketplace_removal.py` to old URLs, since a new Control Center link now exists.
    5. Runtime walkthrough with a real browser screenshot at desktop and phone width.

    AVOID: losing typed values or chosen files silently on a validation error; tell the user that files must be re-selected.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace tests/test_marketplace_removal.py tests/test_recycle_bin.py -q</verify>
  <done>
    Through the real app: create, edit, publish and delete a product and an animal with images; invalid input returns 422 with
    field messages and the entered values; screenshots reviewed. Recorded in `.gsd/phases/10/VERIFICATION.md`.
  </done>
</task>

## Must-Haves
- [ ] Server-side access rules, tested with several roles
- [ ] Full create, edit, publish and delete through the real app
- [ ] Responsive and keyboard usable

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in the full test suite
