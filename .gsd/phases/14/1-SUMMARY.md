---
phase: 14
plan: 1
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 14.1 Summary: Cart & Order Use Cases

- `domain/orders.py`, `IOrderRepository`, `OrderRepository`, `MarketplaceOrderHandler`.
- Reads come before the savepoint and the guarded stock update comes first inside it, because a SQLite savepoint that reads
  and then writes fails at once under concurrent writers.
- Prices and totals come only from the database. The total the customer saw must match, or the order stops.
- `checkout_token` is unique on `mkt_orders`, so a repeated submit returns the same order. `sqlite.py` adds the column to databases that already have the table.
- Moving an order is conditional on its old status, so two clicks cannot return stock twice.
- Delivered marks the COD payment as Paid. Cancelling needs a reason and returns stock.
- Tracking needs both reference and phone, and both wrong cases answer the same.
