---
phase: 10
plan: 2
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 10.2 Summary: Control Center Pages

- `/admin/marketplace`: overview, products, animals, categories, animal types and breeds, with a sidebar item built from `SellerPolicy`.
- `app/web/static/css/marketplace-admin.css` and `app/web/static/js/marketplace-admin.js`, scoped under `.mk`; no inline page styles
  apart from small layout overrides in a few templates.
- `presentation/requests.py` validates forms and gives one readable message per field.
- `inr` template filter uses Indian digit grouping, for use by the storefront too.

## Changes outside the plan

- `tests/conftest.py`: `api` and `token_for` moved up from `tests/dataexchange/conftest.py` so all tests share one app, and
  `MEDIA_PATH` now points to the temporary folder. Without that, test uploads would have gone to the real `storage/media`.
- `tests/test_marketplace_removal.py` now checks old URLs only, since a new Control Center link exists.

## Later phases must update

`tests/test_marketplace_removal.py` still asserts no `/marketplace` route or link. Phases 12 and 15 add those and must
narrow it to the old paths such as `/marketplace/setup`.
