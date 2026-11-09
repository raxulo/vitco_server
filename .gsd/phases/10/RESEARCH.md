# Phase 10 Research: Control Center — Catalog

**Discovery level:** 0 (internal patterns; Pillow, python-multipart and the media module already exist)
**Date:** 2026-11-09

## URLs and access

- Panel lives at `/admin/marketplace/...` (DECISION-019). `/admin` is unused today and is not a public prefix, so the
  middleware already sends guests to `/login`.
- Controllers also require a seller role, and handlers call `SellerPolicy`. Masters (categories, animal types, breeds)
  are Super Admin only even after other roles can sell, because they are shared across sellers.

## Findings that shape the design

| Finding | Consequence |
|---------|-------------|
| `application_exception_handler` answers any web request with an empty body plus a toast header | A plain form POST would show a blank page. Controllers catch domain errors and re-render the form |
| `ForbiddenException` renders the 403 page for normal requests | Use it for the panel's role guard |
| `HTTPException(404)` renders the 404 page | Use it for missing listings on GET |
| Cookie is `SameSite=Lax`, there is no CSRF token anywhere | Cross-site POSTs carry no cookie. State-changing routes are POST only. Same protection as the rest of the app |
| `MediaService.upload_image` has no size check and stores bytes as received | Add a listing path that re-encodes like profile images (EXIF stripped, real image proven) |
| `ImageProcessor` has a fixed 1024 px limit and runs synchronously | Add a `max_side` argument; run it through `asyncio.to_thread`, because the server is a single process (CON-08) |
| Write lock budget is 250 ms (DECISION-010, CON-02) | Decode images before the first write of the request; only saving the file and the row happen inside the transaction |
| `MediaCategory` already has PRODUCT, ANIMAL, BANNER, CATEGORY | No enum change |
| Media files are public under `/api/v1/media/` and cached a year | Listing images work for guests without new routes |

## Form approach

Plain multipart POST, then a 303 redirect on success. Validation failure re-renders the form with status 422, field
messages and the submitted values. Variants and specifications are repeated fields handled by a small vanilla JS file.
This works without HTMX swap rules for 4xx and keeps uploaded-file handling simple.

Pydantic schemas in `presentation/requests.py` validate form input. Business rules live in the domain and handler.

## Publishing rules

Saving a draft is forgiving. Publishing requires:

- **Product:** at least one active variant and one image.
- **Animal:** one image and a price above zero. Lactation and milk per day are required for a female animal, since they
  are what buyers compare (user request: price, lactations, milk litres per day).

## Limits

- 8 images per listing, 5 MB per upload, stored as WebP of at most 1600 px and about 300 KB.
- REST admin API is deferred to Phase 15. The panel is the only consumer in this phase.
