from __future__ import annotations

from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.infrastructure.models import ExcelJobModel


class ExcelJobMapper:

    @staticmethod
    def to_entity(model: ExcelJobModel) -> ExcelJob:
        return ExcelJob(
            id=model.id,
            kind=model.kind,
            status=model.status,
            created_by=model.created_by,
            owner_role=model.owner_role,
            owner_own_id=model.owner_own_id,
            target_id=model.target_id,
            mode=model.mode,
            dry_run=model.dry_run,
            source_file=model.source_file,
            result_file=model.result_file,
            report_file=model.report_file,
            total_rows=model.total_rows,
            processed_rows=model.processed_rows,
            inserted=model.inserted,
            updated=model.updated,
            discarded=model.discarded,
            error_message=model.error_message,
            cancel_requested=model.cancel_requested,
            worker_pid=model.worker_pid,
            heartbeat_at=model.heartbeat_at,
            created_at=model.created_at,
            started_at=model.started_at,
            finished_at=model.finished_at,
            updated_at=model.updated_at,
        )

    @staticmethod
    def to_model(entity: ExcelJob) -> ExcelJobModel:
        return ExcelJobModel(
            id=entity.id,
            kind=entity.kind,
            status=entity.status,
            created_by=entity.created_by,
            owner_role=entity.owner_role,
            owner_own_id=entity.owner_own_id,
            target_id=entity.target_id,
            mode=entity.mode,
            dry_run=entity.dry_run,
            source_file=entity.source_file,
            result_file=entity.result_file,
            report_file=entity.report_file,
            total_rows=entity.total_rows,
            processed_rows=entity.processed_rows,
            inserted=entity.inserted,
            updated=entity.updated,
            discarded=entity.discarded,
            error_message=entity.error_message,
            cancel_requested=entity.cancel_requested,
            worker_pid=entity.worker_pid,
            heartbeat_at=entity.heartbeat_at,
            created_at=entity.created_at,
            started_at=entity.started_at,
            finished_at=entity.finished_at,
            updated_at=entity.updated_at,
        )
