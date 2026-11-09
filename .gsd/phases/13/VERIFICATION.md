# Phase 13 Verification: Browse, Detail Pages & Enquiries

**Date:** 2026-11-09
**Verdict:** Pass

## Test suite

- Full suite without `test_large_import_throughput`: 692 passed, 1 failed. The failure is `test_owner_options_super_admin`,
  which also fails on `a345c6f` (see Phase 8).
- After that run, only a CSS rule and one template wrapper changed. Marketplace and removal tests were re-run: 373 passed.

## Runtime check in real Chrome

Real server on an isolated database and media folder, with demo content created through the real Control Center forms.

| Check | Result |
|-------|--------|
| 7 store pages at 1440, 768, 390 and 360 px | No overflow, no broken images; screenshots reviewed |
| Size picker | Price and stock text change with the chosen size |
| Store gallery thumbnail | Moves to the image and marks the thumbnail |
| Animal type filter | Auto-submits, narrows 4 to 2 and reveals the breed filter |
| Phone | Filters start closed, contact bar shows, price and contact sit above details |
| Enquiry with a bad phone | Message shown, typed name kept |
| Enquiry with a good phone | Thank-you shown, and it appears in the seller's inbox as New |
| Control Center gallery arrows and remove | Order changes in the browser and survives saving |
| Console, JS errors, tracebacks | None, apart from the expected 404 and 422 responses being checked |
| Development database | Checksum unchanged |

## Found by screenshot review, then fixed

On phones the animal page put the long details table before the price and contact box.

## Must-haves

- [x] Search treats `%` and `_` as plain text
- [x] Filters and sorting agree with the price on the card
- [x] Sold animals refuse enquiries; a repeat from the same phone adds nothing until the first is closed
- [x] Only the animal's seller sees its enquiries
- [x] Every link on the home page opens
- [x] 18 kinds of bad query value return 200 on both listing pages
- [x] Animals have no cart; Call, WhatsApp and enquiry are present

## Limits

- Public forms have no rate limit yet. Phase 15 adds it. Until then the hidden field and the repeat rule are the only protection.
- Products have no cart yet. Phase 14 adds it.
- Call and WhatsApp links were checked in the page, not by placing a real call or message.
- Performance on 1,000 listings (NFR-16) is measured in Phase 15.
