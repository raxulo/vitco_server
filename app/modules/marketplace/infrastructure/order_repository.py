"""
Orders repository.

Python 3.13+
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import func, or_, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.database.manager import DatabaseManager
from app.modules.marketplace.domain.entities import ListingViewer
from app.modules.marketplace.domain.enums import OrderStatus, ProductStatus
from app.modules.marketplace.domain.exceptions import DuplicateCheckoutException
from app.modules.marketplace.domain.irepository import IOrderRepository
from app.modules.marketplace.domain.orders import CartVariant, Order, OrderLine, OrderSummary
from app.modules.marketplace.infrastructure.models import (
    MarketplaceCategoryModel,
    MarketplaceOrderItemModel,
    MarketplaceOrderModel,
    MarketplaceProductModel,
    MarketplaceProductVariantModel,
)
from app.modules.marketplace.infrastructure.repository import MarketplaceAccessScope

_CHUNK = 200


def _order(model: MarketplaceOrderModel) -> Order:
    return Order(
        id=model.id, order_ref=model.order_ref, checkout_token=model.checkout_token, buyer_user_id=model.buyer_user_id,
        buyer_name=model.buyer_name, buyer_phone=model.buyer_phone, address_line=model.address_line, city=model.city,
        state=model.state, pincode=model.pincode, notes=model.notes, subtotal=model.subtotal,
        delivery_charge=model.delivery_charge, total=model.total, payment_method=model.payment_method,
        payment_status=model.payment_status, status=model.status, cancel_reason=model.cancel_reason,
        created_at=model.created_at,
        lines=[
            OrderLine(
                id=item.id, product_id=item.product_id, variant_id=item.variant_id, seller_user_id=item.seller_user_id,
                product_title=item.product_title, variant_name=item.variant_name, image_url=item.image_url,
                mrp=item.mrp, unit_price=item.unit_price, quantity=item.quantity, line_total=item.line_total,
            )
            for item in model.items
        ],
    )


class OrderRepository(IOrderRepository):

    __slots__ = ("_database",)

    def __init__(self, database: DatabaseManager) -> None:
        self._database = database

    @property
    def _session(self) -> AsyncSession:
        return self._database.session

    # =========================================================
    # CART
    # =========================================================

    async def cart_variants(self, variant_ids: set[UUID]) -> list[CartVariant]:
        if not variant_ids:
            return []
        rows = await self._session.execute(
            select(MarketplaceProductVariantModel, MarketplaceProductModel)
            .join(MarketplaceProductModel, MarketplaceProductModel.id == MarketplaceProductVariantModel.product_id)
            .join(MarketplaceCategoryModel, MarketplaceCategoryModel.id == MarketplaceProductModel.category_id)
            .where(
                MarketplaceProductVariantModel.id.in_(list(variant_ids)[:_CHUNK]),
                MarketplaceProductVariantModel.is_active.is_(True),
                MarketplaceProductModel.is_deleted.is_(False),
                MarketplaceProductModel.status == ProductStatus.PUBLISHED,
                MarketplaceCategoryModel.is_active.is_(True),
            )
            .options(selectinload(MarketplaceProductModel.images))
        )
        return [
            CartVariant(
                variant_id=variant.id, product_id=product.id, seller_user_id=product.seller_user_id, slug=product.slug,
                title=product.title, size=variant.name, price=variant.price, mrp=variant.mrp, stock=variant.stock,
                image_url=product.images[0].url if product.images else None,
            )
            for variant, product in rows
        ]

    async def take_stock(self, variant_id: UUID, quantity: int) -> bool:
        result = await self._session.execute(
            update(MarketplaceProductVariantModel)
            .where(
                MarketplaceProductVariantModel.id == variant_id,
                MarketplaceProductVariantModel.is_active.is_(True),
                MarketplaceProductVariantModel.stock >= quantity,
            )
            .values(stock=MarketplaceProductVariantModel.stock - quantity)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1

    async def return_stock(self, variant_id: UUID, quantity: int) -> None:
        await self._session.execute(
            update(MarketplaceProductVariantModel)
            .where(MarketplaceProductVariantModel.id == variant_id)
            .values(stock=MarketplaceProductVariantModel.stock + quantity)
            .execution_options(synchronize_session=False)
        )

    # =========================================================
    # ORDERS
    # =========================================================

    async def ref_for_token(self, checkout_token: str) -> str | None:
        return await self._session.scalar(
            select(MarketplaceOrderModel.order_ref).where(MarketplaceOrderModel.checkout_token == checkout_token)
        )

    async def add_order(self, order: Order) -> None:
        model = MarketplaceOrderModel(
            id=order.id, order_ref=order.order_ref, checkout_token=order.checkout_token,
            buyer_user_id=order.buyer_user_id, buyer_name=order.buyer_name, buyer_phone=order.buyer_phone,
            address_line=order.address_line, city=order.city, state=order.state, pincode=order.pincode,
            notes=order.notes, subtotal=order.subtotal, delivery_charge=order.delivery_charge, total=order.total,
            payment_method=order.payment_method, payment_status=order.payment_status, status=order.status,
            items=[
                MarketplaceOrderItemModel(
                    id=line.id, product_id=line.product_id, variant_id=line.variant_id,
                    seller_user_id=line.seller_user_id, product_title=line.product_title,
                    variant_name=line.variant_name, image_url=line.image_url, mrp=line.mrp, unit_price=line.unit_price,
                    quantity=line.quantity, line_total=line.line_total,
                )
                for line in order.lines
            ],
        )
        self._session.add(model)
        try:
            await self._session.flush()
        except IntegrityError as error:
            raise DuplicateCheckoutException() from error

    async def find_for_tracking(self, order_ref: str, phone: str) -> Order | None:
        model = await self._session.scalar(
            select(MarketplaceOrderModel)
            .where(MarketplaceOrderModel.order_ref == order_ref, MarketplaceOrderModel.buyer_phone == phone)
            .options(selectinload(MarketplaceOrderModel.items))
        )
        return None if model is None else _order(model)

    async def get_by_ref(self, order_ref: str) -> Order | None:
        model = await self._session.scalar(
            select(MarketplaceOrderModel)
            .where(MarketplaceOrderModel.order_ref == order_ref)
            .options(selectinload(MarketplaceOrderModel.items))
        )
        return None if model is None else _order(model)

    @staticmethod
    def _visible(viewer: ListingViewer):
        """Orders holding at least one of the viewer's lines; Super Admin sees all."""
        return MarketplaceOrderModel.id.in_(
            select(MarketplaceOrderItemModel.order_id).where(
                MarketplaceAccessScope.condition(viewer, MarketplaceOrderItemModel.seller_user_id)
            )
        )

    async def list_orders(
        self, viewer: ListingViewer, keyword: str | None, status: OrderStatus | None, offset: int, limit: int
    ) -> tuple[list[OrderSummary], int]:
        stmt = select(MarketplaceOrderModel).where(self._visible(viewer))
        if status is not None:
            stmt = stmt.where(MarketplaceOrderModel.status == status)
        if keyword and keyword.strip():
            term = keyword.strip()
            stmt = stmt.where(or_(
                MarketplaceOrderModel.order_ref.icontains(term, autoescape=True),
                MarketplaceOrderModel.buyer_name.icontains(term, autoescape=True),
                MarketplaceOrderModel.buyer_phone.icontains(term, autoescape=True),
            ))
        total = await self._session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
        page = (
            stmt.options(selectinload(MarketplaceOrderModel.items))
            .order_by(MarketplaceOrderModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        return [
            OrderSummary(
                id=model.id, order_ref=model.order_ref, buyer_name=model.buyer_name, buyer_phone=model.buyer_phone,
                pincode=model.pincode, total=model.total, status=model.status, payment_status=model.payment_status,
                item_count=sum(item.quantity for item in model.items), created_at=model.created_at,
            )
            for model in await self._session.scalars(page)
        ], total

    async def get_order(self, order_id: UUID, viewer: ListingViewer) -> Order | None:
        model = await self._session.scalar(
            select(MarketplaceOrderModel)
            .where(MarketplaceOrderModel.id == order_id, self._visible(viewer))
            .options(selectinload(MarketplaceOrderModel.items))
            .execution_options(populate_existing=True)
        )
        return None if model is None else _order(model)

    async def move_order(self, order: Order, from_status: OrderStatus) -> bool:
        result = await self._session.execute(
            update(MarketplaceOrderModel)
            .where(MarketplaceOrderModel.id == order.id, MarketplaceOrderModel.status == from_status)
            .values(status=order.status, payment_status=order.payment_status, cancel_reason=order.cancel_reason)
            .execution_options(synchronize_session=False)
        )
        return result.rowcount == 1
