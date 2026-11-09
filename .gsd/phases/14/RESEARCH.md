# Phase 14 Research: Cart, COD Checkout & Orders

**Discovery level:** 0 (internal; no new dependencies)
**Date:** 2026-11-09

## Cart storage

A cookie holding only `variant id : quantity` pairs, read and revalidated on the server on every page.

- Works without JavaScript and survives reloads.
- It holds no prices, so a tampered cookie can change nothing but which items are in the cart.
- At most 30 lines and 50 of one size, which keeps the cookie well under the 4 KB limit.

## Concurrency (the main risk)

| Fact | Consequence |
|------|-------------|
| `DatabaseMiddleware` wraps each request in a session; `transaction()` inside it is `begin_nested()`, a SQLite `SAVEPOINT` | A savepoint opens a deferred transaction |
| A deferred transaction that reads and then writes fails at once with "database is locked" if another writer committed in between; `busy_timeout` does not help | Read everything before the savepoint; the first statement inside it must be the stock `UPDATE` |
| `busy_timeout` is 5 s, so writers queue | Concurrent orders wait rather than fail, as long as the point above holds |

Stock is reduced with `UPDATE ... SET stock = stock - :q WHERE id = :id AND stock >= :q AND is_active`. Zero rows changed means not enough
stock. The savepoint rollback then returns every line taken so far. Cancelling adds stock back the same way.

## Protecting customers

- **Double submit:** each checkout page carries a one-time token, stored unique on the order. A repeat returns the same order.
  `mkt_orders` is new on this branch, but a development database may already have it, so `sqlite.py` adds the column when missing.
- **Price changed since the cart was shown:** the form carries the total the customer saw. A difference stops the order and shows the new total.
- **Tampering:** prices, totals and delivery charge come only from the server.

## Privacy

- The order placed page needs a short-lived cookie and shows only the reference and amount.
- Tracking is a POST, so the phone number stays out of URLs and logs. A wrong reference and a wrong phone get the same answer.
  It shows items, amounts, status and pincode, but not the name or full address.
- Rate limits on tracking and checkout are in Phase 15.

## Status and payment

`OrderStatus.can_move_to` controls the flow. Moving to Delivered marks the COD payment as Paid. Cancelling returns stock and needs a reason.
A variant removed since the order has a NULL link and is skipped when returning stock.
