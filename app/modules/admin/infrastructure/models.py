"""
Admin Entity
"""

from app.core.database.base import Base

from app.core.database.mixins import TimestampMixin
from app.core.database.mixins import UUIDMixin

from datetime import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    Enum,
    Integer,
    String,
    func,
)

from sqlalchemy.orm import (
    Mapped,
    mapped_column,
)

from app.modules.admin.domain.enums import AdminRole


class Admin(Base, UUIDMixin, TimestampMixin):

    __tablename__ = "admins"

    name: Mapped[str] = mapped_column( String(100), nullable=False )

    email: Mapped[str] = mapped_column( String(255), unique=True, nullable=False, index=True )

    password: Mapped[str] = mapped_column( String(255), nullable=False )

    role: Mapped[AdminRole] = mapped_column( Enum(AdminRole), nullable=False, default=AdminRole.ADMIN )

    is_active: Mapped[bool] = mapped_column( Boolean, default=True, nullable=False,)

    def __repr__(self):
        return f"<Admin {self.email}>"