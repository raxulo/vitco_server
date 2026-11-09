---
phase: 14
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/core/database/drivers/sqlite.py
  - app/modules/marketplace/domain/orders.py
  - app/modules/marketplace/domain/exceptions.py
  - app/modules/marketplace/domain/merchandising.py
  - app/modules/marketplace/domain/irepository.py
  - app/modules/marketplace/infrastructure/models.py
  - app/modules/marketplace/infrastructure/order_repository.py
  - app/modules/marketplace/application/command.py
  - app/modules/marketplace/application/order_handler.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - tests/marketplace/test_order_handler.py
must_haves:
  - Stock can never go negative, under real concurrent orders
  - Totals come only from the server
  - A repeated submit creates one order
  - Cancelling returns stock exactly once
gap_closure: false
---

# Plan 14.1: Cart & Order Use Cases

## Objective
Turn a cart into a safe COD order and let sellers run the order through its status flow (REQ-36, REQ-43, REQ-44, REQ-45, DECISION-018).

## Context
- .gsd/phases/14/RESEARCH.md
- app/modules/marketplace/application/storefront_handler.py

## Tasks

<task type="auto">
  <name>Cart and checkout</name>
  <files>
    app/modules/marketplace/domain/orders.py
    app/modules/marketplace/domain/irepository.py
    app/modules/marketplace/infrastructure/order_repository.py
    app/modules/marketplace/application/order_handler.py
    app/core/database/drivers/sqlite.py
    tests/marketplace/test_order_handler.py
  </files>
  <action>
    Cart view revalidated against live listings. Checkout rules: store open, COD on, pincode served, minimum order, total unchanged, enough stock.
    Reads come before the savepoint and the stock update comes first inside it.

    AVOID: reading inside the order savepoint before the first write, because SQLite would fail at once under concurrent writers.
    AVOID: trusting any amount from the browser.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_order_handler.py -q</verify>
  <done>
    Real database tests: 10 concurrent orders for 3 pieces give exactly 3 orders and stock 0; every checkout rule refuses; tampered total
    refuses; same token gives one order; a failed line returns the lines already taken.
  </done>
</task>

<task type="auto">
  <name>Order management</name>
  <files>
    app/modules/marketplace/application/order_handler.py
    app/modules/marketplace/infrastructure/order_repository.py
    tests/marketplace/test_order_handler.py
  </files>
  <action>
    Seller-scoped list, detail and status change following `OrderStatus.can_move_to`. Delivered marks payment as Paid. Cancel needs a reason and returns stock.
    Tracking needs both reference and phone.

    AVOID: revealing whether a reference exists to someone with the wrong phone.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace -q</verify>
  <done>Tests prove the flow, a second cancel changing nothing, seller scope, and identical answers for wrong reference and wrong phone.</done>
</task>

## Must-Haves
- [ ] Concurrency proven with real parallel orders
- [ ] Server-side totals only
- [ ] Idempotent checkout

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in tests
