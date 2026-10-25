# Plan 5.4: Mobile API Documentation & Milestone Verification

## Goal
Document the full asynchronous Excel exchange lifecycle for mobile app (Flutter / React Native) and external client developers, followed by the final Milestone v1.1.0 verification audit.

## Deliverables
1. **Developer Guide (`docs/EXCEL_EXCHANGE_API.md`):**
   - End-to-end integration flow:
     1. Stage file: `/api/v1/excel/uploads` (chunked) or `/api/v1/excel/uploads/single`.
     2. Enqueue import/export: `/api/v1/excel/{farmers|vlccs|prodata}/{export|import}`.
     3. Poll progress: `/api/v1/excel/jobs/{job_id}` respecting `poll_after_ms`.
     4. Download output / rejected rows: `/api/v1/excel/jobs/{job_id}/file`.
   - Error code catalog: 401 Unauthorized, 403 Forbidden, 404 Target Not Found, 409 Conflict, 422 Invalid Rows, 429 Backpressure / Rate Limit, 507 Insufficient Storage.
   - Recommended mobile retry and backoff strategies.
2. **Phase 5 Verification & Milestone v1.1.0 Audit (`.gsd/phases/5/VERIFICATION.md`):**
   - Traceability matrix for all REQ-01..19 and NFR-01..14.
