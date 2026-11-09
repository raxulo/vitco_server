---
phase: 11
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/marketplace_admin/router.py
  - app/web/marketplace_admin/merchandising_controller.py
  - app/modules/marketplace/presentation/requests.py
  - app/web/templates/pages/marketplace_admin/_shell.html
  - app/web/templates/pages/marketplace_admin/banners.html
  - app/web/templates/pages/marketplace_admin/home_page.html
  - app/web/templates/pages/marketplace_admin/settings.html
  - app/web/static/css/marketplace-admin.css
  - tests/marketplace/test_merchandising_web.py
must_haves:
  - Super Admin manages banners, home page and settings from the panel
  - Each banner shows whether it is live, scheduled, expired or off
gap_closure: false
---

# Plan 11.2: Merchandising Pages

## Objective
Add Banners, Home page and Store settings sections to the Control Center (REQ-34, REQ-35, NFR-15).

## Context
- .gsd/phases/11/1-PLAN.md
- app/web/marketplace_admin/controller.py

## Tasks

<task type="auto">
  <name>Pages and tests</name>
  <files>
    app/web/marketplace_admin/merchandising_controller.py
    app/web/marketplace_admin/router.py
    app/modules/marketplace/presentation/requests.py
    app/web/templates/pages/marketplace_admin/
    tests/marketplace/test_merchandising_web.py
  </files>
  <action>
    Banners: list with state and thumbnail, side form with image, mobile image, link, window, order. Home page: ordered sections
    with up and down, inline edit, add a category section; trending tags. Settings: grouped form for brand, contact, delivery,
    payment, store status and policies.

    AVOID: per-page style blocks, because one stylesheet keeps the panel consistent.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace -q</verify>
  <done>Through the real app: every role other than Super Admin gets 403; invalid input returns 422 with typed values kept; a reloaded page shows saved values.</done>
</task>

<task type="auto">
  <name>Browser check</name>
  <files>.gsd/phases/11/VERIFICATION.md</files>
  <action>Screenshots at 1440, 1200 and 390 px, reviewed by eye. Overflow check. Full suite.</action>
  <verify>.venv\Scripts\python.exe -m pytest -q</verify>
  <done>No overflow, no new test failures, results recorded.</done>
</task>

## Must-Haves
- [ ] Panel covers REQ-34 and REQ-35
- [ ] States are visible on each banner

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in the full test suite
