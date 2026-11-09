---
phase: 15
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/core/rate_limit.py
  - app/config/settings.py
  - app/modules/marketplace/application/rate_limits.py
  - app/modules/marketplace/domain/exceptions.py
  - app/web/storefront/controller.py
  - app/web/storefront/cart_controller.py
  - app/web/templates/pages/store/too_many.html
  - app/api/v1/routers/marketplace.py
  - app/api/v1/schemas/marketplace.py
  - app/api/v1/router.py
  - app/middleware/authentication.py
  - docs/MARKETPLACE_API.md
  - tests/marketplace/test_rate_limit.py
  - tests/marketplace/test_store_api.py
  - tests/test_marketplace_removal.py
must_haves:
  - Enquiry, checkout and tracking are rate limited on web and API
  - Memory used by the limiter stays bounded
  - The API exposes no seller ids, names or addresses publicly
  - API lists and single records use the standard envelopes
gap_closure: false
---

# Plan 15.1: Rate Limits & Public API

## Objective
Protect the public forms and give the mobile app a REST API for the store (REQ-46, NFR-17).

## Context
- AGENTS.md section 4
- app/api/v1/routers/unit_master.py
- docs/EXCEL_EXCHANGE_API.md

## Tasks

<task type="auto">
  <name>Rate limits</name>
  <files>
    app/core/rate_limit.py
    app/modules/marketplace/application/rate_limits.py
    app/web/storefront/
    tests/marketplace/test_rate_limit.py
  </files>
  <action>
    In-memory sliding window per action and client IP, bounded by a key limit. The server is a single process (CON-08), so memory is enough.
    Web shows a store page with status 429 and Retry-After. Limits: enquiry 10, checkout 20, tracking 20, each per 10 minutes.

    AVOID: per-action limits low enough to block a village sharing one mobile IP.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_rate_limit.py -q</verify>
  <done>The limit, its reset, separate actions and clients, the key bound and the 429 page are proven.</done>
</task>

<task type="auto">
  <name>Public REST API</name>
  <files>
    app/api/v1/routers/marketplace.py
    app/api/v1/schemas/marketplace.py
    app/middleware/authentication.py
    docs/MARKETPLACE_API.md
    tests/marketplace/test_store_api.py
    tests/test_marketplace_removal.py
  </files>
  <action>
    Home, store info, categories, animal types and breeds, products, animals, details, cart quote, enquiries, orders, tracking.
    Amounts are JSON strings so paise stay exact. Explicit response schemas decide what is public. Guide for the app team.

    AVOID: serialising domain objects directly, because new fields would become public by accident.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_store_api.py tests/test_marketplace_removal.py -q</verify>
  <done>Every endpoint works through the real app with envelopes checked; private fields are absent; orders match the web rules.</done>
</task>

## Must-Haves
- [ ] Public write endpoints limited
- [ ] Explicit public schemas
- [ ] App team guide written

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in tests
