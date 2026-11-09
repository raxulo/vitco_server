---
phase: 10
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/media/infrastructure/image_compressor.py
  - app/modules/media/application/services.py
  - app/modules/marketplace/domain/entities.py
  - app/modules/marketplace/domain/exceptions.py
  - app/modules/marketplace/domain/irepository.py
  - app/modules/marketplace/infrastructure/repository.py
  - app/modules/marketplace/application/command.py
  - app/modules/marketplace/application/handler.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - tests/marketplace/test_catalog_handler.py
must_haves:
  - Every catalog write calls SellerPolicy; masters are Super Admin only
  - Publishing a product without a variant or image is refused
  - A broken or oversized image never reaches storage
gap_closure: false
---

# Plan 10.1: Catalog Use Cases & Images

## Objective
Provide the application layer of the Control Center: tested use cases for masters, products and animals, plus safe listing image handling (REQ-31, REQ-32, REQ-33, REQ-47).

## Context
- .gsd/phases/10/RESEARCH.md
- app/modules/marketplace/
- app/modules/media/application/services.py

## Tasks

<task type="auto">
  <name>Listing images</name>
  <files>
    app/modules/media/infrastructure/image_compressor.py
    app/modules/media/application/services.py
    tests/marketplace/test_catalog_handler.py
  </files>
  <action>
    1. `ImageProcessor` gets `max_side`, defaulting to today's value so profile images do not change.
    2. `MediaService.prepare_listing_image(file)` checks type and size and re-encodes in a worker thread.
    3. `MediaService.store_listing_image(prepared, category, uploaded_by)` saves file and row, removing the file on rollback.
    4. `MediaService.delete_images(media_ids)` removes rows, and files only after commit.

    AVOID: decoding images inside the write transaction, because it would exceed the lock budget (DECISION-010).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_catalog_handler.py -q -k image</verify>
  <done>Text renamed `.jpg`, an oversized file and an empty file are refused with a clear message; a valid image is stored as WebP within limits and without EXIF.</done>
</task>

<task type="auto">
  <name>Catalog use cases</name>
  <files>
    app/modules/marketplace/domain/entities.py
    app/modules/marketplace/domain/exceptions.py
    app/modules/marketplace/domain/irepository.py
    app/modules/marketplace/infrastructure/repository.py
    app/modules/marketplace/application/command.py
    app/modules/marketplace/application/handler.py
    app/modules/configurator.py
    app/modules/dependencies.py
    tests/marketplace/test_catalog_handler.py
  </files>
  <action>
    1. Domain: `publish_problems()` on Product and Animal; `ListingValidationException` with a message per field.
    2. Repository: status filter, overview counts, low stock list, slug and SKU checks, usage counts, master deletes.
    3. `MarketplaceCatalogHandler`, registered through the IoC container, with writes in transactions: save and delete
       for categories, types, breeds, products and animals; unique slug generation; exactly one default variant;
       a breed must belong to the chosen type; overview.
    4. Deleting a master in use is refused with a message that suggests deactivating it.

    AVOID: changing a slug on update, because it would break shared links.
    AVOID: role checks in controllers only, because the seam must hold at the handler (DECISION-016).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace -q</verify>
  <done>
    Tests on a real database prove: non-sellers are refused on every write; publishing without variant or image is refused
    and a draft is allowed; two same-title listings get different slugs; duplicate SKU, foreign breed and in-use category
    are refused; a removed gallery image disappears and a new one is added, in the requested order.
  </done>
</task>

## Must-Haves
- [ ] Policy enforced in the handler
- [ ] Publish rules enforced on the server
- [ ] Images validated before any write

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in tests
