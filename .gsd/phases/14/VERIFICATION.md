# Phase 14 Verification: Cart, COD Checkout & Orders

**Date:** 2026-11-09
**Verdict:** Pass

## Test suite

Full suite without `test_large_import_throughput`: 764 passed, 1 failed. The failure is `test_owner_options_super_admin`,
which also fails on `a345c6f` (see Phase 8).

## Concurrency

| Test | Result |
|------|--------|
| 10 parallel orders for 3 pieces, at handler level | Exactly 3 orders, stock 0, the other 7 refused with a message, no database errors |
| 10 parallel guests for 3 pieces, over HTTP through the full middleware | Exactly 3 orders, stock 0, every response 303 or 422 |
| Same checkout token submitted 5 times in parallel | One order, stock taken once |
| 5 parallel cancels | One succeeds, stock returned once |
| A later line fails during an order | Stock taken for earlier lines goes back |

These ran in-process on SQLite with `asyncio`. A heavier load test on the real server is in Phase 15.

## Runtime check in real Chrome

Real server on an isolated database and media folder.

| Check | Result |
|-------|--------|
| Product page: choose size, quantity, Add to cart | Cart shows the right size, count and total |
| Change quantity in the cart | Page updates and the total changes |
| Checkout with a bad phone | Message shown, typed values kept, button usable again |
| Place order | Reference shown, cart empties |
| Track with wrong phone, then right phone | Generic message, then the order |
| Seller: confirm, pack, send out | Only the next step is offered each time |
| Seller: cancel | Asks for confirmation, order shows Cancelled |
| Product, cart, checkout and placed pages at 1440, 768, 390 and 360 px; track and order pages on phones | No overflow |
| Console, JS errors, tracebacks | None, apart from the expected 422 being checked |
| Development database | Checksum unchanged |

## Found by screenshot review, then fixed

- The store CSS reset was stronger than single-class rules and removed margins across the store.
- The store name was cut off in the phone header.

## Must-haves

- [x] Stock cannot go negative under real concurrent orders
- [x] Totals come only from the server; a tampered total stops the order
- [x] A repeated submit creates one order
- [x] Cancelling returns stock exactly once
- [x] The cart works without JavaScript (the HTTP tests send no script)
- [x] Tampered cookies only lose items
- [x] Phone numbers stay out of URLs; a wrong reference and a wrong phone answer the same
- [x] The thank-you page shows no personal details

## Limits

- Stock is taken when the order is placed, not when added to the cart, so an item in a cart can sell out. The cart and checkout then say so.
- Checkout and tracking have no rate limit yet. Phase 15 adds it. Tracking guesses are the main reason.
- There are no order notifications. The seller sees new orders in the Control Center, and the buyer tracks with the reference.
- A database that stays busy past 5 s shows "please try again" and places nothing. This path was reviewed, not forced in a test.
