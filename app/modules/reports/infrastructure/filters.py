
from app.modules.administration.domain.enums import Role
from pydantic import Field
from datetime import date
from dataclasses import dataclass


@dataclass(slots=True)
class AppliedOnFilters:
    """Represents filters to be applied on the report"""

    actor_type: Role
    date: bool = False
    date_range: bool = False
    shift: bool = False
    shift_range: bool = False
    milk_type: bool = False
    mcc_id: bool = False
    vlcc_id: bool = False
    route_code: bool = False
    farmer_code: bool = False
    code: bool = False
    code_range: bool = False
    is_deleted: bool = False


    