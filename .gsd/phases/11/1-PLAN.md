---
phase: 11
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/marketplace/domain/merchandising.py
  - app/modules/marketplace/domain/enums.py
  - app/modules/marketplace/domain/exceptions.py
  - app/modules/marketplace/domain/links.py
  - app/modules/marketplace/domain/irepository.py
  - app/modules/marketplace/infrastructure/merchandising_repository.py
  - app/modules/marketplace/application/command.py
  - app/modules/marketplace/application/merchandising_handler.py
  - app/modules/configurator.py
  - app/modules/dependencies.py
  - tests/marketplace/test_merchandising_handler.py
must_haves:
  - Only Super Admin changes storefront content and settings
  - A link with an unsafe scheme is refused
  - A banner is live only inside its window, at its placement, when active
gap_closure: false
---

# Plan 11.1: Merchandising Use Cases

## Objective
Tested use cases for banners, home sections, trending tags and store settings (REQ-34, REQ-35), so the store can be run without code changes.

## Context
- .gsd/phases/10/RESEARCH.md
- app/modules/marketplace/application/handler.py

## Tasks

<task type="auto">
  <name>Domain rules</name>
  <files>
    app/modules/marketplace/domain/entities.py
    app/modules/marketplace/domain/links.py
    tests/marketplace/test_merchandising_handler.py
  </files>
  <action>
    Entities: Banner, HomeSection, TrendingTag, StoreSettings, each with `problems()`. `Banner.state(now)` returns live, scheduled,
    expired or off. `is_safe_link` allows site paths and http(s) URLs only. Pincodes are 6 digits; phone numbers 10 to 15 digits.

    AVOID: accepting `//host` or `javascript:` links, because these values render as links for every customer.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_merchandising_handler.py -q</verify>
  <done>Unsafe links, reversed banner windows and bad pincodes are refused with a message per field.</done>
</task>

<task type="auto">
  <name>Repository and handler</name>
  <files>
    app/modules/marketplace/domain/irepository.py
    app/modules/marketplace/infrastructure/merchandising_repository.py
    app/modules/marketplace/application/merchandising_handler.py
    app/modules/configurator.py
    app/modules/dependencies.py
  </files>
  <action>
    `MarketplaceMerchandisingHandler`, Super Admin only: save and delete banners with images; save, move and delete home sections,
    where only category sections can be deleted and the built-in ones can only be hidden; save and delete trending tags; read
    and save settings. Moving a section renumbers all sections.

    AVOID: deleting built-in sections, because the home page would lose them with no way to restore them.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace -q</verify>
  <done>Tests on a real database prove access, banner window, section order, the built-in delete refusal and the settings round trip.</done>
</task>

## Must-Haves
- [ ] Super Admin only
- [ ] Unsafe links refused
- [ ] Banner window enforced

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in tests
