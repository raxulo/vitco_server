# Plan 5.1: Web Panel Excel Exchange UI (REQ-19)

## Goal
Enable users on the Farmer, VLCC, and Rate Chart list pages to download Excel templates, export data, and import data via a responsive, accessible modal dialog with live progress and result summary cards.

## Proposed Changes

### 1. Authentication Middleware Support
- **File:** `app/middleware/authentication.py`
- Allow cookie-based authentication (`request.cookies.get('access_token')`) for `/api/v1/excel/` paths in addition to web routes, enabling seamless browser downloads (`<a href="..." download>`) and script requests.

### 2. Frontend JavaScript Controller
- **File:** `app/web/static/js/excel_exchange.js`
- Functions:
  - `openExcelModal(kind)`: Opens the modal for `'farmers'`, `'vlccs'`, or `'prodata'`.
  - `loadOptions(kind)`: Calls `/api/v1/excel/{kind}/options`. If single choice or user cannot modify other choices, locks the dropdown.
  - `downloadTemplate(kind)`: Directs browser to `/api/v1/excel/{kind}/template`.
  - `startExport(kind)`: Posts export request, transitions to polling view.
  - `uploadAndImport(kind, file, targetId, mode, dryRun)`:
    - If file <= 5MB: uploads to `/api/v1/excel/uploads/single`.
    - If file > 5MB: slices file into 5MB chunks and uploads sequentially to `/api/v1/excel/uploads`.
    - Submits import job to `/api/v1/excel/{kind}/import`.
    - Transitions to polling view.
  - `pollJob(jobId)`: Polls `/api/v1/excel/jobs/{jobId}` using dynamic `poll_after_ms` interval.
  - `renderSummary(job)`: Shows total, inserted, updated, discarded rows. Shows "Download Discarded Rows" if discarded > 0.

### 3. Excel Modal HTML Component
- **File:** `app/web/templates/components/excel_modal.html`
- Reusable modal with:
  - Tab / Section 1: Template download info & target selector.
  - Tab / Section 2: Export trigger with instant download.
  - Tab / Section 3: File drag & drop, mode selector (for farmer/vlcc), dry-run checkbox, and Submit button.
  - Tab / Section 4: Progress state with animated bar, current step, and cancel button.
  - Tab / Section 5: Summary card with statistics and download report button.

### 4. Integration into List Templates
- **Files:**
  - `app/web/templates/layouts/base.html` (include `excel_exchange.js` script tag)
  - `app/web/templates/layouts/dashboard.html` (include `components/excel_modal.html`)
  - `app/web/templates/pages/farmer/list.html`: add "Excel Exchange" dropdown / buttons in header.
  - `app/web/templates/pages/vlcc/list.html`: add "Excel Exchange" dropdown / buttons in header.
  - `app/web/templates/pages/ratechart/list.html`: add "Excel Exchange" dropdown / buttons in header.

## Verification
- Test cookie-based authentication on `/api/v1/excel/farmers/options` and `/template`.
- Verify modal rendering and integration across all 3 pages via tests and browser/API checks.
