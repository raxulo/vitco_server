---
phase: 2
plan: 1
completed_at: 2026-10-25
---

# Summary: Farmer Sheet, Bulk Repository & Export

## Results
- 3 tasks completed; 6 new tests, module suite 188 passed

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | `FARMER_SHEET` (18 columns) + `ensure_indexes` (`ix_users_email_lower`) | phase commit (pending) | ✅ |
| 2 | `FarmerExchangeRepository` (count + keyset page), `FarmerExportProcessor` (DB page N+1 overlaps xlsx write of page N), cached templates | phase commit (pending) | ✅ |
| 3 | Export tests on real rows | phase commit (pending) | ✅ |

## Deviations Applied
- [Design, faster] Keyset is `farmer_code > :last` alone. `(vlcc_id, farmer_code)` is UNIQUE, so no `id` tie-break is needed and the page is a pure index range scan.
- [Design] The template version is a hash of the sheet spec, so changing a column rebuilds the cached file automatically.
- [Rule 3 - Blocking] The test harness now imports `app.modules.configurator` (all models, like the API) before `create_all`, because VLCC rows need the `settings` / `milk_quality_configs` tables.
- [Test infra] `tests/dataexchange/factories.py`: bulk Core factories for VLCCs and farmers, plus a real `JobContext`.

## Files Changed
- `app/modules/dataexchange/domain/sheets.py`, `infrastructure/indexes.py`, `infrastructure/farmer_repository.py`, `application/farmer_export.py`, `application/templates.py` — new
- `tests/conftest.py` — registers every model
- `tests/dataexchange/factories.py`, `tests/dataexchange/test_farmer_export.py` — new

## Verification
- 2,500 farmers of VLCC A exported in code order across 3 pages; VLCC B's farmers and soft-deleted farmers excluded; mobile / 16-digit account number round-trip as text; enum / bool as labels: ✅ (REQ-07)
- Farmer without address / bank → blank cells; header has no Password; Farmers + Instructions sheets; empty VLCC → header-only file: ✅
- `ensure_indexes` twice → one `ix_users_email_lower`, the query plan uses it: ✅
- Template built once, reused (same mtime), header-only: ✅
