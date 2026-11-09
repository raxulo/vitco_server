---
phase: 15
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/web/templates/layouts/store.html
  - app/web/templates/pages/store/
  - app/web/storefront/seo_controller.py
  - app/web/router.py
  - app/bootstrap/middleware.py
  - app/modules/marketplace/infrastructure/storefront_repository.py
  - app/web/static/css/
  - tests/marketplace/test_seo.py
  - .gsd/phases/15/VERIFICATION.md
  - .gsd/phases/15/RELEASE.md
must_haves:
  - Search engines get canonical URLs, sitemap, robots and structured data; private pages are noindex
  - No serious or critical axe findings on store and Control Center pages
  - Home and listing p95 under 300 ms with 1,000 listings
gap_closure: false
---

# Plan 15.2: SEO, Audits & Release

## Objective
Make the store findable, prove accessibility and speed, and hand over a release checklist (NFR-15, NFR-16, NFR-17).

## Context
- .gsd/phases/15/1-PLAN.md
- .gsd/REQUIREMENTS.md
- .gsd/STATE.md (concerns)

## Tasks

<task type="auto">
  <name>SEO</name>
  <files>
    app/web/templates/layouts/store.html
    app/web/templates/pages/store/
    app/web/storefront/seo_controller.py
    tests/marketplace/test_seo.py
  </files>
  <action>Canonical, Open Graph, JSON-LD on details, `robots.txt`, `sitemap.xml`, noindex on cart, checkout, tracking, search and 404.</action>
  <verify>.venv\Scripts\python.exe -m pytest tests/marketplace/test_seo.py -q</verify>
  <done>Only live listings enter the sitemap; hostile titles stay inert inside JSON-LD.</done>
</task>

<task type="auto">
  <name>Accessibility and performance audits</name>
  <files>app/web/static/css/store.css, app/web/static/css/marketplace-admin.css, .gsd/phases/15/VERIFICATION.md</files>
  <action>
    axe-core in real Chrome on store and panel pages, keyboard walk, then fix what they find. Real server with 1,000 listings:
    concurrent page timings, then parallel orders. Security pass over the new code. Full suite including the throughput test.

    AVOID: adding axe or any audit tool to the project, because it is only a check.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest -q</verify>
  <done>Measured results recorded, including anything that did not meet its target.</done>
</task>

<task type="auto">
  <name>Release checklist and commit message</name>
  <files>.gsd/phases/15/RELEASE.md, .gsd/ROADMAP.md, .gsd/STATE.md, .gsd/REQUIREMENTS.md</files>
  <action>
    Audit every milestone must-have. Write what must be checked on the server, including legacy tables and the old mobile API.
    Present the one milestone commit message for the user's approval.

    AVOID: committing or dropping legacy tables without the user's approval.
  </action>
  <verify>Every requirement of the milestone has a status</verify>
  <done>Release checklist and commit message ready for the user.</done>
</task>

## Must-Haves
- [ ] SEO complete
- [ ] Audits measured and recorded
- [ ] Release checklist delivered

## Success Criteria
- [ ] All tasks verified passing
- [ ] No regressions in the full test suite
