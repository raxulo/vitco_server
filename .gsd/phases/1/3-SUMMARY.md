---
phase: 1
plan: 3
completed_at: 2026-10-25
---

# Summary: File Safety — Storage, Hostile-File Guard, Duplicate Store

## Results
- 3 tasks completed
- All verifications passed: 15 storage + 11 guard + 5 duplicate-store tests (133 in the module suite)

## Tasks Completed
| Task | Description | Commit | Status |
|------|-------------|--------|--------|
| 1 | `ExchangeStorage`: job / upload folders, streamed size-limited writes, disk guard, safe paths | phase commit (pending) | ✅ |
| 2 | `FileGuard`: zip magic, directory limits, ratio, encryption, unsafe paths, XML declarations | phase commit (pending) | ✅ |
| 3 | `SeenKeys`: disk-backed duplicate detection with first-row reporting | phase commit (pending) | ✅ |

## Deviations Applied
- [Rule 2 - Missing critical] Writes land atomically: data goes to `<name>.part` and is renamed only after the last byte, so a cut or oversized stream never leaves a file that looks complete.
- [Rule 1 - Bug, cross-platform] `ExchangeStorage.path()` accepts only plain file names (`[A-Za-z0-9._-]{1,128}`). A Windows-style `C:\...` name is a valid relative name on Linux, so the earlier "absolute / drive" check would have let it through on the server.
- [Design] `SeenKeys.check_and_add` returns `{(kind, value, row_no): first_row_no}` per duplicate occurrence (the plan said per value), so the importer can mark exactly which rows to discard and quote the first row in the reason.
- [Note] Callers must only register keys of rows that passed validation, otherwise an invalid row would "claim" a code / mobile / email. Recorded for Phase 2.

## Files Changed
- `app/modules/dataexchange/infrastructure/storage.py` — new
- `app/modules/dataexchange/infrastructure/file_guard.py` — new
- `app/modules/dataexchange/infrastructure/seen_keys.py` — new
- `tests/dataexchange/test_storage.py`, `test_file_guard.py`, `test_seen_keys.py` — new

## Verification
- 2.3 MB upload saved byte-identical through 1 MB chunks, no `.part` left behind: ✅
- 2 MB upload with a 1 MB limit raises 413 and leaves the folder empty; exact-limit boundary tested: ✅ (NFR-05)
- Free-space check raises 507 when the expected size does not fit: ✅ (NFR-11)
- 9 unsafe names rejected (`..`, absolute, `C:\`, sub-paths, over-long): ✅
- Real xlsxwriter workbook passes the guard; text file, non-workbook zip, ~1000:1 member, total-size limit, member count, `<!DOCTYPE` / `<!ENTITY` (any case), `../` member, truncated zip all rejected with specific messages: ✅ (NFR-09)
- Duplicates within and across batches report the first row; kinds do not collide; scratch file deleted on close: ✅
- 1,000,000 keys: tracemalloc peak **0.2 MB** (Python heap; SQLite's own page cache is fixed-size and not traced): ✅ (NFR-01)
