---
milestone: Marketplace Revamp
version: 1.2.0
updated: 2026-11-08T00:00:00+05:30
---

# Roadmap

> **Current Milestone:** v1.2.0 — Marketplace Revamp
> **Goal:** Replace the old marketplace with a professional e-commerce store for dairy animals and dairy products,
> with a clean, polished storefront and a Control Center that lets the Super Admin run everything without code changes.
> **Current Phase:** 16 - Control Center & Store Visual Refresh
> **Status:** Phases 8 to 16 verified; final visual sign-off and the one milestone commit await the user
> **Branch:** `feature/marketplace-revamp` (from the tip of `bugfix/static-asset-loading`, see DECISION-021)
> **Previous milestone:** [v1.1.0 — Excel Data Exchange](milestones/v1.1.0/ROADMAP.md)

## Must-Haves (from SPEC Goal 5)

- [x] The old marketplace (UI, API, code) is gone; its database tables stay untouched and the Recycle Bin still works
- [x] E-commerce storefront: categories, banners, trending, featured sections, search, filters, sorting
- [x] Animal listings (cow, buffalo, sheep, goat and more) show price, lactation, milk litres per day, full description and an image gallery; buyers respond by Call, WhatsApp or enquiry form
- [x] Product catalog (milk, ghee, coconut and similar) works like mainstream e-commerce: variants, MRP and price, stock, gallery, cart
- [x] Guest checkout with Cash on Delivery, plus order tracking by order reference and phone
- [x] Control Center: Super Admin fully controls catalog, animals, banners, trending, home sections, store settings, orders and enquiries
- [x] Super Admin is the only seller now; Admin and Sub Admin can be enabled later without a schema change (DECISION-016)
- [ ] Responsive, accessible, fast UI that the user signs off visually (NFR-15, NFR-16)

## Nice-to-Haves

- [ ] Product ratings and reviews
- [ ] Wishlist
- [ ] Coupon codes
- [ ] Excel bulk import of products through the existing `dataexchange` engine

## Out of Scope (this milestone)

- Online payments and customer accounts or OTP login (DECISION-018 keeps room for them)
- Seller panel for Admin / Sub Admin (DECISION-016 keeps room for it)
- Dropping the legacy tables (a separate, explicit step after the server is checked)

---

## Phases

### Phase 8: Legacy Marketplace Removal
**Status:** ✅ Complete (verified at runtime 2026-11-09 — [VERIFICATION.md](phases/8/VERIFICATION.md)); phase commit pending approval
**Objective:** Delete the old marketplace code, API, pages, cart and uploads so the app runs cleanly without it, while legacy tables stay intact and the Recycle Bin can still purge users who own legacy rows.
**Requirements:** REQ-28, REQ-29
**Decisions:** DECISION-015
**Discovery:** Level 0 — see [phases/8/RESEARCH.md](phases/8/RESEARCH.md)

**Plans:**
- [x] Plan 8.1: Decouple Recycle Bin from legacy models (wave 1) — [1-PLAN.md](phases/8/1-PLAN.md)
- [x] Plan 8.2: Remove the old marketplace (wave 2) — [2-PLAN.md](phases/8/2-PLAN.md)

---

### Phase 9: Marketplace Domain Foundation
**Status:** ✅ Complete (verified at runtime 2026-11-09 — [VERIFICATION.md](phases/9/VERIFICATION.md)); phase commit pending approval
**Objective:** Build the new `app/modules/marketplace/` domain and `mkt_*` schema: categories, animal types and breeds, products, variants, animals, images, banners, home sections, settings, orders and enquiries. Includes the single seller policy and owner scope, starter master data, and Recycle Bin coverage of the new tables.
**Requirements:** REQ-47
**Decisions:** DECISION-015, 016
**Depends on:** Phase 8
**Discovery:** Level 0 — see [phases/9/RESEARCH.md](phases/9/RESEARCH.md)

**Plans:**
- [x] Plan 9.1: Domain rules & schema (wave 1) — [1-PLAN.md](phases/9/1-PLAN.md)
- [x] Plan 9.2: Catalog repository, seller scope, seed & Recycle Bin (wave 2) — [2-PLAN.md](phases/9/2-PLAN.md)

---

### Phase 10: Control Center — Catalog
**Status:** ✅ Complete (verified at runtime 2026-11-09 — [VERIFICATION.md](phases/10/VERIFICATION.md))
**Objective:** A professional Super Admin panel at `/admin/marketplace`: overview dashboard, categories, products with variants, stock and gallery, animals with all specifications and gallery, and animal type and breed masters. Draft, publish and sold states, with image upload through `MediaService`.
**Requirements:** REQ-30, REQ-31, REQ-32, REQ-33
**Decisions:** DECISION-019, 022
**Depends on:** Phase 9
**Discovery:** Level 0 — see [phases/10/RESEARCH.md](phases/10/RESEARCH.md)

**Plans:**
- [x] Plan 10.1: Catalog use cases & images (wave 1) — [1-PLAN.md](phases/10/1-PLAN.md)
- [x] Plan 10.2: Control Center pages (wave 2) — [2-PLAN.md](phases/10/2-PLAN.md)

---

### Phase 11: Control Center — Merchandising & Settings
**Status:** ✅ Complete (verified at runtime 2026-11-09 — [VERIFICATION.md](phases/11/VERIFICATION.md))
**Objective:** Super Admin control of the storefront without code changes: banners with scheduling, trending items, ordered home sections, and store settings (brand, contact, WhatsApp, delivery charges, minimum order, COD switch, serviceable pincodes, policies, store open or closed).
**Requirements:** REQ-34, REQ-35
**Depends on:** Phase 10

**Plans:**
- [x] Plan 11.1: Merchandising use cases (wave 1) — [1-PLAN.md](phases/11/1-PLAN.md)
- [x] Plan 11.2: Merchandising pages (wave 2) — [2-PLAN.md](phases/11/2-PLAN.md)

---

### Phase 12: Storefront Design System & Home
**Status:** ✅ Complete (verified 2026-11-09, design approved by the user — [VERIFICATION.md](phases/12/VERIFICATION.md))
**Objective:** A standalone store layout and design system (tokens, typography, cards, buttons, skeletons, empty states), then the public home page: header with search, category navigation, banner carousel, trending, featured animals and products, footer. The user approves the visual direction on a real page before later phases build on it.
**Requirements:** REQ-37, NFR-15, NFR-18
**Decisions:** DECISION-020
**Depends on:** Phase 11 (home content comes from the Control Center)

**Plans:**
- [x] Plan 12.1: Storefront read side (wave 1) — [1-PLAN.md](phases/12/1-PLAN.md)
- [x] Plan 12.2: Design system & home page, with user design approval (wave 2) — [2-PLAN.md](phases/12/2-PLAN.md)

---

### Phase 13: Browse, Detail Pages & Enquiries
**Status:** ✅ Complete (verified at runtime 2026-11-09 — [VERIFICATION.md](phases/13/VERIFICATION.md))
**Objective:** Product and animal listing pages with search, filters, sorting and pagination; a mainstream product detail page; an animal detail page with gallery, price, lactation, milk litres per day and full description; Call, WhatsApp and enquiry form; an enquiry inbox in the Control Center.
**Requirements:** REQ-36 (enquiries), REQ-38, REQ-39, REQ-40, REQ-41, REQ-42
**Decisions:** DECISION-017
**Depends on:** Phase 12

**Plans:**
- [x] Plan 13.1: Browse, detail and enquiry use cases (wave 1) — [1-PLAN.md](phases/13/1-PLAN.md)
- [x] Plan 13.2: Store pages and enquiry inbox (wave 2) — [2-PLAN.md](phases/13/2-PLAN.md)

---

### Phase 14: Cart, COD Checkout & Orders
**Status:** ✅ Complete (verified at runtime 2026-11-09 — [VERIFICATION.md](phases/14/VERIFICATION.md))
**Objective:** Cart, guest COD checkout with server-side prices and atomic stock control, order confirmation, tracking by reference and phone, and order management with a controlled status flow in the Control Center.
**Requirements:** REQ-36 (orders), REQ-43, REQ-44, REQ-45
**Decisions:** DECISION-018
**Depends on:** Phase 13
**Discovery:** Level 0 — see [phases/14/RESEARCH.md](phases/14/RESEARCH.md)

**Plans:**
- [x] Plan 14.1: Cart & order use cases (wave 1) — [1-PLAN.md](phases/14/1-PLAN.md)
- [x] Plan 14.2: Cart, checkout & orders pages (wave 2) — [2-PLAN.md](phases/14/2-PLAN.md)

---

### Phase 15: Public API, SEO & Launch Hardening
**Status:** ✅ Complete (2026-11-09)
**Objective:** The new `/api/v1/marketplace` REST API with standard envelopes, SEO metadata and sitemap, abuse limits on public forms, accessibility and performance audit, end-to-end walkthrough, and the release checklist including the deferred legacy-table decision.
**Requirements:** REQ-46, NFR-15, NFR-16, NFR-17
**Depends on:** Phase 14

**Plans:**
- [x] Plan 15.1: Rate limits & public API (wave 1) — [1-PLAN.md](phases/15/1-PLAN.md)
- [x] Plan 15.2: SEO, audits & release (wave 2) — [2-PLAN.md](phases/15/2-PLAN.md)

**Verification:** [VERIFICATION.md](phases/15/VERIFICATION.md) · **Release checklist:** [RELEASE.md](phases/15/RELEASE.md)

### Phase 16: Control Center & Store Visual Refresh
**Status:** ✅ Complete (2026-11-09)
**Objective:** A more professional, modern Control Center, requested by the user after Phase 15, plus removable demo data. A store redesign was tried and undone at the user's request. No change to URLs or buying rules.
**Requirements:** NFR-15
**Depends on:** Phase 15

**Plans:**
- [x] Plan 16.1: Control Center & store visual refresh — [1-PLAN.md](phases/16/1-PLAN.md)

**Verification:** [VERIFICATION.md](phases/16/VERIFICATION.md)

### Phase 17: Collection Totals & Filters
**Status:** ✅ Complete (2026-11-09), on branch `feature/collection-summary-filters`
**Objective:** Totals and fuller filters on the VLCC and MCC collection lists, requested by the user. Not part of the marketplace milestone's goal.
**Depends on:** Nothing in the marketplace

**Plans:**
- [x] Plan 17.1: Collection totals & filters — [1-PLAN.md](phases/17/1-PLAN.md)

**Verification:** [VERIFICATION.md](phases/17/VERIFICATION.md)

### Phase 18: MCC Visible Member
**Status:** ✅ Complete (2026-11-09), on branch `feature/mcc-visible-member`
**Objective:** A setting on FAT / SNF and Fixed Rate MCCs that hides the VLCC's name in the sample number detail, reported in sync. VLCC comes later.
**Depends on:** Nothing in the marketplace

**Plans:**
- [x] Plan 18.1: MCC Visible Member — [1-PLAN.md](phases/18/1-PLAN.md)

**Verification:** [VERIFICATION.md](phases/18/VERIFICATION.md)

### Phase 20: PostgreSQL Support
**Status:** 🔄 In progress (planned 2026-11-11), on branch `feature/postgresql-support`
**Objective:** PostgreSQL becomes the default database, with the schema managed by Alembic. SQLite keeps working through `DATABASE_URL` (DECISION-025, DECISION-026). Requested by the user.
**Depends on:** Nothing in the marketplace

**Plans:**
- [x] Plan 20.1: Postgres driver & configuration — [1-PLAN.md](phases/20/1-PLAN.md)
- [x] Plan 20.2: Alembic migrations — [2-PLAN.md](phases/20/2-PLAN.md) (verified on SQLite)
- [ ] Plan 20.3: Postgres compatibility & docs — [3-PLAN.md](phases/20/3-PLAN.md)

**Research:** [RESEARCH.md](phases/20/RESEARCH.md)

---

## Progress Summary

| Phase | Status | Plans | Complete |
|-------|--------|-------|----------|
| 8 | ✅ | 2/2 | 100% |
| 9 | ✅ | 2/2 | 100% |
| 10 | ✅ | 2/2 | 100% |
| 11 | ✅ | 2/2 | 100% |
| 12 | ✅ | 2/2 | 100% |
| 13 | ✅ | 2/2 | 100% |
| 14 | ✅ | 2/2 | 100% |
| 15 | ✅ | 2/2 | 100% |
| 16 | ✅ | 1/1 | 100% |
| 17 | ✅ | 1/1 | 100% |
| 18 | ✅ | 1/1 | 100% |
| 20 | 🔄 | 2/3 | 67% |

---
*Phases 9–15 are planned one at a time with `/plan N`. Last updated: 2026-11-08*
