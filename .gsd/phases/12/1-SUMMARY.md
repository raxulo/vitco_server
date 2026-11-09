---
phase: 12
plan: 1
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 12.1 Summary: Storefront Read Side

- `IStorefrontRepository`, `StorefrontRepository`, `StorefrontHandler`, and public card read models in `domain/dto.py`.
- Only live listings are returned. Cards have no seller ids or internal notes.
- `home()` follows visible sections in order and drops empty ones.
