"""
SQLAlchemy Metadata Configuration

Enterprise Database Layer

Python 3.13+
"""

from __future__ import annotations

from sqlalchemy import MetaData


__all__ = (
    "metadata",
)


# ============================================================
# Naming Convention
# ============================================================

NAMING_CONVENTION: dict[str, str] = {

    # Primary Key
    "pk": "pk_%(table_name)s",

    # Foreign Key
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",

    # Unique Constraint
    "uq": "uq_%(table_name)s_%(column_0_name)s",

    # Index
    "ix": "ix_%(table_name)s_%(column_0_name)s",

    # Check Constraint
    "ck": "ck_%(table_name)s_%(constraint_name)s",
}


# ============================================================
# Global Metadata
# ============================================================


metadata = MetaData(
    naming_convention=NAMING_CONVENTION,
)