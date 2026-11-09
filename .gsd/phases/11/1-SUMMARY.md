---
phase: 11
plan: 1
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 11.1 Summary: Merchandising Use Cases

- `domain/merchandising.py`: Banner with `state(now)`, HomeSection, TrendingTag, StoreSettings with `serves(pincode)`.
- `domain/links.py`: `is_safe_link` allows site paths and http(s) only.
- `IMerchandisingRepository`, `MerchandisingRepository`, `MarketplaceMerchandisingHandler` (Super Admin only).
- Entities live in `domain/merchandising.py` rather than `entities.py`, so the catalog and store content stay separate.
- During review the handler was changed to depend on the domain interface and commands moved to `command.py`, as AGENTS.md requires.
