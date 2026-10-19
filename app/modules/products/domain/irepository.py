from abc import ABC, abstractmethod
from uuid import UUID

from app.modules.products.domain.entities import Product, ProductImage


class IProductRepository(ABC):

    @abstractmethod
    async def create(self, entity: Product) -> None:
        ...

    @abstractmethod
    async def update(self, entity: Product) -> None:
        ...

    @abstractmethod
    async def get_by_id(self, id: UUID) -> Product | None:
        ...

    @abstractmethod
    async def list(self, offset: int, limit: int) -> list[Product]:
        ...

    @abstractmethod
    async def count(self) -> int:
        ...

    @abstractmethod
    async def add_image(self, entity: ProductImage) -> None:
        ...

    @abstractmethod
    async def get_images(self, product_id: UUID) -> list[ProductImage]:
        ...
