# Plan 25.2 Summary: Portal shell, design system, login redirect and route isolation

**Status:** ✅ Complete (2026-11-18), visual sign-off by the user pending

## What was built
- Design system `app/web/static/css/support.css` (every class `sp-`; one indigo accent, neutral greys, semantic chips,
  4 / 8 spacing, 10 px radius, Inter self-hosted, card-list tables and drawer sidebar under 900 px, reduced motion).
- `app/web/static/js/support.js`: toasts, `data-confirm` dialog, `data-copy`, profile menu, sidebar drawer, HTMX
  error toasts.
- `layouts/support.html` (stand-alone: no `app.min.css`, no dairy sidebar), `support/partials/sidebar.html`,
  `topbar.html`, `notice.html`, macros `support/components/ui.html`.
- `app/web/support/`: `navigation.py` (one list, permission per entry, `team_scoped` entries hidden for Super
  Admin), `portal.py` (`SupportPortal.page` builds the `sp` page model from the server-side context), `controller.py`
  (`/support` home, `/support/_kit` design kit for Super Admin), `router.py`.
- Login: web login sends `Role.SUPPORT` to `/support`; `/` does the same; `Role.SUPPORT` added to the mobile API's
  blocked roles.
- Isolation in `AuthenticationMiddleware._support_isolation`: a support user may only use `/support`,
  `/api/v1/support`, `/ws/support`, `/login`, `/auth/login`, `/logout` (web → redirect `/support`, API → 403
  `SUPPORT_ACCESS_ONLY`); anyone but Super Admin is sent away from `/support` (web → `/`, API → 403).
  `/api/v1/support` stays open to other roles: the requester API of Phase 26 lives there.

## Notes
- The live badge is in the topbar but hidden until Phase 27.
- Found while testing: the shared test client keeps cookies, and the middleware reads the cookie before the header,
  so the web-login test now clears cookies.

## Tests
`tests/support/test_portal_shell.py` — 22 tests.
