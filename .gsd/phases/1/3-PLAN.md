---
phase: 1
plan: 3
wave: 2
depends_on: [1]
files_modified:
  - app/modules/dataexchange/infrastructure/storage.py
  - app/modules/dataexchange/infrastructure/file_guard.py
  - app/modules/dataexchange/infrastructure/seen_keys.py
  - tests/dataexchange/test_storage.py
  - tests/dataexchange/test_file_guard.py
  - tests/dataexchange/test_seen_keys.py
autonomous: true
user_setup: []

must_haves:
  truths:
    - "Uploads stream to disk in chunks, stop the moment they pass the size limit, and leave no partial file behind"
    - "Zip bombs (uncompressed total > limit, member ratio > 100, > 10,000 members), non-zip files and xlsx files with XML entity declarations are rejected before openpyxl parses them"
    - "A job refuses to start when free disk < EXCHANGE_MIN_FREE_DISK_MB + expected size (507), and a running job can re-check cheaply"
    - "In-file duplicate detection for 1,000,000 keys uses < 30 MB of Python memory (disk-backed)"
  artifacts:
    - "ExchangeStorage, FileGuard, SeenKeys — all with __slots__, all synchronous-safe or async as documented"
  key_links:
    - "Requirements: NFR-01, NFR-05, NFR-09, NFR-11; DECISION-011"
---

# Plan 1.3: File Safety — Storage, Hostile-File Guard, Disk Guard, Duplicate Store

<objective>
Make every file the system touches safe and bounded: streamed storage with path-escape protection, rejection of hostile xlsx files before parsing, free-disk checks, and a disk-backed duplicate detector whose memory does not grow with the file.

Purpose: a single malicious or huge file must never exhaust memory, disk or CPU (user rule: never freeze / lag / crash).
Output: three infrastructure components with tests.
</objective>

<context>
Load for context:
- .gsd/REQUIREMENTS.md (NFR-01, NFR-05, NFR-09, NFR-11)
- .gsd/DECISIONS.md (DECISION-011)
- .gsd/phases/1/RESEARCH.md (uploads, hostile-file findings)
- app/modules/dataexchange/domain/exceptions.py (Plan 1.1)
- app/config/settings.py (EXCHANGE_* settings from Plan 1.1)
</context>

<tasks>

<task type="auto">
  <name>Job storage with streamed writes and disk guard</name>
  <files>
    app/modules/dataexchange/infrastructure/storage.py
    tests/dataexchange/test_storage.py
  </files>
  <action>
    `ExchangeStorage(root, *, max_upload_bytes, min_free_bytes)` with `__slots__`:
    - `job_dir(job_id)` / `upload_dir(upload_id)` create `root/jobs/<id>/` and `root/uploads/<id>/`;
    - `async write_stream(dest, chunks: AsyncIterator[bytes], *, limit) -> int`: writes with `aiofiles`, counts bytes, raises `ExcelFileTooLargeException` as soon as `limit` is passed and deletes the partial file;
    - `async save_upload_file(dest, upload)` reads an UploadFile in 1 MB chunks into `write_stream`;
    - `ensure_free_space(expected_bytes)`: `shutil.disk_usage(root).free` < `min_free_bytes + expected_bytes` → `ExcelStorageFullException` (507, add to domain/exceptions.py if Plan 1.1 did not);
    - `path(base_dir, name)`: resolve and reject anything outside `base_dir` (`..`, absolute, symlink escape);
    - `delete_dir(path)` ignoring missing; `folder_size(path)`.
    Tests: small file saved byte-identical; 2 MB with a 1 MB limit raises and leaves no file; free-space check with a huge `expected_bytes` raises 507; `path(dir, "../x")` and an absolute path raise; delete removes the folder.
    AVOID: `await upload.read()` without a size, because it loads the whole upload into memory.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_storage.py -q → green</verify>
  <done>Size limit, disk guard and path-escape guard each have a passing negative test.</done>
</task>

<task type="auto">
  <name>Hostile-file guard (zip bomb, XML bomb, wrong format)</name>
  <files>
    app/modules/dataexchange/infrastructure/file_guard.py
    tests/dataexchange/test_file_guard.py
  </files>
  <action>
    `FileGuard(*, max_uncompressed_bytes, max_ratio=100, max_members=10_000)` with `__slots__`; `inspect(path) -> None` (sync; called via `asyncio.to_thread`):
    1. first 4 bytes `PK\x03\x04` else InvalidExcelFileException("Not an .xlsx file");
    2. `zipfile.ZipFile` directory only (no extraction): reject `BadZipFile`, > max_members, sum(`file_size`) > max_uncompressed_bytes, any member with `file_size / max(compress_size, 1) > max_ratio` and `file_size` > 1 MB, encrypted members, member names with `..` or absolute paths;
    3. must contain `[Content_Types].xml` and `xl/workbook.xml` (else "Not an Excel workbook" — catches .docx / random zips);
    4. scan the first 64 KB of each `xl/worksheets/*.xml` and `xl/sharedStrings.xml` for `<!DOCTYPE` / `<!ENTITY` → reject early with a clear message (the expat reader also refuses them while parsing — DECISION-012, defense in depth).
    Tests build real files under tmp_path: valid workbook passes; text file → rejected; zip without workbook.xml → rejected; high-ratio member (e.g. 50 MB of zeros) → rejected; 10,001 members → rejected; sheet XML with `<!ENTITY` → rejected.
    AVOID: extracting or fully decompressing members to measure them, because that is exactly what a zip bomb exploits.
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_file_guard.py -q → green</verify>
  <done>Each hostile case is rejected with a specific message; the valid workbook passes.</done>
</task>

<task type="auto">
  <name>Disk-backed duplicate detector</name>
  <files>
    app/modules/dataexchange/infrastructure/seen_keys.py
    tests/dataexchange/test_seen_keys.py
  </files>
  <action>
    `SeenKeys(path)` with `__slots__`: a scratch SQLite database (stdlib `sqlite3`, `journal_mode=OFF`, `synchronous=OFF` — scratch data, losing it on a crash is fine) in the job folder; one table `seen(kind TEXT, value TEXT, row_no INTEGER, PRIMARY KEY(kind, value)) WITHOUT ROWID`.
    `check_and_add(rows: list[tuple[kind, value, row_no]]) -> dict[(kind, value), first_row_no]` for a whole batch in one `executemany` + one select (returns the earlier row for duplicates, so the Reason can say "Mobile repeats row 17"); values are normalised by the caller (lower-case email, digit-only mobile). Context manager closes and deletes the file.
    Tests: duplicates within one batch and across batches are reported with the first row number; different kinds with the same value do not collide; 1,000,000 keys → tracemalloc peak < 30 MB.
    AVOID: Python `set` / `dict` of all keys, because memory then grows with the file (NFR-01).
  </action>
  <verify>.venv\Scripts\python.exe -m pytest tests/dataexchange/test_seen_keys.py -q → green</verify>
  <done>Duplicate detection is correct across batches and stays under 30 MB for 1,000,000 keys.</done>
</task>

</tasks>

<verification>
After all tasks, verify:
- [ ] `.venv\Scripts\python.exe -m pytest tests/dataexchange -q` is green
- [ ] No component reads a whole file into memory (`grep -n "\.read()" app/modules/dataexchange` shows only bounded reads)
</verification>

<success_criteria>
- [ ] All tasks verified
- [ ] Must-haves confirmed
</success_criteria>
