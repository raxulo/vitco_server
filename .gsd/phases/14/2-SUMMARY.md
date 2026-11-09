---
phase: 14
plan: 2
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 14.2 Summary: Cart, Checkout & Orders Pages

- Customer: Add to cart and Buy now, cart icon with count, cart, checkout, order placed, tracking. Everything works without JavaScript.
- The cart is a cookie of variant and quantity pairs, with no prices; the server revalidates it on every page.
- Seller: Orders tab with search and filters; order detail with items, buyer, address, totals, only the allowed next step, and cancel with a reason.

## Changes outside the plan

- `store.css`: the reset `.st p { margin: 0 }` was stronger than single-class rules and silently removed margins across the store.
  It now uses `:where()`, so spacing on existing pages improved too. The home page was reviewed again afterwards.
- `tests/dataexchange/factories.py`: `create_user` built emails from 6 hex characters, which collided at random as the shared test
  database grew and caused a flaky failure. It now uses the full id.
