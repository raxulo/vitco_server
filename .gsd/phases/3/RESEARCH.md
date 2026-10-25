---
phase: 3
researched_at: 2026-10-25
discovery_level: 1
---

# Phase 3 Research — VLCC Excel Exchange

## Objective
How do we export, template, and upsert-import VLCCs owned by one selected Admin, Sub Admin, or MCC at high throughput without violating hierarchy constraints, role permissions, or SQLite concurrency limits?

## Discovery Level
**Level 1** — internal codebase patterns + schema inspection (`VlccModel`, `UserModel`, `AddressModel`, `BankAccountModel`, `SettingsModel`, `MilkQualityConfigModel`, and `Hierarchy`).

---

## Findings

### 1. The 44 Columns Layout
The specification calls for 44 columns across 6 sections:

1. **VLCC Entity (10 columns)**:
   - `vlcc_code*` (Code, max 30) — Unique match key within owner's VLCCs.
   - `uic_code*` (Code, max 50) — Unique Identifier / Company code.
   - `name*` (Text, max 150) — Center / VLCC name.
   - `contact_person` (Text, max 150).
   - `entry_mode` (Enum: MANUAL / AUTOMATIC).
   - `route_code` (Int: Route master code).
   - `soc_percentage` (Float: SOC / deduction percentage, default 0.0).
   - `farmer_enabled` (Bool: YES / NO, default YES).
   - `is_active` (Bool: YES / NO, default YES).
   - `assigned_chart_rank` (Int: 1..100, default 1).

2. **User (4 columns)**:
   - `name*` (Text, max 150) — Login user's display name.
   - `mobile*` (Mobile, 10 digits) — Unique across all users.
   - `email` (Email) — Unique across all users. Empty on insert = auto-generated (`vlcc_<code>_<hex6>@dairy.local`).
   - `password` (Password, import-only) — Empty on insert = `Vitco@123`. Never exported.

3. **Address (4 columns)**:
   - `address_line` (Text, max 255)
   - `city` (Text, max 100)
   - `state` (Text, max 100)
   - `pincode` (Pincode, 6 digits)

4. **Bank (5 columns)**:
   - `account_holder` (Text, max 150) — Empty on insert defaults to user name.
   - `bank_name` (Text, max 150)
   - `account_number` (Account number)
   - `ifsc_code` (IFSC code)
   - `upi_id` (Text, max 100)

5. **Settings (13 columns)**:
   - `analyzer_type` (Enum: TYPE_A, TYPE_B, TYPE_C, TYPE_D; default TYPE_A)
   - `analyzer_collection_mode` (Enum: MANUAL, AUTOMATIC; default MANUAL)
   - `weight_unit` (Enum: LITER, KILOGRAM; default LITER)
   - `weight_collection_mode` (Enum: MANUAL, AUTOMATIC; default MANUAL)
   - `auto_tare_enabled` (Bool: YES / NO; default NO)
   - `morning_collection_start` (Time: HH:MM, default 06:00)
   - `morning_collection_end` (Time: HH:MM, default 10:00)
   - `evening_collection_start` (Time: HH:MM, default 12:00)
   - `evening_collection_end` (Time: HH:MM, default 22:00)
   - `receipt_size` (Enum: SMALL, MEDIUM, LARGE, EXTRA_LARGE; default SMALL)
   - `printer_type` (Enum: NONE, THERMAL, DOT_MATRIX, LASER; default NONE)
   - `printer_enabled` (Bool: YES / NO; default NO)
   - `cattle_type` (Enum: COW_AND_BUFFALO, COW_ONLY, BUFFALO_ONLY; default COW_AND_BUFFALO)

6. **Milk Quality Config (8 columns)**:
   - `cow_min_fat`, `cow_max_fat`, `cow_min_snf`, `cow_max_snf` (Float, default 0.0)
   - `buffalo_min_fat`, `buffalo_max_fat`, `buffalo_min_snf`, `buffalo_max_snf` (Float, default 0.0)

**Total Columns = 10 + 4 + 4 + 5 + 13 + 8 = 44 columns.**

---

### 2. Owner Selection & Role Scoping (REQ-12)
- **Super Admin**: Can choose any Admin or Sub Admin as owner, or "Self" (`owner_id = super_admin.id`).
- **Admin**: Can choose any of its Sub Admins, or itself (`owner_id = admin.id`).
- **Sub Admin**: Locked to itself (`owner_id = sub_admin.id`, `locked = True`).
- **MCC**: Locked to itself (`owner_id = mcc_user.id`, `locked = True`).
- **VLCC / Farmer**: Not allowed (403 Forbidden).

### 3. Upsert Semantics (REQ-14, REQ-15, REQ-16)
- Match key: `(created_by, vlcc_code)`.
- Existing `vlcc_code` for that owner updates the VLCC, User, Address, BankAccount, Settings, and MilkQualityConfig records.
- Blank cells on update keep the stored value (DECISION-003).
- Blank settings / milk quality cells on insert take standard defaults (REQ-16).
- New VLCC receives `created_by = selected_owner_id`.
- Code conflict check (REQ-15): A new VLCC code cannot conflict with any code in the owner's hierarchy line via `Hierarchy.code_conflict`.

### 4. Database Architecture & Multi-Table Writes
One VLCC involves 6 tables:
1. `users` (Role = `Role.VLCC` = 5)
2. `addresses` (`user_id = users.id`)
3. `bank_accounts` (`user_id = users.id`)
4. `settings` (`user_id = users.id` via VlccModel `settings_id`)
5. `milk_quality_configs` (`user_id = users.id`)
6. `vlcc_master` (`user_id`, `address_id`, `bank_account_id`, `settings_id`, `milk_quality_config_id`, `created_by = owner_id`)

Using Core bulk SQL:
- Pre-fetch existing VLCCs for the owner, users by email/mobile, and code conflicts in the hierarchy line.
- Insert/update users, addresses, bank accounts, settings, and milk quality configs in batches, linking primary keys.
- Write lock budget: target ≤ 250ms per transaction using adaptive batching.

---

## Recommendations for Phase 3 Plans
1. **Plan 3.1: VLCC Column Spec (44 Columns), Template & Export**
   - Define `VLCC_SHEET` with 44 columns, choices, validation rules, section styling.
   - Implement `VlccBulkRepository` for export keyset pagination and joined relations.
   - Implement `VlccExportProcessor` and template caching.
2. **Plan 3.2: VLCC Import Pipeline**
   - Implement `VlccImportProcessor` with pre-checks, hierarchy code conflict validation, deduplication, password hashing, and bulk multi-table upsert.
   - Register processors in worker engine.
3. **Plan 3.3: Owner Scope, Options API & VLCC Endpoints**
   - Implement `OwnerScopeService` / options endpoint returning items, locked state, and default owner.
   - Expose `/api/v1/excel/vlccs/export`, `/import`, `/template`, `/options`.
   - Comprehensive unit and integration verification tests.
