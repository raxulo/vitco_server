---
phase: 1
plan: 2
wave: 2
depends_on: [1]
files_modified:
  - app/modules/dataexchange/domain/columns.py
  - app/modules/dataexchange/infrastructure/xlsx.py
  - tests/dataexchange/test_columns.py
  - tests/dataexchange/test_xlsx.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "One SheetSpec produces the template, the export rows, the import parsing and the Instructions sheet"
    - "Headers match by normalised name: 'Farmer Code *', 'farmer code' and 'FARMER_CODE' map to the same column; column order does not matter; unknown columns are ignored"
    - "A missing required header is reported once, before any row is processed"
    - "Mobile 9876543210 read back from Excel as int / float / str is the string '9876543210'; a 16-digit account number survives a write → read round-trip unchanged"
    - "A 100,000-row write + read round-trip runs with flat memory (tracemalloc peak < 60 MB)"
    - "An export larger than the per-sheet limit continues on sheets named '<Name> (2)', '<Name> (3)', each with the header row; the reader returns rows from every sheet whose header matches, with correct sheet + row numbers"
    - "Reading stops after 1,000 consecutive empty rows, so a sheet formatted down to row 1,048,576 is not scanned to the end"
  artifacts:
    - "Written workbook: row 1 header, frozen pane A2, AutoFilter, '*' on required headers, section fill colours, '@' format on text columns, list validations on enum / YES-NO columns, an Instructions sheet"
  key_links:
    - "Requirements: REQ-04, REQ-05, NFR-01, NFR-09 (empty-row stop), NFR-10; DECISION-002, DECISION-007, DECISION-011"
---

# Plan 1.2: Column Specs & Streaming XLSX

<objective>
Build the format layer: a declarative column-spec system and a streaming xlsx writer / reader on openpyxl that handle any row count with flat memory.

Purpose: Phases 2–4 only declare columns (farmer 21, VLCC 44, prodata 9); formatting, validation, streaming and sheet limits are solved once here.
Output: `domain/columns.py`, `infrastructure/xlsx.py` with tests. (File storage and hostile-file guards are Plan 1.3.)
</objective>

<context>
Load for context:
- .gsd/REQUIREMENTS.md (REQ-04, REQ-05, NFR-01, NFR-09, NFR-10, CON-11)
- .gsd/DECISIONS.md (DECISION-002, DECISION-007, DECISION-011)
- .gsd/phases/1/RESEARCH.md (openpyxl streaming findings)
- app/core/validators.py (`mobile_number` — reuse its rules, do not duplicate them)
- app/modules/dataexchange/domain/exceptions.py (from Plan 1.1)
</context>

<tasks>

<task type="auto">
  <name>Declarative column specs with cell parsing</name>
  <files>
    app/modules/dataexchange/domain/columns.py
    tests/dataexchange/test_columns.py
  </files>
  <action>
    Pure Python (domain layer — no openpyxl, no pydantic).
    1. `ColumnKind(IntEnum)`: TEXT, CODE, INT, FLOAT, BOOL, ENUM, EMAIL, MOBILE, TIME, PINCODE, ACCOUNT_NUMBER, IFSC, PASSWORD.
    2. `Section(IntEnum)`: USER, ENTITY, ADDRESS, BANK, SETTINGS, MILK_QUALITY, RATE — each with a `fill` hex colour property (🟦 #DBEAFE, 🟩 #DCFCE7, 🟧 #FFEDD5, 🟪 #EDE9FE, 🟨 #FEF9C3, 🟥 #FEE2E2, rate #E0F2FE).
    3. `ColumnSpec` `@dataclass(slots=True, frozen=True, kw_only=True)`: key, header, section, kind, required=False, choices (tuple of (label, value)) = (), min_value / max_value (float | None), max_length (int | None), help, example, export_only=False, import_only=False (password).
       Properties: `is_text_format` (CODE, MOBILE, PINCODE, ACCOUNT_NUMBER, IFSC, TIME → Excel "@"), `display_header` (header + " *" when required).
    4. `SheetSpec` `@dataclass(slots=True, frozen=True, kw_only=True)`: name, columns, `key_column` (the upsert key), methods `export_columns()`, `import_columns()`, `by_normalised_header()`.
    5. `normalise_header(text) -> str`: strip, drop trailing `*`, lower-case, collapse spaces / `_` / `-` into one `_`.
    6. `HeaderMap.build(sheet, raw_headers) -> HeaderMap`: index per column key, list of `missing_required`, list of `unknown` headers; duplicate header → keep first, record a warning.
    7. `parse_cell(spec, raw) -> ParsedCell` (`value`, `error: str | None`, `blank: bool`):
       - blank: None, "", whitespace → blank=True (never an error here; "required" is checked by the importer because blank-on-update means keep — DECISION-003).
       - numbers that Excel returns as float for code / mobile / pincode / account (`9876543210.0`) → digit string without `.0`; reject real fractions.
       - MOBILE via `app.core.validators.mobile_number` rules (10 digits); EMAIL basic RFC check + lower-case; BOOL accepts YES/NO/TRUE/FALSE/1/0/Y/N; ENUM accepts label (case-insensitive) or numeric value; TIME `HH:MM` 00:00–23:59 (also accept Excel `datetime.time`); FLOAT / INT with min / max; TEXT / CODE trimmed with max_length.
       - error messages are short and human (`"Mobile must be 10 digits"`), used verbatim in the discarded-rows `Reason` column.
    8. `format_cell(spec, value)`: inverse for export (enum → label, bool → YES / NO, None → "").
    Tests (test_columns.py): header normalisation variants; HeaderMap with reordered + unknown + missing required headers; each ColumnKind accepts a good value and rejects a bad one with a message; float-mobile normalisation; enum by label and by number; format_cell ↔ parse_cell round-trip for every kind.
    AVOID: putting the "required" check in parse_cell, because on update a blank cell must keep the stored value.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_columns.py -q → green</verify>
  <done>Every ColumnKind has a passing positive and negative test; format_cell → parse_cell round-trips for all kinds.</done>
</task>

<task type="auto">
  <name>Streaming xlsx writer and reader</name>
  <files>
    app/modules/dataexchange/infrastructure/xlsx.py
    tests/dataexchange/test_xlsx.py
  </files>
  <action>
    Synchronous classes (they run inside `asyncio.to_thread`); `__slots__` on both.
    1. `XlsxSheetWriter(path, sheet, *, extra_columns=(), rows_per_sheet=1_048_575)` — `Workbook(write_only=True)`. When a sheet reaches `rows_per_sheet` data rows, open the next sheet `"<name> (2)"`, `"(3)"`, … and repeat the header + formatting on it (CON-11). Before the first append on each sheet: column widths, `freeze_panes = "A2"`, `auto_filter.ref`, one `DataValidation(type="list")` per ENUM / BOOL column over rows 2..1048576, `"@"` number format per text column. `write_header()` writes `WriteOnlyCell`s with bold font + section fill. `write_rows(rows: Iterable[Sequence])` appends values (text columns as `str` with `"@"` format). `extra_columns` lets the report writer append `Row No` and `Reason`. `write_instructions()` adds an `Instructions` sheet: Column, Section, Required, Type, Allowed values, Example, Notes. `close()` saves.
    2. `XlsxSheetReader(path, sheet, *, max_empty_run=1000, max_rows)` — `load_workbook(read_only=True, data_only=True)`. Data sheets = every sheet (in order) whose row-1 `HeaderMap` has no missing required header; the `Instructions` sheet and non-matching sheets are skipped; if none match, report the first sheet's missing headers. `iter_batches(size) -> Iterator[list[RawRow]]` where `RawRow` has `sheet`, `row_no` (Excel row number) and `cells: dict[key, raw]`; fully empty rows are skipped; after `max_empty_run` consecutive empty rows the sheet is considered finished; more than `max_rows` data rows raises a clear error ("File has more than N rows"). `estimated_rows` = sum of `max_row - 1` per data sheet. Always close the workbook (context manager).
    3. Tests (test_xlsx.py, files under `tmp_path`):
       - header row has `*` on required columns, frozen pane is A2, AutoFilter is set, validations exist for enum columns, Instructions sheet exists (re-open with normal openpyxl to inspect);
       - round-trip a 16-digit account number and a mobile → identical strings;
       - reader works with reordered columns and an extra unknown column;
       - 100,000-row round-trip: `tracemalloc` peak < 60 MB for write and for read (proves streaming);
       - sheet split with `rows_per_sheet=1000` and 2,500 rows → sheets `X`, `X (2)`, `X (3)` with headers; reader returns all 2,500 rows with the right sheet / row numbers;
       - a sheet with 10 data rows, 1,500 empty rows, then 1 more row → reader stops after the empty run (returns 10 rows, does not scan further);
       - more than `max_rows` rows → the "more than N rows" error (negative case).
    AVOID: setting freeze panes / validations after the first append — openpyxl write-only mode ignores them silently.
    AVOID: `load_workbook` without `read_only=True`, because it loads the whole file into memory.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_xlsx.py -q → green (the 100k test included)</verify>
  <done>Formatting assertions pass; the 100,000-row round-trip stays under the 60 MB tracemalloc peak; sheet split, multi-sheet read, empty-run stop and max-rows error are proven by tests.</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` is green
- [ ] `domain/columns.py` imports nothing outside the standard library and `app.core.validators`
- [ ] 100k-row round-trip peak memory < 60 MB (NFR-01 evidence)
- [ ] Sheet split + multi-sheet read proven (NFR-10)
</verification>

<success_criteria>
- [ ] All tasks verified
- [ ] Must-haves confirmed
</success_criteria>
