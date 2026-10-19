"""
Admin Entity
"""

from uuid import UUID
from sqlalchemy.orm import Mapped
from sqlalchemy import ForeignKey
from app.core.database.base import Base
from app.core.database.mixins import TimestampMixin, UUIDMixin

from sqlalchemy import String
from sqlalchemy.orm import mapped_column

class AddressModel(Base, UUIDMixin,TimestampMixin):

    __tablename__ = "addresses"

    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"), nullable=False,unique=True,index=True)
    line: Mapped[str | None] = mapped_column(String(255), nullable=True)
    state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    city: Mapped[str | None] = mapped_column(String(255), nullable=True)
    pincode: Mapped[str | None] = mapped_column(String(10), nullable=True)