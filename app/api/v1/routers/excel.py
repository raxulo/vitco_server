"""
Excel Import / Export API

Shared by the web panel and the mobile app:

    uploads:  POST /excel/uploads -> PUT /excel/uploads/{id}/chunks/{n} -> POST /excel/uploads/{id}/complete
              (or POST /excel/uploads/single for files up to 10 MB)
    jobs:     GET /excel/jobs, GET /excel/jobs/{id} (poll), GET /excel/jobs/{id}/file, POST /excel/jobs/{id}/cancel

Entity endpoints (`/excel/farmers/...`, `/excel/vlccs/...`, `/excel/ratecharts/...`)
are added by later phases. Upload routes run without the request-wide DB
transaction (DECISION-009).

Python 3.13+
"""

from __future__ import annotations

import math
from uuid import UUID

from fastapi import APIRouter, File, HTTPException, Query, Request, UploadFile
from fastapi.encoders import jsonable_encoder
from fastapi.responses import FileResponse, JSONResponse

from app.api.v1.schemas.excel import (
    CreateUploadRequest,
    ExcelJobResponse,
    FarmerExportRequest,
    FarmerImportRequest,
    OwnerOptionResponse,
    UploadResponse,
    VlccExportRequest,
    VlccImportRequest,
    VlccOptionResponse,
)
from app.core.exceptions.base import ApplicationException
from app.middleware.authentication import CurrentUser
from app.modules.dataexchange.application.command import (
    CancelExcelJobCommand,
    GetExcelJobFileQuery,
    GetExcelJobQuery,
    ListExcelJobsQuery,
)
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus, ImportMode
from app.modules.dataexchange.domain.exceptions import ExcelJobCapacityException, ExcelJobConflictException
from app.modules.dependencies import GetHandler

router = APIRouter(
    prefix="/excel",
    tags=["Excel Import / Export"],
)

_XLSX = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"


# =========================================================
# HELPERS
# =========================================================

def _compute_pagination(total: int, limit: int, offset: int):
    """Compute pagination metadata (pages, next_page, has_more)."""
    limit_val = max(1, limit)
    offset_val = max(0, offset)
    pages = math.ceil(total / limit_val) if total > 0 else 1
    current_page = (offset_val // limit_val) + 1
    has_more = (offset_val + limit_val) < total
    next_page = (current_page + 1) if has_more else None
    return {
        "limit": limit_val,
        "offset": offset_val,
        "total": total,
        "pages": pages,
        "next_page": next_page,
        "has_more": has_more,
    }


def _user(request: Request) -> CurrentUser:
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return user


def _single(data, message: str, code: int = 200) -> JSONResponse:
    return JSONResponse(
        status_code=code,
        content=jsonable_encoder({"status": True, "code": code, "message": message, "data": data}),
    )


def excel_busy_response(exc: ApplicationException) -> JSONResponse:
    """429 / 409 with Retry-After, in the app's standard error shape (used by submit endpoints)."""
    headers = {}
    retry_after = getattr(exc, "retry_after", None)
    if retry_after:
        headers["Retry-After"] = str(retry_after)
    return JSONResponse(
        status_code=exc.status_code,
        headers=headers,
        content={"success": False, "error": {"code": exc.code, "message": exc.message, "details": exc.details}},
    )


def _accepted(dto) -> JSONResponse:
    return _single(ExcelJobResponse.from_dto(dto), "Job queued", code=202)


# =========================================================
# FARMERS
# =========================================================

@router.get("/options/vlccs")
async def vlcc_options(
    request: Request,
    search: str | None = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """VLCCs this user may export / import farmers for. `locked` = the app shows the selection disabled."""
    user = _user(request)
    options = await GetHandler.farmer_exchange_handler(request).vlcc_options(user, search=search, limit=limit, offset=offset)
    return JSONResponse(content=jsonable_encoder({
        "status": True,
        "code": 200,
        "message": "Records fetched successfully",
        "items": [VlccOptionResponse(id=item.id, code=item.code, name=item.name) for item in options.items],
        "locked": options.locked,
        "default_id": options.default_id,
        **_compute_pagination(options.total, limit, offset),
    }))


@router.get("/farmers/template")
async def farmer_template(request: Request):
    _user(request)
    path = await GetHandler.farmer_exchange_handler(request).template()
    return FileResponse(path, media_type=_XLSX, filename="farmers_template.xlsx",
                        headers={"Content-Encoding": "identity"})


@router.post("/farmers/export", status_code=202)
async def export_farmers(request: Request, payload: FarmerExportRequest):
    user = _user(request)
    try:
        dto = await GetHandler.farmer_exchange_handler(request).export(user, payload.vlcc_id)
    except (ExcelJobConflictException, ExcelJobCapacityException) as busy:
        return excel_busy_response(busy)
    return _accepted(dto)


@router.post("/farmers/import", status_code=202)
async def import_farmers(request: Request, payload: FarmerImportRequest):
    user = _user(request)
    try:
        dto = await GetHandler.farmer_exchange_handler(request).import_(
            user,
            vlcc_id=payload.vlcc_id,
            upload_id=payload.upload_id,
            mode=ImportMode[payload.mode],
            dry_run=payload.dry_run,
        )
    except (ExcelJobConflictException, ExcelJobCapacityException) as busy:
        return excel_busy_response(busy)
    return _accepted(dto)


# =========================================================
# VLCCS
# =========================================================

@router.get("/options/owners")
@router.get("/vlccs/options")
async def owner_options(
    request: Request,
    search: str | None = Query(None, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    """Owners (Admin, Sub Admin, MCC) this user may export / import VLCCs for."""
    user = _user(request)
    options = await GetHandler.vlcc_exchange_handler(request).owner_options(user, search=search, limit=limit, offset=offset)
    return JSONResponse(content=jsonable_encoder({
        "status": True,
        "code": 200,
        "message": "Records fetched successfully",
        "items": [OwnerOptionResponse(id=item.id, name=item.name, role=item.role) for item in options.items],
        "locked": options.locked,
        "default_id": options.default_id,
        **_compute_pagination(options.total, limit, offset),
    }))


@router.get("/vlccs/template")
async def vlcc_template(request: Request):
    _user(request)
    path = await GetHandler.vlcc_exchange_handler(request).template()
    return FileResponse(path, media_type=_XLSX, filename="vlccs_template.xlsx",
                        headers={"Content-Encoding": "identity"})


@router.post("/vlccs/export", status_code=202)
async def export_vlccs(request: Request, payload: VlccExportRequest):
    user = _user(request)
    try:
        dto = await GetHandler.vlcc_exchange_handler(request).export(user, payload.owner_id)
    except (ExcelJobConflictException, ExcelJobCapacityException) as busy:
        return excel_busy_response(busy)
    return _accepted(dto)


@router.post("/vlccs/import", status_code=202)
async def import_vlccs(request: Request, payload: VlccImportRequest):
    user = _user(request)
    try:
        dto = await GetHandler.vlcc_exchange_handler(request).import_(
            user,
            owner_id=payload.owner_id,
            upload_id=payload.upload_id,
            mode=ImportMode[payload.mode],
            dry_run=payload.dry_run,
        )
    except (ExcelJobConflictException, ExcelJobCapacityException) as busy:
        return excel_busy_response(busy)
    return _accepted(dto)



# =========================================================
# UPLOADS (no request-wide DB transaction)
# =========================================================

@router.post("/uploads", status_code=201)
async def create_upload(request: Request, payload: CreateUploadRequest):
    """Start a resumable upload; send the file in `chunk_size` pieces afterwards."""
    user = _user(request)
    status = GetHandler.excel_upload_service(request).create(
        user, file_name=payload.file_name, size=payload.size, sha256=payload.sha256,
    )
    return _single(UploadResponse.from_status(status), "Upload started", code=201)


@router.put("/uploads/{upload_id}/chunks/{index}")
async def put_upload_chunk(request: Request, upload_id: UUID, index: int):
    """Raw chunk bytes as the request body. Re-sending a chunk is harmless."""
    user = _user(request)
    status = await GetHandler.excel_upload_service(request).put_chunk(user, upload_id, index, request.stream())
    return _single(UploadResponse.from_status(status), "Chunk received")


@router.get("/uploads/{upload_id}")
async def get_upload(request: Request, upload_id: UUID):
    """Which chunks arrived / are missing — used to resume after a network drop."""
    user = _user(request)
    status = GetHandler.excel_upload_service(request).status(user, upload_id)
    return _single(UploadResponse.from_status(status), "Upload status fetched")


@router.post("/uploads/{upload_id}/complete")
async def complete_upload(request: Request, upload_id: UUID):
    user = _user(request)
    status = await GetHandler.excel_upload_service(request).complete(user, upload_id)
    return _single(UploadResponse.from_status(status), "Upload completed")


@router.post("/uploads/single", status_code=201)
async def single_upload(request: Request, file: UploadFile = File(...)):
    """One-request upload for files up to 10 MB."""
    user = _user(request)
    status = await GetHandler.excel_upload_service(request).save_single(user, file, file.filename or "")
    return _single(UploadResponse.from_status(status), "Upload completed", code=201)


# =========================================================
# JOBS
# =========================================================

@router.get("/jobs")
@router.post("/jobs/list")
async def list_jobs(
    request: Request,
    kind: ExcelJobKind | None = Query(None),
    status: ExcelJobStatus | None = Query(None),
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
):
    user = _user(request)
    handler = GetHandler.excel_handler(request)
    query = ListExcelJobsQuery(owner=user, kind=kind, status=status, limit=limit, offset=offset)
    total = await handler.count(query)
    items = [ExcelJobResponse.from_dto(dto) for dto in await handler.list(query)]
    return JSONResponse(content=jsonable_encoder({
        "status": True,
        "code": 200,
        "message": "Records fetched successfully",
        "items": items,
        **_compute_pagination(total, limit, offset),
    }))


@router.get("/jobs/{job_id}")
async def get_job(request: Request, job_id: UUID):
    """Poll this until `poll_after_ms` is null (finished)."""
    user = _user(request)
    dto = await GetHandler.excel_handler(request).get(GetExcelJobQuery(id=job_id, owner=user))
    return _single(ExcelJobResponse.from_dto(dto), "Job fetched successfully")


@router.get("/jobs/{job_id}/file")
async def download_job_file(request: Request, job_id: UUID):
    """The export file, or the discarded-rows report of an import. Supports Range (resume)."""
    user = _user(request)
    path, job = await GetHandler.excel_handler(request).file_path(GetExcelJobFileQuery(id=job_id, owner=user))
    stamp = (job.created_at.strftime("%Y%m%d_%H%M") if job.created_at else "file")
    suffix = "" if path.name == job.result_file else "_discarded_rows"
    return FileResponse(
        path,
        media_type=_XLSX,
        filename=f"{job.kind.name.lower()}_{stamp}{suffix}.xlsx",
        # xlsx is already compressed: an explicit encoding makes GZipMiddleware skip it,
        # which keeps CPU free and Range / resume working
        headers={"Content-Encoding": "identity"},
    )


@router.post("/jobs/{job_id}/cancel")
async def cancel_job(request: Request, job_id: UUID):
    user = _user(request)
    dto = await GetHandler.excel_handler(request).cancel(CancelExcelJobCommand(id=job_id, owner=user))
    return _single(ExcelJobResponse.from_dto(dto), "Cancel requested")
