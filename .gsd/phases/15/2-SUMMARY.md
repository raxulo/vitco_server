---
phase: 15
plan: 2
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 15.2 Summary: SEO, Audits & Release

- Canonical links, Open Graph tags and JSON-LD on product and animal pages. `robots.txt` and `sitemap.xml` with live listings only.
- Cart, checkout, tracking, search, order placed, 404 and 429 pages are `noindex`.
- `MARKETPLACE_PUBLIC_URL` sets the address used in those links.
- axe-core findings fixed on the store and Control Center: contrast, landmarks, heading order, table headers, focus ring on the search box.
- Measured results are in [VERIFICATION.md](VERIFICATION.md). Server tasks are in [RELEASE.md](RELEASE.md).

## Changes outside the plan

- **`app/core/logging/manager.py` (security, whole app):** `sqlalchemy.engine` was always at INFO, whatever `DATABASE_ECHO` said, so every SQL statement and its values reached the log files. The audit found buyer names, phones and addresses, plus `password_hash` values, in `logs/application.log*`. SQL is now logged only with `DATABASE_ECHO=true` (DECISION-024).
- **Shared app shell (every logged-in page):**
  - `layouts/dashboard.html` now has a `<main>` and `partials/topbar.html` a `<header>`.
  - Sidebar group headers are real buttons that work with Enter and Space, and their `aria-expanded` is now correct.
  - The sidebar label colour and `.badge-purple` were darkened to meet contrast.
- `tests/marketplace/test_checkout_web.py`: the parallel test failed once logging stopped slowing it down. Some buyers opened checkout after stock had already run out and were correctly sent to the cart. All buyers now open the form first, so all ten compete for the stock.
