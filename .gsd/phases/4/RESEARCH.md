---
phase: 4
researched_at: 2026-10-25
discovery_level: 1
---

# Phase 4 Research — Prodata Rate-Chart Excel Exchange

## Objective
How do we export the rows of a Prodata rate chart visible to the user in row order (REQ-17), and import rows from Excel to replace all rows of an existing chart in one atomic transaction with strict validation (fat_min > fat_max, overlapping FAT/SNF ranges) rejecting the whole file if invalid (REQ-18, DECISION-005)?

## Discovery Level
**Level 1** — internal codebase patterns + schema inspection (`RateChartModel`, `ProdataRateRowModel`, `Hierarchy.shared_visible`, `Hierarchy.shared_modifiable`).

---

## Findings

### 1. Sheet Spec & Column Layout (9 Columns)
In accordance with `2-PLAN.md` and `ProdataRateRowModel`, the sheet has 9 columns all under `Section.RATE`:

1. `row_number` (`Row No`): ColumnKind.INT, min_value=1, example="1", help="Row sequence number. If blank, auto-assigned from row order."
2. `fat_min` (`FAT Min*`): ColumnKind.FLOAT, required=True, min_value=0.0, max_value=20.0, example="3.0", help="Minimum FAT percentage."
3. `fat_max` (`FAT Max*`): ColumnKind.FLOAT, required=True, min_value=0.0, max_value=20.0, example="4.5", help="Maximum FAT percentage."
4. `snf_min` (`SNF Min`): ColumnKind.FLOAT, min_value=0.0, max_value=20.0, example="7.0", help="Minimum SNF percentage (optional)."
5. `snf_max` (`SNF Max`): ColumnKind.FLOAT, min_value=0.0, max_value=20.0, example="9.0", help="Maximum SNF percentage (optional)."
6. `fat_rate_per_kg` (`FAT Rate / KG`): ColumnKind.FLOAT, min_value=0.0, example="350.0", help="Rate per kg FAT (rupees)."
7. `snf_rate_per_kg` (`SNF Rate / KG`): ColumnKind.FLOAT, min_value=0.0, example="250.0", help="Rate per kg SNF (rupees)."
8. `snf_cutoff` (`SNF Cut-off`): ColumnKind.FLOAT, min_value=0.0, max_value=20.0, example="8.0", help="SNF threshold below which deduction applies."
9. `snf_deduction` (`SNF Deduction`): ColumnKind.FLOAT, min_value=0.0, example="2.0", help="Deduction rate per unit below cutoff."

### 2. Validation Rules & Overlap Detection (REQ-18)
Unlike Farmer and VLCC imports where valid rows are committed in batches and bad rows are discarded individually, **Prodata import is an atomic all-or-nothing replace** (DECISION-005).

If ANY row in the workbook fails validation:
- The entire import is rejected.
- Zero rows are written or deleted in `prodata_rate_rows`.
- A discarded-rows Excel report is generated with the rejected rows, plus `Row No` and `Reason`.
- The job completes with `inserted = 0, updated = 0, discarded = <count of failed rows>`.

Validation checks:
1. **Required Fields**: `fat_min` and `fat_max` must be non-null and numeric.
2. **Bounds & Range Inversion**:
   - `0.0 <= fat_min <= 20.0` and `0.0 <= fat_max <= 20.0`.
   - `fat_min <= fat_max`: If `fat_min > fat_max`, error: `f"FAT Min ({fat_min}) exceeds FAT Max ({fat_max})"`.
   - If `snf_min` and `snf_max` are both provided: `0.0 <= snf_min <= 20.0` and `0.0 <= snf_max <= 20.0`.
   - `snf_min <= snf_max`: If `snf_min > snf_max`, error: `f"SNF Min ({snf_min}) exceeds SNF Max ({snf_max})"`.
3. **Rates & Deductions**:
   - `fat_rate_per_kg >= 0.0`, `snf_rate_per_kg >= 0.0`, `snf_cutoff >= 0.0`, `snf_deduction >= 0.0`.
4. **Interval Overlap Validation**:
   - Two rows $A$ and $B$ within the same chart overlap if their FAT ranges overlap:
     $\max(A.\text{fat\_min}, B.\text{fat\_min}) < \min(A.\text{fat\_max}, B.\text{fat\_max})$ (or exact boundary match: $A.\text{fat\_min} == B.\text{fat\_min} \land A.\text{fat\_max} == B.\text{fat\_max}$).
   - If both rows define SNF ranges ($A.\text{snf\_min} \ne \text{None} \land B.\text{snf\_min} \ne \text{None}$):
     They only conflict if their SNF ranges ALSO overlap:
     $\max(A.\text{snf\_min}, B.\text{snf\_min}) < \min(A.\text{snf\_max}, B.\text{snf\_max})$.
     If either row has no SNF range (wildcard/all SNF), the FAT overlap alone constitutes a conflict.
   - When an overlap occurs, row $B$ is flagged: `f"Range overlaps with row {A.row_no} (FAT {A.fat_min}-{A.fat_max})"` (or including SNF if applicable).

### 3. Atomic Replacement in SQLite / PostgreSQL
When all rows pass validation:
- In a single database transaction:
  ```python
  async with self._database.transaction():
      await session.execute(
          delete(ProdataRateRowModel).where(ProdataRateRowModel.rate_chart_id == chart_id)
      )
      await session.execute(
          insert(ProdataRateRowModel),
          insert_params
      )
  ```
- No partial state is ever visible to milk collection queries.

### 4. Chart Selection & Role Scoping (REQ-17, REQ-18)
- Target selection uses `RateChartScope`:
  - **Export** (`resolve_for_export`): Checks chart exists, is `RateChartType.PRODATA` (value 2), and is visible to the logged-in user via `Hierarchy.shared_visible(user, RateChartModel.created_by)`.
  - **Import** (`resolve_for_import`): Checks chart exists, is `RateChartType.PRODATA`, and is modifiable by the logged-in user via `Hierarchy.shared_modifiable(user, RateChartModel.created_by)`.
  - **Options** (`GET /api/v1/excel/prodata/options`): Returns all Prodata charts visible to the user, annotated with `can_modify: bool`.
