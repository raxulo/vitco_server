"""
Rate Chart API Router

Python 3.13+
"""
from app.modules.ratechart.application.command import CreateRateChartAssignmentCommand
from datetime import date
from typing import Any
from uuid import UUID
from fastapi import APIRouter, HTTPException, Query, Request

from app.api.v1.schemas.ratechart import (
    CreateRateChartApiRequest,
    RateChartDetailResponse,
    RateChartItemResponse,
    RateChartListResponse,
)
from app.middleware.authentication import CurrentUser
from app.modules.dependencies import GetHandler
from app.modules.ratechart.domain.enums import (
    MilkType,
    RateCalculationType,
    RateChartStatus,
    RateChartType,
)
from app.modules.ratechart.application.command import (
    CreateRateChartCommand,
    DeleteRateChartCommand,
    GetRateChartQuery,
    GridRowInput,
    ListRateChartsQuery,
    ProdataRowInput,
    SaveFormulaConfigCommand,
    SaveGridRowsCommand,
    SaveProdataRowsCommand,
)
from app.modules.ratechart.domain.exceptions import RateChartNotFoundException

router = APIRouter(
    prefix="/ratecharts",
    tags=["Rate Charts"],
)


@router.get("", response_model=RateChartListResponse)
@router.get("/", response_model=RateChartListResponse)
async def list_rate_charts(
    request: Request,
    page: int = Query(default=1, ge=1, description="Page number"),
    size: int = Query(default=20, ge=1, le=500, description="Page size"),
    search: str | None = Query(default=None, description="Search keyword"),
):
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.ratechart_handler(request)
    keyword = search.strip() if search and search.strip() else None

    if keyword:
        total = await handler.count_search(keyword=keyword, owner=user)
    else:
        total = await handler.count(owner=user)

    total_pages = (total + size - 1) // size if total > 0 else 1

    query = ListRateChartsQuery(
        page=page,
        size=size,
        keyword=keyword,
        owner=user,
    )
    items = await handler.list(query=query)

    return RateChartListResponse(
        items=[RateChartItemResponse.model_validate(item) for item in items],
        page=page,
        size=size,
        total=total,
        total_pages=total_pages,
    )


@router.get("/{ratechart_id}", response_model=RateChartDetailResponse)
async def get_rate_chart(
    request: Request,
    ratechart_id: UUID,
):
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        handler = GetHandler.ratechart_handler(request)
        query = GetRateChartQuery(id=ratechart_id, owner=user)
        dto = await handler.get(query=query)
        if not dto:
            raise HTTPException(status_code=404, detail="Rate Chart not found")

        res_data = RateChartDetailResponse.model_validate(dto)

        # Load child config
        if dto.chart_type in (RateChartType.FORMULA, 0):
            try:
                res_data.formula_config = await handler.get_formula_config(ratechart_id)
            except Exception:
                pass
        elif dto.chart_type in (RateChartType.CSV, RateChartType.TEXT, 1, 3):
            try:
                grids = await handler.get_grid_rows(ratechart_id)
                res_data.grids_data = [{"fat": float(g.fat), "snf": float(g.snf), "rate": float(g.rate)} for g in grids]
            except Exception:
                pass
        elif dto.chart_type in (RateChartType.PRODATA, 2):
            try:
                prodata = await handler.get_prodata_rows(ratechart_id)
                res_data.prodata_data = [
                    {
                        "fat_min": float(p.fat_min),
                        "fat_max": float(p.fat_max),
                        "snf_min": float(p.snf_min) if p.snf_min is not None else None,
                        "snf_max": float(p.snf_max) if p.snf_max is not None else None,
                        "kg_fat_rate": float(p.fat_rate_per_kg) if p.fat_rate_per_kg is not None else 0.0,
                        "kg_snf_rate": float(p.snf_rate_per_kg) if p.snf_rate_per_kg is not None else 0.0,
                        "snf_cut_off": float(p.snf_cutoff) if p.snf_cutoff is not None else 0.0,
                        "snf_deduction": float(p.snf_deduction) if p.snf_deduction is not None else 0.0,
                    }
                    for p in prodata
                ]
            except Exception:
                pass

        return res_data
    except RateChartNotFoundException:
        raise HTTPException(status_code=404, detail="Rate Chart not found")
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve rate chart: {str(e)}")


@router.post("", response_model=RateChartDetailResponse)
@router.post("/", response_model=RateChartDetailResponse)
async def create_rate_chart(
    request: Request,
    body: CreateRateChartApiRequest,
):
    """
    Create a new Rate Chart (Formula, Grid/CSV, or Prodata).
    Matches web controller behavior.
    """
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.ratechart_handler(request)

    # Coerce Enums & Fields
    try:
        chart_type_val = RateChartType(int(body.chart_type.value))
    except Exception:
        chart_type_val = RateChartType.FORMULA

    try:
        milk_type_val = MilkType(int(body.milk_type.value))
    except Exception:
        milk_type_val = MilkType.MIXED

    raw_calc = body.calculation_type
    try:
        calc_type_val = RateCalculationType(int(raw_calc.value))
    except Exception:
        calc_type_val = RateCalculationType.FAT_AND_SNF

    raw_eff = body.effective_from or body.effective_date
    if isinstance(raw_eff, str) and raw_eff.strip():
        try:
            eff_from = date.fromisoformat(raw_eff.strip())
        except Exception:
            eff_from = date.today()
    elif isinstance(raw_eff, date):
        eff_from = raw_eff
    else:
        eff_from = date.today()

    status_raw = body.status.ACTIVE
    if isinstance(status_raw, bool):
        status_val = RateChartStatus.ACTIVE if status_raw else RateChartStatus.INACTIVE
    else:
        try:
            status_val = RateChartStatus(int(status_raw.value))
        except Exception:
            status_val = RateChartStatus.ACTIVE

    command = CreateRateChartCommand(
        chart_name=body.chart_name.strip(),
        chart_type=chart_type_val,
        milk_type=milk_type_val,
        calculation_type=calc_type_val,
        effective_from=eff_from,
        effective_to=body.effective_to,
        status=status_val,
        description=body.description,
        created_by=user.id,
    )

    result = await handler.create(command)
    if not result:
        raise HTTPException(status_code=400, detail="Unable to create rate chart")

    # Handle child configurations
    if chart_type_val == RateChartType.FORMULA:
        fc = body.formula_config

        formula_cmd = SaveFormulaConfigCommand(
            rate_chart_id=result.id,
            milk_type=milk_type_val,
            cow_standard_fat=fc.cow_standard_fat if fc else 0.0,
            cow_standard_snf=fc.cow_standard_snf if fc else 0.0,
            cow_standard_rate=fc.cow_standard_rate if fc else 0.0,
            buffalo_standard_fat=fc.buffalo_standard_fat if fc else 0.0,
            buffalo_standard_snf=fc.buffalo_standard_snf if fc else 0.0,
            buffalo_standard_rate=fc.buffalo_standard_rate if fc else 0.0,
            cow_fat_percentage=fc.cow_fat_percentage if fc else 0.0,
            cow_snf_percentage=fc.cow_snf_percentage if fc else 0.0,
            buffalo_fat_percentage=fc.buffalo_fat_percentage if fc else 0.0,
            buffalo_snf_percentage=fc.buffalo_snf_percentage if fc else 0.0,
        )
        await handler.save_formula_config(formula_cmd, user)

    elif chart_type_val in (RateChartType.CSV, RateChartType.TEXT):
        if body.grids:
            rows = [
                GridRowInput(
                    row_number=g.row_number or (idx + 1),
                    fat=g.fat,
                    snf=g.snf,
                    rate=g.rate,
                )
                for idx, g in enumerate(body.grids)
            ]
            await handler.save_grid_rows(SaveGridRowsCommand(rate_chart_id=result.id, rows=rows), user)

    elif chart_type_val == RateChartType.PRODATA:
        if body.prodata_rows:
            rows = [
                ProdataRowInput(
                    row_number=r.row_number or (idx + 1),
                    fat_min=r.fat_min,
                    fat_max=r.fat_max,
                    snf_min=r.snf_min,
                    snf_max=r.snf_max,
                    fat_rate_per_kg=r.kg_fat_rate,
                    snf_rate_per_kg=r.kg_snf_rate,
                    snf_cutoff=r.snf_cut_off,
                    snf_deduction=r.snf_deduction,
                )
                for idx, r in enumerate(body.prodata_rows)
            ]
            await handler.save_prodata_rows(SaveProdataRowsCommand(rate_chart_id=result.id, rows=rows), user)

    chart_dto = await handler.get(GetRateChartQuery(id=result.id, owner=user))
    res_data = RateChartDetailResponse.model_validate(chart_dto)

    if chart_type_val == RateChartType.FORMULA:
        try:
            res_data.formula_config = await handler.get_formula_config(result.id)
        except Exception:
            pass
    elif chart_type_val in (RateChartType.CSV, RateChartType.TEXT):
        try:
            grids = await handler.get_grid_rows(result.id)
            res_data.grids = [{"fat": float(g.fat), "snf": float(g.snf), "rate": float(g.rate)} for g in grids]
        except Exception:
            pass
    elif chart_type_val == RateChartType.PRODATA:
        try:
            prodata = await handler.get_prodata_rows(result.id)
            res_data.prodata_rows = [
                {
                    "fat_min": float(p.fat_min),
                    "fat_max": float(p.fat_max),
                    "snf_min": float(p.snf_min) if p.snf_min is not None else None,
                    "snf_max": float(p.snf_max) if p.snf_max is not None else None,
                    "kg_fat_rate": float(p.fat_rate_per_kg) if p.fat_rate_per_kg is not None else 0.0,
                    "kg_snf_rate": float(p.snf_rate_per_kg) if p.snf_rate_per_kg is not None else 0.0,
                    "snf_cut_off": float(p.snf_cutoff) if p.snf_cutoff is not None else 0.0,
                    "snf_deduction": float(p.snf_deduction) if p.snf_deduction is not None else 0.0,
                }
                for p in prodata
            ]
        except Exception:
            pass
    await handler.create_assignment(
        command = CreateRateChartAssignmentCommand(
                rate_chart_id=result.id, 
                owner_id=user.id, 
                owner_type=user.role_type,
                created_by=user.id,
                priority=0,
                is_default=False
            )
        )
    return res_data


@router.delete("/{ratechart_id}")
async def delete_rate_chart(
    request: Request,
    ratechart_id: UUID,
):
    user: CurrentUser | None = getattr(request.state, "user", None)
    if not user:
        raise HTTPException(status_code=401, detail="Unauthorized")

    handler = GetHandler.ratechart_handler(request)
    await handler.delete(DeleteRateChartCommand(id=ratechart_id, owner=user))
    return {"status": True, "message": "Rate chart deleted successfully"}
