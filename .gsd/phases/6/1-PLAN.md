---
phase: 6
plan: 1
wave: 1
---

# Plan 6.1: Formula Sheet Specification, Repository & Export Engine

## Objective
Define the column specification and data structures for Formula Rate Charts, implement the data access repository for formula configurations, and build the `FormulaExportProcessor` that exports both the formula parameters and an expanded 2D pricing matrix preview into Excel.

## Context
- `.gsd/SPEC.md`
- `.gsd/REQUIREMENTS.md` (REQ-20)
- `app/modules/dataexchange/domain/sheets.py`
- `app/modules/dataexchange/domain/enums.py`
- `app/modules/ratechart/infrastructure/models.py` (`RateFormulaConfigModel`, `RateChartModel`)
- `app/modules/ratechart/infrastructure/repository.py` (`resolve_formula_rate`)

## Tasks

<task type="auto">
  <name>Task 1: Domain Enums & Column Specification</name>
  <files>
    app/modules/dataexchange/domain/enums.py
    app/modules/dataexchange/domain/sheets.py
  </files>
  <action>
    1. In `app/modules/dataexchange/domain/enums.py`:
       - Add `FORMULA_EXPORT = 7` and `FORMULA_IMPORT = 8` to `ExcelJobKind`.
       - Update `ExcelJobKind.is_import` to include `FORMULA_IMPORT`.
    2. In `app/modules/dataexchange/domain/sheets.py`:
       - Define `FORMULA_SHEET` with `ColumnSpec`:
         - `animal_type`: Enum ("COW", "BUFFALO"), required.
         - `standard_fat`: Float, min 0.1, max 20.0, required.
         - `standard_snf`: Float, min 0.1, max 20.0, required.
         - `standard_rate`: Float, min 0.1, required.
         - `fat_percentage`: Float, min 0.0, max 100.0, required.
         - `snf_percentage`: Float, min 0.0, max 100.0, required.
       - Define `FORMULA_KEYS = ("animal_type", "standard_fat", "standard_snf", "standard_rate", "fat_percentage", "snf_percentage")`.
  </action>
  <verify>
    .venv\Scripts\python.exe -c "from app.modules.dataexchange.domain.enums import ExcelJobKind; assert ExcelJobKind.FORMULA_EXPORT == 7; assert ExcelJobKind.FORMULA_IMPORT.is_import; from app.modules.dataexchange.domain.sheets import FORMULA_SHEET; assert len(FORMULA_SHEET.columns) == 6"
  </verify>
  <done>
    `FORMULA_SHEET` and `ExcelJobKind` members exist, validate cleanly, and are importable.
  </done>
</task>

<task type="auto">
  <name>Task 2: Formula Exchange Repository & Export Processor</name>
  <files>
    app/modules/dataexchange/infrastructure/formula_repository.py
    app/modules/dataexchange/application/formula_export.py
  </files>
  <action>
    1. Create `app/modules/dataexchange/infrastructure/formula_repository.py`:
       - `FormulaExchangeRepository`:
         - `get_formula_config(chart_id: UUID) -> RateFormulaConfigModel | None`
         - `save_formula_config(chart_id: UUID, config_data: dict) -> RateFormulaConfigModel`
         - `get_chart_info(chart_id: UUID) -> RateChartModel | None`
    2. Create `app/modules/dataexchange/application/formula_export.py`:
       - `FormulaExportProcessor(ExchangeProcessor)`:
         - Handles `ExcelJobKind.FORMULA_EXPORT`.
         - Writes `Formula Config` sheet with COW and BUFFALO parameters.
         - Generates a `Pricing Matrix (Preview)` sheet displaying calculated rates for FAT (3.0 to 10.0%, step 0.2) vs SNF (7.5 to 10.0%, step 0.2) using the exact dairy formula.
  </action>
  <verify>
    .venv\Scripts\python.exe -c "from app.modules.dataexchange.application.formula_export import FormulaExportProcessor; from app.modules.dataexchange.infrastructure.formula_repository import FormulaExchangeRepository; print('Formula export imports cleanly')"
  </verify>
  <done>
    Repository and export processor implemented with slots, proper typing, and clean separation.
  </done>
</task>

<task type="auto">
  <name>Task 3: Template Generator & Worker Registration</name>
  <files>
    app/modules/dataexchange/application/templates.py
    app/modules/configurator.py
  </files>
  <action>
    1. In `app/modules/dataexchange/application/templates.py`:
       - Add `formula_template_path(storage_root: Path) -> Path`:
         - Creates `formula_template.xlsx` cached under `storage_root / "templates"`.
         - Pre-fills standard example rows:
           - COW: Std FAT 4.0, Std SNF 8.5, Std Rate 35.0, FAT% 60.0, SNF% 40.0
           - BUFFALO: Std FAT 6.5, Std SNF 9.0, Std Rate 48.0, FAT% 60.0, SNF% 40.0
    2. In `app/modules/configurator.py`:
       - Register `FormulaExchangeRepository` in IoC container.
       - Register `FormulaExportProcessor` in `ExchangeWorker`.
  </action>
  <verify>
    .venv\Scripts\python.exe -c "from app.modules.dataexchange.application.templates import formula_template_path; from pathlib import Path; p = formula_template_path(Path('exchange_data')); assert p.exists(); print('Template created:', p)"
  </verify>
  <done>
    Template generates cleanly and export processor is registered in the exchange worker.
  </done>
</task>

## Success Criteria
- [ ] `ExcelJobKind.FORMULA_EXPORT` and `FORMULA_IMPORT` registered.
- [ ] `FORMULA_SHEET` defines the 6 configuration columns with validation rules.
- [ ] Export processor generates both configuration rows and preview rate grid.
- [ ] Pre-formatted official Excel template generated on demand.
