---
phase: 13
plan: 1
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 13.1 Summary: Browse, Detail & Enquiry Use Cases

- `ProductFilters`, `AnimalFilters`, detail read models, and listing and detail queries in `StorefrontRepository`.
- Price filter and sort use the price shown on the card: the default active size, else the lowest active price.
- Search escapes `%` and `_`. A category filter includes its whole branch.
- Sold animals open by link but stay out of lists, and they refuse enquiries.
- `normalize_indian_mobile`; a repeat enquiry from the same phone adds nothing until the first is closed.
- Seller side: scoped `list_enquiries` and `update_enquiry`, proven with a second seller.
