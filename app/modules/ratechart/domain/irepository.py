from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.ratechart.domain.entities import (
    RateChart,
    RateFormulaConfig,
    RateGridRow,
    ProdataRateRow,
    RateChartAssignment,
)


from app.middleware.authentication import CurrentUser


class IRateChartRepository(ABC):

    @abstractmethod
    async def create(self, entity: RateChart) -> None:
        ...

    @abstractmethod
    async def update(self, entity: RateChart, owner: CurrentUser | None = None) -> None:
        ...

    @abstractmethod
    async def delete(self, id: UUID, owner: CurrentUser | None = None) -> None:
        ...

    @abstractmethod
    async def get_by_id(self, id: UUID, owner: CurrentUser | None = None) -> RateChart | None:
        ...

    @abstractmethod
    async def get_formula_config(self, rate_chart_id: UUID) -> RateFormulaConfig | None:
        ...

    @abstractmethod
    async def save_formula_config(self, config: RateFormulaConfig) -> None:
        ...

    @abstractmethod
    async def get_grid_rows(self, rate_chart_id: UUID) -> list[RateGridRow]:
        ...

    @abstractmethod
    async def save_grid_rows(self, rate_chart_id: UUID, rows: list[RateGridRow]) -> None:
        ...

    @abstractmethod
    async def get_prodata_rows(self, rate_chart_id: UUID) -> list[ProdataRateRow]:
        ...

    @abstractmethod
    async def save_prodata_rows(self, rate_chart_id: UUID, rows: list[ProdataRateRow]) -> None:
        ...

    @abstractmethod
    async def list(self, offset: int, limit: int, owner: CurrentUser | None = None) -> list[RateChart]:
        ...

    @abstractmethod
    async def search(self, keyword: str, offset: int, limit: int, owner: CurrentUser | None = None) -> list[RateChart]:
        ...

    @abstractmethod
    async def count(self, owner: CurrentUser | None = None) -> int:
        ...

    @abstractmethod
    async def count_search(self, keyword: str, owner: CurrentUser | None = None) -> int:
        ...

    @abstractmethod
    async def create_assignment(self, entity: RateChartAssignment) -> None:
        ...

    @abstractmethod
    async def update_assignment(self, entity: RateChartAssignment) -> None:
        ...

    @abstractmethod
    async def delete_assignment(self, id: UUID) -> None:
        ...

    @abstractmethod
    async def get_assignment_by_id(self, id: UUID) -> RateChartAssignment | None:
        ...

    @abstractmethod
    async def get_assignments_by_owner(self, owner_id: UUID) -> list[RateChartAssignment]:
        ...

    @abstractmethod
    async def list_assignments(self, offset: int, limit: int) -> list[RateChartAssignment]:
        ...

    @abstractmethod
    async def count_assignments(self) -> int:
        ...

    @abstractmethod
    async def delete_assignments_by_owner(self, owner_id: UUID) -> None:
        ...

    @abstractmethod
    async def get_assignments_by_owners(self, owner_ids: list[UUID]) -> list[RateChartAssignment]:
        """Active assignments of many owners in a single query."""
        ...
