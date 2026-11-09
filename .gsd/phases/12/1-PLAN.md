---
phase: 12
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/marketplace/domain/dto.py
  - app/modules/marketplace/domain/irepository.py
  - app/modules/marketplace/infrastructure/storefront_repository.py
  - app/modules/marketplace/application/storefront_handler.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - tests/marketplace/test_storefront_handler.py
must_haves:
  - Guests never see drafts, deleted, archived or sold listings, or inactive categories
  - Empty sections disappear
  - Query count does not grow with the number of cards
gap_closure: false
---

# Plan 12.1: Storefront Read Side

## Objective
Read the published catalog and store content for customers, with no login, as card-shaped read models (REQ-37, NFR-16).

## Context
- app/modules/marketplace/infrastructure/repository.py
- app/modules/marketplace/application/merchandising_handler.py

## Tasks

<task type="auto">
  <name>Cards and home page assembly</name>
  <files>
    app/modules/marketplace/domain/dto.py
    app/modules/marketplace/domain/irepository.py
    app/modules/marketplace/infrastructure/storefront_repository.py
    app/modules/marketplace/application/storefront_handler.py
    app/modules/configurator.py
    app/modules/dependencies.py
    tests/marketplace/test_storefront_handler.py
  </files>
  <action>
    1. ProductCard: price and MRP of the default active size, discount, stock, sizes count. AnimalCard: price, milk, lactation, age, location, type, breed.
    2. Products need PUBLISHED status, an active size and an active category. Animals need PUBLISHED or RESERVED status and an active type.
    3. `StorefrontHandler.home()` follows visible home sections in order and drops empty ones.

    AVOID: exposing seller ids or internal notes on cards, because these pages are public.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_storefront_handler.py -q</verify>
  <done>Tests on a real database cover every hidden state, section order, empty sections, card numbers and query count.</done>
</task>

## Must-Haves
- [ ] Only live listings are readable
- [ ] Sections follow the Control Center

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in tests
