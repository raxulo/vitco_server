---
phase: 13
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/storefront/controller.py
  - app/web/storefront/router.py
  - app/modules/marketplace/presentation/requests.py
  - app/web/templates/pages/store/
  - app/web/static/css/store.css
  - app/web/static/js/store.js
  - app/web/marketplace_admin/controller.py
  - app/web/marketplace_admin/router.py
  - app/web/templates/pages/marketplace_admin/enquiries.html
  - app/web/templates/pages/marketplace_admin/_shell.html
  - app/web/templates/pages/marketplace_admin/overview.html
  - tests/marketplace/test_browse_web.py
must_haves:
  - No store link from the home page leads to a 404
  - Bad query values never produce an error page
  - Animals have no cart; Call, WhatsApp and enquiry work
gap_closure: false
---

# Plan 13.2: Store Pages & Enquiry Inbox

## Objective
Build the pages customers browse and the inbox sellers work from (REQ-36, REQ-38 to REQ-42, NFR-15).

## Context
- .gsd/phases/13/1-PLAN.md
- app/web/templates/layouts/store.html

## Tasks

<task type="auto">
  <name>Store pages</name>
  <files>
    app/web/storefront/
    app/web/templates/pages/store/
    app/web/static/css/store.css
    app/web/static/js/store.js
  </files>
  <action>
    Listing pages with filters (collapsed on phones), sort, pagination, active filter clear, empty state. Product detail with gallery and
    size picker. Animal detail with gallery, spec table, contact box and enquiry form. Search, policy pages and a store 404.

    AVOID: strict typed query parameters on public pages, because a shared or edited URL should still open.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_browse_web.py -q</verify>
  <done>Every link on the home page opens; junk parameters return 200; invalid enquiry returns 422 with values kept.</done>
</task>

<task type="auto">
  <name>Enquiry inbox</name>
  <files>
    app/web/marketplace_admin/
    app/web/templates/pages/marketplace_admin/
    tests/marketplace/test_browse_web.py
  </files>
  <action>Enquiries tab with status filter, one-tap Call and WhatsApp, status and notes. The overview tile links to it.</action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace -q</verify>
  <done>A customer's enquiry appears in the inbox and can be worked to closed.</done>
</task>

<task type="auto">
  <name>Browser walkthrough</name>
  <files>.gsd/phases/13/VERIFICATION.md</files>
  <action>Real Chrome at several widths: browse, filter, open details, switch size and gallery image, send an enquiry. Review screenshots. Full suite.</action>
  <verify>.venv\Scripts\python.exe -m pytest -q</verify>
  <done>No overflow, no console errors, no new test failures, results recorded.</done>
</task>

## Must-Haves
- [ ] All home links work
- [ ] Junk URLs are safe
- [ ] Enquiry flow works end to end

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in the full test suite
