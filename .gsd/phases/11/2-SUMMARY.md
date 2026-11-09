---
phase: 11
plan: 2
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 11.2 Summary: Merchandising Pages

- Control Center tabs added: Banners, Home page, Store settings.
- `merchandising_controller.py` holds the routes; the `image_field` macro now takes a field name, URL key and remove flag.
- `tests/marketplace/test_merchandising_web.py` covers access, invalid input, the real banner, section and settings flows.
