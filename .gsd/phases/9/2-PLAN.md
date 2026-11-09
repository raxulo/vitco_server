---
phase: 9
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/modules/marketplace/domain/entities.py
  - app/modules/marketplace/domain/irepository.py
  - app/modules/marketplace/infrastructure/mapper.py
  - app/modules/marketplace/infrastructure/repository.py
  - app/modules/marketplace/infrastructure/seed.py
  - app/modules/configurator.py
  - app/bootstrap/lifespan.py
  - app/modules/recyclebin/infrastructure/repository.py
  - .gsd/STACK.md
  - tests/marketplace/test_repository.py
  - tests/marketplace/test_seed.py
  - tests/test_recycle_bin.py
must_haves:
  - A non-Super-Admin seller can only see and change their own listings
  - Startup seeds starter masters once and never recreates removed ones
  - Recycle Bin purge succeeds for a user who owns new listings
gap_closure: false
---

# Plan 9.2: Catalog Repository, Seller Scope, Seed & Recycle Bin

## Objective
Provide scoped catalog data access, starter master data and Recycle Bin coverage, so Phase 10 can build the Control Center directly on them (REQ-47, DECISION-016).

## Context
- .gsd/phases/9/RESEARCH.md
- app/modules/masters/units/infrastructure/repository.py
- app/bootstrap/lifespan.py
- app/modules/recyclebin/infrastructure/repository.py

## Tasks

<task type="auto">
  <name>Entities and scoped repository</name>
  <files>
    app/modules/marketplace/domain/entities.py
    app/modules/marketplace/domain/irepository.py
    app/modules/marketplace/infrastructure/mapper.py
    app/modules/marketplace/infrastructure/repository.py
    app/modules/configurator.py
    tests/marketplace/test_repository.py
  </files>
  <action>
    1. Entities with `@dataclass(slots=True, kw_only=True)`: Category, AnimalType, AnimalBreed, Product, ProductVariant, Animal, ListingImage.
    2. `IMarketplaceRepository` plus the SQLAlchemy implementation: create, update, get, list with total, and soft delete for
       products and animals; create, update, delete and list for categories, types and breeds.
    3. `MarketplaceAccessScope`: Super Admin has no filter, any other owner gets `seller_user_id == owner.id`, and no owner gets nothing.
    4. Load variants and images with `selectinload`, so a list of N listings does not issue N queries.
    5. Register in `_repo_config`.

    AVOID: returning silently when an update targets a row outside scope, because the caller must see "not found".
    AVOID: importing the application layer or `app.middleware` in `domain/`, because the dependency rule forbids it.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_repository.py -q</verify>
  <done>
    Real-DB tests prove: Super Admin sees all sellers' listings; an Admin seller sees only their own and gets
    "not found" on another seller's listing, for read, update and delete; soft-deleted listings leave lists;
    the query count for a 20-item list stays the same as for a 2-item list.
  </done>
</task>

<task type="auto">
  <name>Starter data at startup</name>
  <files>
    app/modules/marketplace/infrastructure/seed.py
    app/bootstrap/lifespan.py
    tests/marketplace/test_seed.py
  </files>
  <action>
    1. `MarketplaceSeeder.run()` does nothing once the settings row exists. Otherwise it adds animal types and breeds,
       root categories, default home sections and the settings row in one transaction.
    2. Call it in `lifespan.py` after the Super Admin seeder, in its own transaction. Log a failure and keep starting.

    AVOID: fake products, animals or banners, because they could reach customers.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_seed.py -q</verify>
  <done>
    Running twice adds nothing; a category removed after seeding stays removed; settings has exactly one row with COD on.
  </done>
</task>

<task type="auto">
  <name>Recycle Bin coverage and docs</name>
  <files>
    app/modules/recyclebin/infrastructure/repository.py
    tests/test_recycle_bin.py
    .gsd/STACK.md
  </files>
  <action>
    1. Purge deletes products and animals of the tree's users before the users. Impact counts them under `marketplace_listings`, alongside legacy rows.
    2. Run a full suite comparison and update `.gsd/STACK.md`.

    AVOID: deleting order lines or enquiries, because other users' records must survive with their snapshots.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/test_recycle_bin.py tests/marketplace -q</verify>
  <done>
    Purging an Admin who owns a product with variants and images, an animal, an order line and an enquiry succeeds;
    the listings, variants and images are gone; the order line and enquiry remain with their snapshot and a NULL
    seller; another seller's listing is untouched.
  </done>
</task>

## Must-Haves
- [ ] Seller scope proven with a non-Super-Admin seller
- [ ] Seeder is idempotent and cannot stop startup
- [ ] Purge covers new tables without losing other users' history

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in the full test suite
