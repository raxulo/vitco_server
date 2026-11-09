---
phase: 10
plan: 1
status: complete
commit: pending milestone commit (user: commit after all phases)
---

# Plan 10.1 Summary: Catalog Use Cases & Images

- `MediaService`: `prepare_listing_image` validates and re-encodes in a worker thread, before any write. `store_listing_image`
  and `delete_images` tie files to the transaction. Listing images are WebP, at most 1600 px and about 300 KB, without EXIF.
- `MarketplaceCatalogHandler`: masters, products, animals, overview. It calls `SellerPolicy` on every use case.
- Domain: `problems()` and `publish_problems()` on Product and Animal, plus `ListingValidationException` and `MasterInUseException`.
- A test proves the DECISION-016 seam: adding Admin to `SELLER_ROLES` lets an Admin sell and see only their own listings,
  while masters stay with the Super Admin.
