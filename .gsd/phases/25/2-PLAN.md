---
phase: 25
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/templates/layouts/support.html
  - app/web/templates/support/partials/sidebar.html
  - app/web/templates/support/partials/topbar.html
  - app/web/templates/support/components/*.html
  - app/web/static/css/support.css
  - app/web/static/js/support.js
  - app/web/support/router.py
  - app/web/support/controller.py
  - app/web/support/dependencies.py
  - app/web/router.py
  - app/web/auth/controller.py
  - app/middleware/authentication.py
  - app/web/middleware.py
  - tests/support/test_portal_shell.py
must_haves:
  - Support users land on /support after login and never see the dairy sidebar or pages
  - Non-support users cannot open /support (redirect or 403); support users cannot open dairy pages or dairy API
  - New layout, sidebar, topbar and component library follow docs/TECHNICAL_SUPPORT_PLAN.md section 10A
  - Sidebar shows only the menus the member has permission for
  - No change to app.min.css or the dairy layouts
gap_closure: false
---

# Plan 25.2: Portal shell, design system, login redirect and route isolation

## Objective
The professional, clean look of the support portal and its isolation from the dairy app (REQ-58, REQ-65, D-13).

## Context
- docs/TECHNICAL_SUPPORT_PLAN.md section 9 (menus) and 10A (UI standard)
- app/web/templates/layouts/dashboard.html, partials/sidebar.html (to see what NOT to reuse), app/web/auth/controller.py
  (role redirect around line 82), app/middleware/authentication.py, app/web/middleware.py, app/web/mount.py

## Tasks

<task type="auto">
  <name>Design system: css, layout and components</name>
  <files>support.css, layouts/support.html, support/components/*, support.js</files>
  <action>CSS tokens on `:root` (one indigo accent, neutral greys, semantic status colours, radius 10, 4/8 spacing,
  14px base, self-hosted font as the rest of the app, no CDN; NFR-18). All classes prefixed `sp-`. Components as Jinja
  macros: page header, stat card, data table + filter bar + pagination, status chip, priority dot, avatar with presence
  dot, empty state, skeleton, toast, confirm dialog, form field and section, tabs, live badge (static for now),
  chat bubble and timeline (markup only). Layout: fixed 248 px sidebar, topbar (title, search slot, live badge, bell,
  profile menu), content max-width 1280. Mobile: sidebar becomes a drawer, tables become card lists. Focus ring, AA
  contrast, `aria-live` region for toasts.
  AVOID: editing app.min.css or dairy templates; gradients, heavy animation, more than one accent colour.
  USE: a small `/support/_kit` page (Super Admin only, dev aid) that renders every component for visual review.</action>
  <verify>open /support/_kit at 1440, 1024, 768 and 390 px (headless Chrome screenshots, as in earlier phases);
  keyboard tab order check</verify>
  <done>Kit page shows every component in every state without console errors; the user signs off the look.</done>
</task>

<task type="auto">
  <name>Routes, redirect and isolation</name>
  <files>web/support/*, web/router.py, auth/controller.py, authentication.py, web/middleware.py</files>
  <action>Register `support_router` under `/support` (dashboard stub with welcome and the member's team). Login
  redirect: `Role.SUPPORT` goes to `/support`. `/` redirects support users to `/support`. A dependency
  `require_support_member` resolves `SupportContext` (from plan 25.1) and 403s otherwise; a middleware rule redirects
  support users away from every non-support web path and returns 403 on non-support API paths; non-support users
  hitting `/support` are redirected to their dashboard. Sidebar items come from one list with the permission each
  needs. Super Admin reaches the portal through a single new "Technical Support" entry in the dairy sidebar that
  opens `/support/teams` in the support layout.
  AVOID: adding /support to public routes; checking the role only in templates.</action>
  <verify>tests/support/test_portal_shell.py: login redirects per role; support user gets 403 / redirect on
  /dashboard, /mcc, /api/v1/collection; MCC user gets redirected from /support; sidebar menu per permission set</verify>
  <done>Isolation holds both ways; shell renders with the real sidebar for each template role.</done>
</task>

## Must-Haves
- [ ] Section 10A standard implemented as reusable macros
- [ ] Redirect and isolation tested for every role

## Success Criteria
- [ ] Visual sign-off from the user on /support/_kit
- [ ] No regressions in the existing suite
