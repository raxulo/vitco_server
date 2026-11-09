---
phase: 16
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/web/static/css/store.css
  - app/web/static/css/marketplace-admin.css
  - app/web/templates/layouts/store.html
  - app/web/templates/pages/store/home.html
  - app/web/templates/pages/store/_cards.html
  - app/web/templates/pages/marketplace_admin/_shell.html
  - app/web/templates/pages/marketplace_admin/overview.html
  - app/web/marketplace_admin/router.py
  - app/web/marketplace_admin/controller.py
  - app/modules/marketplace/application/handler.py
  - app/modules/marketplace/domain/irepository.py
  - app/modules/marketplace/infrastructure/repository.py
  - tests/marketplace/test_control_center_web.py
must_haves:
  - Control Center uses the same blue accent as the rest of the app
  - Sections are grouped, and Orders and Enquiries show their new counts on every page
  - Overview puts work first and shows the latest orders
  - Store is clean and neutral, with real category icons and honest trust points
  - No new axe violations, no sideways scroll from 360 px, every existing test passes
gap_closure: false
---

# Plan 16.1: Control Center & Store Visual Refresh

## Objective
The user asked for a more professional, modern look for both the Control Center and the store (NFR-15). Behaviour and URLs don't change.

## Tasks

<task type="auto">
  <name>Control Center</name>
  <files>_shell.html, overview.html, marketplace-admin.css, router.py, controller.py</files>
  <action>
    A header card with grouped tabs, icons and new counts. Overview: work first, latest orders, low stock, quick actions. Quieter tables and buttons.

    AVOID: a second sidebar, because it would squeeze tables beside the app's own sidebar.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_control_center_web.py -q</verify>
  <done>Counts respect the seller's scope and appear on every page.</done>
</task>

<task type="auto">
  <name>Store</name>
  <files>store.css, home.html, _cards.html</files>
  <action>
    Neutral white canvas, one green accent, calmer type, borderless cards, icon category tiles, trust row.

    AVOID: trust claims the store can't back, such as "certified" or "best price".
  </action>
  <verify>Screenshots at 1440, 768, 390 and 360 px; axe-core run</verify>
  <done>Reviewed in real Chrome on an isolated database.</done>
</task>

## Success Criteria
- [ ] Full test suite has no new failures
- [ ] axe-core clean on store and Control Center pages
