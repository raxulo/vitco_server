---
phase: 12
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/templates/layouts/store.html
  - app/web/templates/pages/store/
  - app/web/static/css/store.css
  - app/web/static/js/store.js
  - app/web/storefront/
  - app/web/router.py
  - app/web/framework/formatting.py
  - app/web/mount.py
  - app/middleware/authentication.py
  - app/bootstrap/middleware.py
  - app/modules/dashboard/presentation/navigation.py
  - tests/marketplace/test_storefront_web.py
  - tests/test_marketplace_removal.py
must_haves:
  - The store has its own look, with no dashboard shell
  - Guests can open it without login; the Control Center stays protected
  - The user approves the visual direction before Phase 13
gap_closure: false
---

# Plan 12.2: Design System & Home Page

## Objective
Build the customer-facing look and the home page, and get the user's approval on a real page (REQ-37, NFR-15, NFR-18, DECISION-020).

## Context
- .gsd/phases/12/1-PLAN.md
- .gsd/DECISIONS.md (DECISION-019, DECISION-020)

## Design direction

Warm cream canvas, deep forest green, ghee gold as an accent on surfaces, clay for discounts. Outfit for headings and Inter for
text, both already self-hosted. Two large doors on the home page, Animals and Dairy products, because the store sells two
different things. The animal card's signature is a spec strip showing milk per day, lactation and age at a glance.

## Tasks

<task type="auto">
  <name>Layout, tokens and home page</name>
  <files>
    app/web/templates/layouts/store.html
    app/web/templates/pages/store/
    app/web/static/css/store.css
    app/web/static/js/store.js
    app/web/storefront/
  </files>
  <action>
    Standalone layout with skip link, header, search, trending links, footer with contact and policies. Home page: banner carousel
    or a text hero when there are no banners, two doors, then sections in Control Center order. Carousel respects reduced motion
    and can be used by keyboard. Self-hosted assets only.

    AVOID: extending the dashboard layout, because customers should not see the admin shell.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_storefront_web.py -q</verify>
  <done>Guest gets 200 at `/marketplace`, with and without any content; only self-hosted assets are referenced.</done>
</task>

<task type="auto">
  <name>Public access and links</name>
  <files>
    app/middleware/authentication.py
    app/bootstrap/middleware.py
    app/web/router.py
    app/modules/dashboard/presentation/navigation.py
    tests/test_marketplace_removal.py
  </files>
  <action>
    `/marketplace` becomes public; `/` sends guests there. Add "Visit store" to the staff sidebar. Narrow the removal tests to old URLs.

    AVOID: making `/admin` or `/api/v1/marketplace` public, because DECISION-019 keeps them apart.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/test_marketplace_removal.py tests/marketplace -q</verify>
  <done>Guest `/` goes to `/marketplace`; `/admin/marketplace` still requires login.</done>
</task>

<task type="checkpoint:human-verify">
  <name>Design approval</name>
  <files>.gsd/phases/12/VERIFICATION.md</files>
  <action>Show the user the real page at desktop and phone width and wait for approval or changes.</action>
  <verify>User response</verify>
  <done>User has approved the direction. Phase 13 does not start before this.</done>
</task>

## Must-Haves
- [ ] Standalone design, public, self-hosted
- [ ] Responsive with no overflow at 1440, 1024, 768 and 390 px
- [ ] User approval recorded

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in the full test suite
