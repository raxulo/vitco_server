---
phase: 15
plan: 1
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 15.1 Summary: Rate Limits & Public API

- `app/core/rate_limit.py`: a sliding-window limiter whose memory is bounded at 10,000 keys.
- `StoreRateLimiter`: per IP over 10 minutes: enquiries 10, orders 20, tracking 20. The website and API share each count.
- Website answers with a store page and API with JSON, both `429` with `Retry-After`. `MARKETPLACE_RATE_LIMIT_ENABLED` switches limits off for tests.
- `/api/v1/marketplace`: store, home, categories, animal types, breeds, products, animals, details, cart quote, enquiries, orders, tracking.
- Explicit response schemas decide what is public. No seller ids, exact stock or internal fields. Tracking leaves out the buyer's name and address.
- `docs/MARKETPLACE_API.md` is the guide for the app team.

## Changes outside the plan

- `tests/test_marketplace_removal.py`: `/api/v1/marketplace` is in use again, so the checks now name the old paths that must stay gone.
- The admin REST API named in DECISION-019 was not built (DECISION-023).
