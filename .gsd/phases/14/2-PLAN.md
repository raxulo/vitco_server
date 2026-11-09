---
phase: 14
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/storefront/cart_cookie.py
  - app/web/storefront/cart_controller.py
  - app/web/storefront/router.py
  - app/web/mount.py
  - app/modules/marketplace/presentation/requests.py
  - app/web/templates/layouts/store.html
  - app/web/templates/pages/store/
  - app/web/static/css/store.css
  - app/web/static/js/store.js
  - app/web/marketplace_admin/order_controller.py
  - app/web/marketplace_admin/router.py
  - app/web/templates/pages/marketplace_admin/
  - tests/marketplace/test_checkout_web.py
must_haves:
  - A guest can go from product page to placed order to tracking
  - The cart works without JavaScript
  - Sellers can run an order from placed to delivered or cancelled
gap_closure: false
---

# Plan 14.2: Cart, Checkout & Orders Pages

## Objective
Build the buying flow for customers and the orders screen for sellers (REQ-36, REQ-43 to REQ-45, NFR-15).

## Context
- .gsd/phases/14/RESEARCH.md
- .gsd/phases/14/1-PLAN.md

## Tasks

<task type="auto">
  <name>Customer pages</name>
  <files>
    app/web/storefront/
    app/web/templates/pages/store/
    app/web/templates/layouts/store.html
    app/web/static/css/store.css
    app/web/static/js/store.js
  </files>
  <action>
    Add to cart and Buy now on the product page; cart icon with count; cart page; checkout; order placed; tracking.

    AVOID: phone numbers in URLs, because URLs end up in logs and browser history.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_checkout_web.py -q</verify>
  <done>Tests through the real app, including a tampered cookie, a double submit and parallel orders over HTTP.</done>
</task>

<task type="auto">
  <name>Seller orders screen</name>
  <files>
    app/web/marketplace_admin/order_controller.py
    app/web/marketplace_admin/router.py
    app/web/templates/pages/marketplace_admin/
  </files>
  <action>Orders tab with status filter and search; order detail with items, buyer, address, totals, next-step buttons and cancel with a reason. The overview tile links to it.</action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace -q</verify>
  <done>Only allowed next steps appear; other roles get 403.</done>
</task>

<task type="auto">
  <name>Browser walkthrough</name>
  <files>.gsd/phases/14/VERIFICATION.md</files>
  <action>Real Chrome: product, cart, checkout, order placed, track, seller delivers. Screenshots at several widths. Full suite.</action>
  <verify>.venv\Scripts\python.exe -m pytest -q</verify>
  <done>No overflow, no console errors, no new test failures, results recorded.</done>
</task>

## Must-Haves
- [ ] End-to-end guest purchase works
- [ ] Works without JavaScript
- [ ] Seller flow complete

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in the full test suite
