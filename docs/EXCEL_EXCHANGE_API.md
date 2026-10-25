# Quickyee Excel Data Exchange API — Mobile & Client Developer Guide

This document defines the contract, flow, and lifecycle for integrating Excel Import and Export in the **Quickyee** mobile app (Flutter / React Native) and external client systems.

---

## 1. Overview & Core Architecture

To guarantee **zero freeze, zero lag, and zero server crashes**, all Excel imports and exports execute asynchronously as background worker jobs.

### The 4-Step Exchange Lifecycle

```
+-----------------------------------------------------------------------------------------+
|                                1. STAGE / UPLOAD                                        |
| Client uploads the .xlsx spreadsheet to staging storage (/uploads/single or /uploads).  |
| Server returns an upload_id (UUID).                                                     |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                2. SUBMIT JOB                                            |
| Client submits the import or export job request with upload_id and target scope.        |
| Server validates permissions immediately and returns HTTP 202 Accepted with a job_id.   |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                3. POLL STATUS                                           |
| Client polls GET /api/v1/excel/jobs/{job_id} at intervals guided by poll_after_ms.      |
| Response shows: PENDING -> RUNNING (processed_rows / total_rows) -> COMPLETED / FAILED. |
+-----------------------------------------------------------------------------------------+
                                           |
                                           v
+-----------------------------------------------------------------------------------------+
|                                4. DOWNLOAD RESULT                                       |
| - If EXPORT completed: download the generated .xlsx spreadsheet from /jobs/{id}/file.   |
| - If IMPORT has discarded > 0: download the discarded rows report from /jobs/{id}/file. |
+-----------------------------------------------------------------------------------------+
```

---

## 2. Authentication

All requests require JWT Bearer authentication in the HTTP header:
```http
Authorization: Bearer <access_token>
```
*(On web browsers, the `access_token` cookie is also automatically accepted).*

---

## 3. Endpoints Reference

### A. Scopes & Target Options
Use these endpoints to populate target selection dropdowns before submitting an export or import.

#### 1. Farmer Targets (VLCC Centers)
```http
GET /api/v1/excel/farmers/options?search={query}&limit=20&offset=0
```
- **Response:**
  ```json
  {
    "status": true,
    "code": 200,
    "items": [
      { "id": "uuid-here", "code": "V001", "name": "Center A" }
    ],
    "locked": true,
    "default_id": "uuid-here",
    "total": 1
  }
  ```
  > **Note on `locked`:** When `locked: true` (e.g. for VLCC or MCC users), the app **must disable** the dropdown and pre-select `default_id`.

#### 2. VLCC Targets (Owners)
```http
GET /api/v1/excel/vlccs/options?search={query}&limit=20&offset=0
```
- **Response:** List of Admin, Sub-Admin, and MCC owners the user may manage.

#### 3. Prodata Rate-Chart Targets
```http
GET /api/v1/excel/prodata/options?search={query}&limit=20&offset=0
```
- **Response:**
  ```json
  {
    "status": true,
    "code": 200,
    "items": [
      {
        "id": "uuid-here",
        "name": "Standard Buffalo Slabs",
        "can_modify": true
      }
    ]
  }
  ```
  > **Note on `can_modify`:** Only charts with `can_modify: true` may be selected for **Import (atomic replace)**. Charts with `can_modify: false` can only be exported.

---

### B. Template Downloads
Download official, pre-styled templates with validation rules, examples, and correct column headers:
- **Farmers:** `GET /api/v1/excel/farmers/template`
- **VLCCs:** `GET /api/v1/excel/vlccs/template`
- **Prodata:** `GET /api/v1/excel/prodata/template`

---

### C. File Staging & Uploads

#### 1. Single Upload (Recommended for files ≤ 10 MB)
```http
POST /api/v1/excel/uploads/single
Content-Type: multipart/form-data
```
- **Form field:** `file` (binary `.xlsx` file)
- **Response (HTTP 201 Created):**
  ```json
  {
    "status": true,
    "code": 201,
    "data": {
      "id": "3fa85f64-5717-4562-b3fc-2c963f66afa6",
      "file_name": "farmers.xlsx",
      "size": 1048576,
      "complete": true
    }
  }
  ```

#### 2. Resumable Chunked Upload (For large files > 10 MB)
1. **Initialize Upload Session:**
   ```http
   POST /api/v1/excel/uploads
   Content-Type: application/json

   {
     "file_name": "farmers_large.xlsx",
     "size": 25165824
   }
   ```
   *Returns `data.id` and `data.chunk_size` (default 5 MB).*

2. **Upload Each Chunk Sequentially:**
   ```http
   PUT /api/v1/excel/uploads/{upload_id}/chunks/{chunk_index}
   Content-Type: application/octet-stream

   <binary chunk bytes>
   ```

3. **Complete Upload:**
   ```http
   POST /api/v1/excel/uploads/{upload_id}/complete
   ```

---

### D. Submitting Jobs (HTTP 202 Accepted)

#### 1. Farmer Import / Export
- **Export:**
  ```http
  POST /api/v1/excel/farmers/export
  Content-Type: application/json

  {
    "vlcc_id": "optional-uuid-if-not-locked"
  }
  ```
- **Import:**
  ```http
  POST /api/v1/excel/farmers/import
  Content-Type: application/json

  {
    "vlcc_id": "optional-uuid-if-not-locked",
    "upload_id": "staged-upload-uuid",
    "mode": "UPSERT",
    "dry_run": false
  }
  ```
  *Allowed `mode` values: `UPSERT` (default), `ADD_ONLY`, `UPDATE_ONLY`.*

#### 2. VLCC Import / Export
- **Export:** `POST /api/v1/excel/vlccs/export` (`owner_id` optional if single).
- **Import:** `POST /api/v1/excel/vlccs/import` (`upload_id`, `owner_id`, `mode`, `dry_run`).

#### 3. Prodata Rate-Chart Import / Export
- **Export:** `POST /api/v1/excel/prodata/export` (`chart_id`).
- **Import (Atomic Replace):** `POST /api/v1/excel/prodata/import` (`upload_id`, `chart_id`, `dry_run`).

All submission endpoints return **HTTP 202 Accepted** with:
```json
{
  "status": true,
  "code": 202,
  "message": "Job queued",
  "data": {
    "id": "job-uuid",
    "kind": "FARMER_IMPORT",
    "status": { "code": 1, "name": "QUEUED" },
    "poll_after_ms": 1000
  }
}
```

---

### E. Polling Job Progress

```http
GET /api/v1/excel/jobs/{job_id}
```
- **Response:**
  ```json
  {
    "status": true,
    "code": 200,
    "data": {
      "id": "job-uuid",
      "kind": "FARMER_IMPORT",
      "status": { "code": 2, "name": "RUNNING" },
      "total_rows": 5000,
      "processed_rows": 2400,
      "inserted": 2400,
      "updated": 0,
      "discarded": 0,
      "poll_after_ms": 1000,
      "created_at": "2026-10-25T16:00:00"
    }
  }
  ```

> **Client Polling Rule:**
> Always wait for `poll_after_ms` milliseconds (typically 1,000 ms) before the next poll. When the job is finished (`COMPLETED` or `FAILED`), `poll_after_ms` will be `null`.

---

### F. Downloading Output or Error Reports

```http
GET /api/v1/excel/jobs/{job_id}/file
```
- **When to call:**
  - For **Export jobs**: When `status.name == "COMPLETED"`. Downloads the generated Excel workbook.
  - For **Import jobs**: When `status.name == "COMPLETED"` and `discarded > 0`. Downloads the `discarded_rows.xlsx` error report containing each failed row with `Row No` and `Reason` columns appended.

---

## 4. Error Handling & HTTP Status Codes

| HTTP Code | Error Code | Description & Client Action |
|-----------|------------|-----------------------------|
| `401` | `UNAUTHORIZED` | Token expired or missing. Refresh token or redirect to login. |
| `403` | `EXCEL_EXCHANGE_FORBIDDEN` | User does not have permission to manage this VLCC, Owner, or Rate Chart. |
| `404` | `EXCEL_JOB_NOT_FOUND` | Job ID does not exist or expired (> 24 hours old). |
| `409` | `EXCEL_JOB_ALREADY_RUNNING` | Another job of this kind is already running for this user. Wait for completion. |
| `422` | `INVALID_EXCEL_FILE` | Hostile, corrupted, or non-xlsx file. Instruct user to upload valid `.xlsx`. |
| `429` | `EXCEL_JOB_QUEUE_FULL` | Worker capacity busy. Check `Retry-After` header and retry after specified seconds. |
| `507` | `EXCEL_STORAGE_FULL` | Server disk space low. Alert admin. |
