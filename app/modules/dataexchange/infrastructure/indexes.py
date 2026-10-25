"""
Exchange Indexes

Indexes the bulk import relies on but that `create_all` cannot add to tables
which already exist. Created idempotently by the exchange worker at startup,
so a one-time build on a large table never blocks the API process.

Python 3.13+
"""

from __future__ import annotations

import time

from sqlalchemy import text

from app.core.database.manager import DatabaseManager
from app.core.logging.logger import get_logger

logger = get_logger("exchange_indexes")

# Case-insensitive email checks (`lower(email) IN (...)`, also used by the
# existing exists_email) become index searches instead of full table scans.
_STATEMENTS = (
    "CREATE INDEX IF NOT EXISTS ix_users_email_lower ON users (lower(email))",
)


async def ensure_indexes(database: DatabaseManager) -> None:
    for statement in _STATEMENTS:
        started = time.perf_counter()
        async with database.transaction() as session:
            await session.execute(text(statement))
        logger.info("index ready in %.0f ms: %s", (time.perf_counter() - started) * 1000, statement)
