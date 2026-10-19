from app.modules.masters.route.domain.dto import RouteMasterDto

from app.modules.masters.route.domain.entities import RouteMaster
from app.modules.masters.route.infrastructure.models import RouteMasterModel


class RouteMasterMapper:

    @staticmethod
    def to_entity(model: RouteMasterModel, owner_name: str | None = None, can_modify: bool = False) -> RouteMaster:
        return RouteMaster(
            id=model.id,
            route_code=model.route_code,
            route_name=model.route_name,
            is_active=model.is_active,
            created_by=model.created_by,
            created_at=model.created_at,
            updated_at=model.updated_at,
            owner_name=owner_name,
            can_modify=can_modify,
        )

    @staticmethod
    def to_model(entity: RouteMaster) -> RouteMasterModel:
        return RouteMasterModel(
            id=entity.id,
            route_code=entity.route_code,
            route_name=entity.route_name,
            is_active=entity.is_active,
            created_by=entity.created_by,
            created_at=entity.created_at,
            updated_at=entity.updated_at,
        )

    @staticmethod
    def to_short_dto(model: RouteMasterModel) -> RouteMasterDto:
        return RouteMasterDto(
            id=model.id,
            route_code=model.route_code,
            route_name=model.route_name,
            is_active=True,
        )