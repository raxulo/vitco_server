---
phase: 3
plan: 1
wave: 1
depends_on: []
files_modified:
  - app/modules/dataexchange/domain/sheets.py
  - app/modules/dataexchange/infrastructure/vlcc_repository.py
  - app/modules/dataexchange/application/vlcc_export.py
  - app/modules/dataexchange/application/templates.py
  - tests/dataexchange/test_vlcc_export.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "VLCC_SHEET declares 44 columns across VLCC, User, Address, Bank, Settings, and Milk Quality; vlcc_code, uic_code, name, user name, mobile are required"
    - "ReceiptSize dropdown in Settings includes SMALL, MEDIUM, LARGE, EXTRA_LARGE"
    - "Export of one owner writes every non-deleted VLCC owned by that owner (and no other owner's) ordered by vlcc_code, with all joined relations"
    - "Export pages with keyset pagination ((vlcc_code, id) > (...)) and writes rows in worker threads"
    - "The VLCC template is built once and served from a cached file"
  artifacts:
    - "VlccExportProcessor (kind VLCC_EXPORT) usable by the exchange worker"
  key_links:
    - "Requirements: REQ-12, REQ-13; DECISIONS: 004, 007, 011, 012"
---

# Plan 3.1: VLCC Sheet Spec (44 Columns), Template & Export

<objective>
Declare the 44-column VLCC sheet spec, build the VLCC bulk repository for export queries, implement the export processor, and add the cached template builder.

Output: `VLCC_SHEET`, `VlccExchangeRepository` (export queries; bulk upsert in 3.2), `VlccExportProcessor`, cached VLCC template.
</objective>

<context>
- .gsd/phases/3/RESEARCH.md
- .gsd/REQUIREMENTS.md (REQ-12, REQ-13)
- app/modules/dataexchange/domain/columns.py, domain/sheets.py
- app/modules/vlcc/infrastructure/models.py
- app/modules/administration/infrastructure/models.py (UserModel)
- app/modules/common/address/infrastructure/models.py, common/bank/infrastructure/models.py
- app/modules/common/settings/infrastructure/models.py (SettingsModel, ReceiptSize)
- app/modules/common/milk_quality/infrastructure/models.py (MilkQualityConfigModel)
</context>

<tasks>

<task type="auto">
  <name>VLCC sheet specification (44 columns)</name>
  <files>
    app/modules/dataexchange/domain/sheets.py
  </files>
  <action>
    Define `VLCC_SHEET` in `app/modules/dataexchange/domain/sheets.py` with 44 columns in order:
    1. Entity (10 cols):
       - vlcc_code* (CODE, max 30, required=True, example="V001")
       - uic_code* (CODE, max 50, required=True, example="UIC001")
       - name* (TEXT, max 150, required=True, example="Gokul Dairy Center")
       - contact_person (TEXT, max 150)
       - entry_mode (ENUM: MANUAL/AUTOMATIC, default note MANUAL)
       - route_code (INT)
       - soc_percentage (FLOAT, min 0.0, max 100.0, example="0.0")
       - farmer_enabled (BOOL, default YES)
       - is_active (BOOL, default YES)
       - assigned_chart_rank (INT, min 1, max 100, default 1)
    2. User (4 cols):
       - name* (TEXT, max 150, required=True, example="Gokul Operator")
       - mobile* (MOBILE, required=True, example="9876543210")
       - email (EMAIL, example="gokul@dairy.local")
       - password (PASSWORD, import_only=True, min 6, max 128)
    3. Address (4 cols):
       - address_line, city, state, pincode (PINCODE)
    4. Bank (5 cols):
       - account_holder, bank_name, account_number (ACCOUNT_NUMBER), ifsc_code (IFSC), upi_id
    5. Settings (13 cols):
       - analyzer_type (ENUM: TYPE_A, TYPE_B, TYPE_C, TYPE_D)
       - analyzer_collection_mode (ENUM: MANUAL, AUTOMATIC)
       - weight_unit (ENUM: LITER, KILOGRAM)
       - weight_collection_mode (ENUM: MANUAL, AUTOMATIC)
       - auto_tare_enabled (BOOL)
       - morning_collection_start (TIME, example="06:00")
       - morning_collection_end (TIME, example="10:00")
       - evening_collection_start (TIME, example="12:00")
       - evening_collection_end (TIME, example="22:00")
       - receipt_size (ENUM: SMALL, MEDIUM, LARGE, EXTRA_LARGE)
       - printer_type (ENUM: NONE, THERMAL, DOT_MATRIX, LASER)
       - printer_enabled (BOOL)
       - cattle_type (ENUM: COW_AND_BUFFALO, COW_ONLY, BUFFALO_ONLY)
    6. Milk Quality Config (8 cols):
       - cow_min_fat, cow_max_fat, cow_min_snf, cow_max_snf (FLOAT, default 0.0)
       - buffalo_min_fat, buffalo_max_fat, buffalo_min_snf, buffalo_max_snf (FLOAT, default 0.0)
    All columns must have clean section assignment, examples, and help text.
  </action>
  <verify>.venv\Scripts\python.exe -c "from app.modules.dataexchange.domain.sheets import VLCC_SHEET as s; print(len(s.columns), [c.key for c in s.columns if c.required])" → `44 ['vlcc_code', 'uic_code', 'name', 'name', 'mobile']` (or distinct keys)</verify>
  <done>VLCC_SHEET declared with 44 columns, choices, and validators.</done>
</task>

<task type="auto">
  <name>VLCC bulk repository (export side) and export processor</name>
  <files>
    app/modules/dataexchange/infrastructure/vlcc_repository.py
    app/modules/dataexchange/application/vlcc_export.py
    app/modules/dataexchange/application/templates.py
  </files>
  <action>
    1. Create `VlccExchangeRepository(database)`:
       - `export_page(owner_id, after: tuple[str, UUID] | None, limit) -> list[Row]`: Core select of all 44 fields joined across `vlcc_master`, `users`, `addresses`, `bank_accounts`, `settings`, `milk_quality_configs` where `vlcc_master.created_by = :owner_id AND vlcc_master.is_deleted = false`. Keyset order `(vlcc_master.vlcc_code, vlcc_master.id) > (:code, :id)`.
       - `count_export(owner_id) -> int`.
    2. Create `VlccExportProcessor(database, repository, page_size=1000)`:
       - Registered with kind `VLCC_EXPORT`.
       - Pulls `target_id` as the owner UUID from `ctx.job`.
       - Keyset-paginates and streams rows to `XlsxSheetWriter(result.xlsx, VLCC_SHEET)`.
    3. Update `templates.py`:
       - Add `vlcc_template_path(storage)` creating `storage.root / "templates" / f"vlccs-v{TEMPLATE_VERSION}.xlsx"` cached atomically.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_vlcc_export.py -q → green</verify>
  <done>Export processor streams VLCCs of selected owner; template builder cached.</done>
</task>

<task type="auto">
  <name>VLCC export tests on a real database</name>
  <files>
    tests/dataexchange/test_vlcc_export.py
  </files>
  <action>
    Add automated tests verifying:
    - 44 columns exported in exact order with correct headers and sections.
    - Export only includes non-deleted VLCCs of the specified owner.
    - Joined relations (user, address, bank, settings, milk quality) correctly mapped to cells.
    - Enums and Times formatted as expected by the spec.
    - Keyset pagination works across multiple pages.
    - Template builds and caches correctly.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_vlcc_export.py -q → green</verify>
  <done>All export and template tests pass.</done>
</task>

</tasks>

<verification>
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange/test_vlcc_export.py -q` passes
</verification>
