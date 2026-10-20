from app.modules.collections.mcc_collection.domain.enums import MilkType
from app.modules.collections.mcc_collection.domain.enums import CollectionShift
from datetime import date
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.validators import indian_date, optional_digits
from app.modules.reports.domain.enums import ReportType
from app.modules.reports.application.queries import ReportQuery

from uuid import UUID

from pydantic import BaseModel, Field


class ReportPreviewRequest(BaseModel):
    mcc_id: UUID | None = None
    vlcc_id: UUID | None = None
    report_type: ReportType

    start_date: date | None = None
    end_date: date | None = None

    start_shift: CollectionShift | None = None
    end_shift: CollectionShift | None = None

    milk_type: MilkType | None = None

    route_code: str | None = None
    # Member of the report's owner: farmer code for VLCC reports, VLCC code for MCC reports
    member_code: str | None = None

    code_from: str | None = None
    code_to: str | None = None
    route_from: str | None = None
    route_to: str | None = None

    page: int = Field(default=1, ge=1)
    size: int = Field(default=100, ge=1, le=500)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _dates(cls, value, info):
        return indian_date(value, info.field_name.replace("_", " ").capitalize())

    @field_validator("code_from", "code_to", "member_code", "route_from", "route_to", mode="before")
    @classmethod
    def _codes(cls, value, info):
        return optional_digits(value, info.field_name.replace("_", " ").capitalize())

    def to_query(
        self,
        *,
        actor_id: UUID,
    ) -> ReportQuery:

        return ReportQuery(
            actor_id=actor_id,
            report_type=self.report_type,

            start_date=self.start_date,
            end_date=self.end_date,

            milk_type=self.milk_type,

            mcc_id=self.mcc_id,
            vlcc_id=self.vlcc_id,

            route_code=self.route_code,
            member_code=self.member_code.strip() if self.member_code else None,

            code_from=self.code_from,
            code_to=self.code_to,
            route_from=self.route_from,
            route_to=self.route_to,

            start_shift=self.start_shift,
            end_shift=self.end_shift,

            page=self.page,
            size=self.size,
        )

class ReportRequest(BaseModel):

    dairy_id: str | None = None

    start_date: date | None = None
    end_date: date | None = None

    shift: int | None = Field(default=None, ge=0, le=1)
    milk_type: int | None = Field(default=None, ge=0, le=2)

    mcc_id: str | None = None
    vlcc_id: str | None = None

    route_code: str | None = None
    member_code: str | None = None

    code_from: str | None = None
    code_to: str | None = None

    start_shift: int | None = Field(default=None, ge=0, le=1)
    end_shift: int | None = Field(default=None, ge=0, le=1)

    page: int = Field(default=1, ge=1)
    size: int = Field(default=100, ge=1, le=1000)

    @field_validator("start_date", "end_date", mode="before")
    @classmethod
    def _dates(cls, value, info):
        return indian_date(value, info.field_name.replace("_", " ").capitalize())

    @field_validator("code_from", "code_to", "member_code", mode="before")
    @classmethod
    def _codes(cls, value, info):
        return optional_digits(value, info.field_name.replace("_", " ").capitalize())

    def to_query(
        self,
        *,
        actor_id: UUID,
        report_type: ReportType,
    ) -> ReportQuery:

        return ReportQuery(
            actor_id=actor_id,
            report_type=report_type,

            start_date=self.start_date,
            end_date=self.end_date,

            milk_type=self.milk_type,

            mcc_id=self.mcc_id,
            vlcc_id=self.vlcc_id,

            route_code=self.route_code,
            member_code=self.member_code.strip() if self.member_code else None,

            code_from=self.code_from,
            code_to=self.code_to,

            start_shift=self.start_shift,
            end_shift=self.end_shift,

            page=self.page,
            size=self.size,
        )