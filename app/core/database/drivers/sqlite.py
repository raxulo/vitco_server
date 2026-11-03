"""
RealTimeTransfer
================

Enterprise SQLite Driver

Python 3.13+
"""

from __future__ import annotations

from sqlalchemy import event

from app.core.config import config
from app.core.database.base import Base
from app.core.database.drivers.base import BaseDatabaseDriver
from app.core.database.engine import (
    EngineFactory,
    EngineOptions,
)
from app.core.database.session import SessionManager


class SQLiteDriver(BaseDatabaseDriver):
    """
    Enterprise SQLite Driver.
    """

    __slots__ = ()

    @property
    def name(self) -> str:
        return "sqlite"

    async def connect(self) -> None:
        if self.connected:
            return

        # Ensure parent directory exists for SQLite
        from pathlib import Path
        url = config.database.url
        if url.startswith("sqlite+aiosqlite:///"):
            db_path = url.replace("sqlite+aiosqlite:///", "")
            if not db_path.startswith(":memory:") and db_path != "":
                path = Path(db_path)
                if not path.is_absolute():
                    from app.config.settings import BASE_DIR
                    path = BASE_DIR / path
                path.parent.mkdir(parents=True, exist_ok=True)

        options = EngineOptions(
            url=config.database.url,
            echo=config.database.echo,
        )

        self._engine = EngineFactory.create(options)
        self._install_events()
        self._session_manager = SessionManager(self.engine)

        # Create tables & auto-migrate columns (development only)
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            def _sync_alter(raw_conn):
                try:
                    cur = raw_conn.cursor()
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='animals';")
                    if cur.fetchone():
                        cur.execute("PRAGMA table_info(animals);")
                        cols = [c[1] for c in cur.fetchall()]
                        if "image_url" not in cols:
                            cur.execute("ALTER TABLE animals ADD COLUMN image_url VARCHAR(500);")
                        if "images" not in cols:
                            cur.execute("ALTER TABLE animals ADD COLUMN images JSON;")
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='marketplace_orders';")
                    if cur.fetchone():
                        cur.execute("PRAGMA table_info(marketplace_orders);")
                        cols = [c[1] for c in cur.fetchall()]
                        if "buyer_id" not in cols:
                            # Nullable: older / guest orders have no buyer
                            cur.execute("ALTER TABLE marketplace_orders ADD COLUMN buyer_id UUID REFERENCES users(id);")
                            cur.execute("CREATE INDEX IF NOT EXISTS ix_marketplace_orders_buyer_id ON marketplace_orders (buyer_id);")
                    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='vlcc_master';")
                    if cur.fetchone():
                        cur.execute("PRAGMA table_info(vlcc_master);")
                        cols = [c[1] for c in cur.fetchall()]
                        if "vlcc_type" not in cols:
                            # Existing VLCCs are normal (VlccType.NORMAL = 0)
                            cur.execute("ALTER TABLE vlcc_master ADD COLUMN vlcc_type SMALLINT NOT NULL DEFAULT 0;")
                    cur.close()
                except Exception:
                    pass
            await conn.run_sync(lambda raw_conn: _sync_alter(raw_conn.connection))
            
        self._connected = True

    async def disconnect(self) -> None:
        if not self.connected:
            return

        await self.engine.dispose()
        self._engine = None
        self._session_manager = None
        self._connected = False

    def _install_events(self) -> None:
        @event.listens_for(
            self.engine.sync_engine,
            "connect",
        )
        def sqlite_connect(dbapi_connection, connection_record) -> None:
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON")
            cursor.execute("PRAGMA journal_mode=WAL")
            cursor.execute("PRAGMA synchronous=NORMAL")
            cursor.execute("PRAGMA busy_timeout=5000")
            cursor.execute("PRAGMA temp_store=MEMORY")
            cursor.execute("PRAGMA mmap_size=268435456")
            cursor.execute("PRAGMA cache_size=-64000")
            cursor.execute("PRAGMA optimize")
            cursor.close()