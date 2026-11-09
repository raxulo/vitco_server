---
phase: 9
plan: 1
status: complete
commit: pending phase commit after user approval
---

# Plan 9.1 Summary: Domain Rules & Schema

- `domain/`: enums with the order status flow, exceptions, `SellerPolicy` and `slugify`.
- `infrastructure/models.py`: 15 `mkt_*` tables, covering catalog, galleries, banners, home sections, trending tags,
  settings, orders and enquiries. The settings table is limited to one row by a constraint.
- Tests on real SQLite: 32 passed, covering refused bad prices and stock, cascades, duplicate slugs and a refused
  delete of a user who owns a listing.
