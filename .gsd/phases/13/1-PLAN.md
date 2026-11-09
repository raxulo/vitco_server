---
phase: 13
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/marketplace/domain/dto.py
  - app/modules/marketplace/domain/contact.py
  - app/modules/marketplace/domain/entities.py
  - app/modules/marketplace/domain/exceptions.py
  - app/modules/marketplace/domain/irepository.py
  - app/modules/marketplace/infrastructure/storefront_repository.py
  - app/modules/marketplace/infrastructure/repository.py
  - app/modules/marketplace/application/command.py
  - app/modules/marketplace/application/storefront_handler.py
  - app/modules/marketplace/application/handler.py
  - tests/marketplace/test_browse_handler.py
must_haves:
  - Search treats % and _ as plain text
  - Filters and sorting agree with the price shown on the card
  - A sold animal cannot get an enquiry; the same buyer cannot flood one animal
  - Only the animal's seller sees its enquiries
gap_closure: false
---

# Plan 13.1: Browse, Detail & Enquiry Use Cases

## Objective
Give customers real browsing and give sellers their enquiries (REQ-36, REQ-38 to REQ-42, DECISION-017).

## Context
- app/modules/marketplace/infrastructure/storefront_repository.py
- app/modules/marketplace/application/storefront_handler.py

## Tasks

<task type="auto">
  <name>Listing and detail reads</name>
  <files>
    app/modules/marketplace/domain/dto.py
    app/modules/marketplace/domain/irepository.py
    app/modules/marketplace/infrastructure/storefront_repository.py
    app/modules/marketplace/application/storefront_handler.py
    tests/marketplace/test_browse_handler.py
  </files>
  <action>
    Products: search, category with its sub-categories, price range on the shown price, in stock, sort, pagination.
    Animals: search, type, breed, price, minimum milk, lactation, location, sort, pagination.
    Detail read models with sizes and every public animal field, and related listings. Sold animals open by URL but stay out of lists.

    AVOID: exposing the exact stock count, because "only 3 left" below the low stock level is all a shopper needs.
    AVOID: exposing seller ids on public read models, because customers deal with the store.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_browse_handler.py -q</verify>
  <done>Each filter, each sort and pagination are proven on a real database, with hidden listings still hidden.</done>
</task>

<task type="auto">
  <name>Enquiries</name>
  <files>
    app/modules/marketplace/domain/contact.py
    app/modules/marketplace/domain/entities.py
    app/modules/marketplace/infrastructure/repository.py
    app/modules/marketplace/application/storefront_handler.py
    app/modules/marketplace/application/handler.py
    tests/marketplace/test_browse_handler.py
  </files>
  <action>
    Public create with Indian phone validation and normalisation; title snapshot; repeat from the same phone while one is still open
    adds nothing. Seller side: scoped list and status plus notes update.

    AVOID: telling a bot its honeypot was seen, because it would simply adapt.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace -q</verify>
  <done>Sold, unknown, duplicate and invalid cases are proven; a second seller cannot read or change another's enquiry.</done>
</task>

## Must-Haves
- [ ] Filters proven individually
- [ ] Enquiry abuse cases covered
- [ ] Seller scope holds

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in tests
