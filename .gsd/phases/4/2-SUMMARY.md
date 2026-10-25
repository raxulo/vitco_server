# Plan 4.2 Summary: Prodata Rate-Chart Import, Scoping & REST API

## Implemented Features
1. **Atomic Replace Import Processor (`ProdataImportProcessor`):**
   - Implemented in `app/modules/dataexchange/application/prodata_import.py`.
   - Full 2-pass in-memory validation:
     - Boundary checks: `fat_min <= fat_max`, `snf_min <= snf_max` when provided, non-negative rates.
     - Overlap validation: detects overlapping `[fat_min, fat_max]` and `[snf_min, snf_max]` intervals across rows within the same chart; touching boundaries (e.g., `3.0-4.0` and `4.0-5.0`) permitted.
     - Rejects entire file on any validation error (all-or-nothing replace, DECISION-005) and generates discarded rows report (`discarded_rows.xlsx`).
     - On valid file, executes delete of old rows and insertion of new rows within a single atomic database transaction.
   - Registered in `app/worker/exchange.py` under `ExcelJobKind.PRODATA_IMPORT`.

2. **Access Control & Scoping (`RateChartScope`):**
   - Implemented in `app/modules/dataexchange/infrastructure/ratechart_scope.py`.
   - Hierarchical access rules:
     - `SUPER_ADMIN`: Access and modify all charts.
     - `SUB_ADMIN`: Access charts created by self or creator; modify charts created by self.
     - `MCC`: Access and modify charts within own MCC scope.
     - `VLCC`: Access assigned charts; read-only.
     - `FARMER`: Denied.

3. **Application Handler & Dependency Injection:**
   - Implemented `ProdataExchangeHandler` in `app/modules/dataexchange/application/prodata_exchange.py` handling `chart_options()`, `export()`, `import_()`, and `template()`.
   - Configured in IoC container in `app/modules/configurator.py` and helper `GetHandler.prodata_exchange_handler()` in `app/modules/dependencies.py`.

4. **REST Endpoints & Schemas:**
   - Added Pydantic schemas in `app/api/v1/schemas/excel.py` (`RateChartOptionResponse`, `RateChartOptionsResponse`, `ProdataExportRequest`, `ProdataImportRequest`).
   - Added REST endpoints in `app/api/v1/routers/excel.py`:
     - `GET /api/v1/excel/prodata/options`: List accessible rate charts with `can_modify` flag.
     - `GET /api/v1/excel/prodata/template`: Static cached Excel template download.
     - `POST /api/v1/excel/prodata/export`: Enqueue export background job.
     - `POST /api/v1/excel/prodata/import`: Enqueue import background job via staged upload.

5. **Test Coverage:**
   - `tests/dataexchange/test_prodata_import.py`: 7 tests covering valid atomic replace, dry-run, invalid FAT/SNF bounds, range overlaps, and continuous slabs (All PASS).
   - `tests/dataexchange/test_prodata_api.py`: 5 tests covering options scoping, template download, end-to-end export job, end-to-end import job with worker loop, and 403 permission denial (All PASS).
