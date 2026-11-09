---
phase: 9
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/marketplace/__init__.py
  - app/modules/marketplace/domain/__init__.py
  - app/modules/marketplace/domain/enums.py
  - app/modules/marketplace/domain/exceptions.py
  - app/modules/marketplace/domain/policy.py
  - app/modules/marketplace/domain/slug.py
  - app/modules/marketplace/infrastructure/__init__.py
  - app/modules/marketplace/infrastructure/models.py
  - tests/marketplace/__init__.py
  - tests/marketplace/test_domain.py
  - tests/marketplace/test_models.py
must_haves:
  - Every REQ-30 to REQ-47 data field has a home in a mkt_ table
  - No marketplace table name collides with a legacy table
  - The database itself rejects negative stock and a price above MRP
gap_closure: false
---

# Plan 9.1: Domain Rules & Schema

## Objective
Create the pure domain rules (enums, exceptions, seller policy, slugs) and the full `mkt_*` schema that later phases build on.

## Context
- .gsd/phases/9/RESEARCH.md
- .gsd/REQUIREMENTS.md
- AGENTS.md section 5
- app/modules/masters/units/

## Tasks

<task type="auto">
  <name>Domain rules</name>
  <files>
    app/modules/marketplace/domain/enums.py
    app/modules/marketplace/domain/exceptions.py
    app/modules/marketplace/domain/policy.py
    app/modules/marketplace/domain/slug.py
    tests/marketplace/test_domain.py
  </files>
  <action>
    1. Enums: product status, animal status, gender, pregnancy status, enquiry status, order status with an allowed
       transition map, payment method, payment status, banner placement, home section type.
    2. Exceptions subclassing `ApplicationException`, with `code`, `message` and `status_code`.
    3. `SellerPolicy`: `SELLER_ROLES`, `can_sell(role)`, `ensure_can_sell(role)`.
    4. `slugify(text)`: lowercase ASCII, hyphens; Hindi or other text without Latin letters falls back to a short random id.

    AVOID: importing FastAPI or SQLAlchemy in `domain/`, because AGENTS.md forbids it.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_domain.py -q</verify>
  <done>
    Tests prove: only Super Admin may sell and every other role raises; `cancelled` and `delivered` orders cannot
    move on; `Desi Ghee 1 L!` becomes `desi-ghee-1-l`; non-Latin titles still give a non-empty slug.
  </done>
</task>

<task type="auto">
  <name>SQLAlchemy models</name>
  <files>
    app/modules/marketplace/infrastructure/models.py
    tests/marketplace/test_models.py
  </files>
  <action>
    1. Model all 15 tables in RESEARCH.md with `Base`, `UUIDMixin`, `AuditMixin`, plus `SoftDeleteMixin` on products and animals.
    2. Timestamps come from the mixins. Enums use `native_enum=False`, as the rest of the app does.
    3. Add indexes for the listing queries: status + category, status + type, featured, trending, seller, order phone and reference.
    4. Add check constraints for money, stock, percentages and non-negative animal numbers.

    AVOID: JSON image columns, because galleries need ordering and a primary image.
    AVOID: reusing any legacy table name, because `create_all` would silently keep the old shape (DECISION-015).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_models.py -q</verify>
  <done>
    Real-DB tests prove: all 15 tables exist; negative stock, price above MRP and negative price raise
    `IntegrityError`; deleting a product removes its variants and images; a duplicate slug is rejected; deleting
    a user who owns a product is refused.
  </done>
</task>

## Must-Haves
- [ ] Domain has no framework imports
- [ ] 15 `mkt_` tables, no legacy name reused
- [ ] Constraints enforced by the database, proven by tests

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in tests
