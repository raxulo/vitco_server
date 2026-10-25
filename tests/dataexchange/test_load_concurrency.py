"""
Automated Concurrency & Latency Test (Plan 5.3, NFR-01, NFR-02, NFR-08).
Verifies that during background import processing:
- Concurrent read queries experience 0 database lock errors.
- API response latency remains low.
- Worker memory remains bounded.
"""

from __future__ import annotations

import asyncio
import time
from uuid import uuid4

import pytest
from sqlalchemy import text

from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.dataexchange.application.batching import read_rss_bytes
from app.modules.dataexchange.application.farmer_import import FarmerImportProcessor
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.domain.sheets import FARMER_SHEET
from app.modules.dataexchange.infrastructure.farmer_repository import FarmerExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from tests.dataexchange.factories import create_vlcc, make_context, unique_mobile


async def test_concurrent_api_traffic_during_bulk_import(database, tmp_path):
    vlcc = await create_vlcc(database)
    rows_count = 1500

    # Write test rows
    columns = FARMER_SHEET.import_columns()
    source_path = tmp_path / "concurrent_test.xlsx"
    writer = XlsxSheetWriter(source_path, FARMER_SHEET, columns=columns)
    dict_rows = [
        {"farmer_code": f"L{i:05d}", "name": f"Load Farmer {i}", "mobile": f"9{i:09d}",
         "city": "Indore", "pincode": "452001", "bank_name": "SBI", "account_number": f"{i:012d}"}
        for i in range(rows_count)
    ]
    writer.write_rows([[r.get(c.key) for c in columns] for r in dict_rows])
    writer.close()

    job_dir = tmp_path / "job_load"
    job_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(source_path, job_dir / "source.xlsx")

    ctx = await make_context(
        database,
        kind=ExcelJobKind.FARMER_IMPORT,
        owner_id=vlcc.user_id,
        owner_role=Role.VLCC,
        target_id=vlcc.id,
        job_dir=job_dir,
        mode=ImportMode.UPSERT,
        source_file="source.xlsx",
    )

    processor = FarmerImportProcessor(
        database=database,
        repository=FarmerExchangeRepository(database),
        password_service=PasswordService(),
    )

    stop_event = asyncio.Event()
    latencies: list[float] = []
    lock_errors: int = 0

    async def traffic_simulator():
        nonlocal lock_errors
        while not stop_event.is_set():
            t0 = time.perf_counter()
            try:
                async with database.transaction() as session:
                    await session.execute(text("SELECT count(*) FROM users"))
                latencies.append((time.perf_counter() - t0) * 1000)
            except Exception as e:
                if "locked" in str(e).lower():
                    lock_errors += 1
            await asyncio.sleep(0.01)

    traffic_task = asyncio.create_task(traffic_simulator())
    rss_before = read_rss_bytes()

    await processor.run(ctx)

    stop_event.set()
    await traffic_task
    rss_after = read_rss_bytes()

    assert ctx.inserted == rows_count
    assert lock_errors == 0, "No SQLite lock contention errors allowed during bulk import"
    assert (rss_after - rss_before) / 1e6 < 50.0, "RSS memory growth must be < 50 MB"
    if latencies:
        latencies.sort()
        p95 = latencies[int(len(latencies) * 0.95)]
        assert p95 < 300.0, f"P95 query latency was {p95:.2f} ms (target < 300 ms)"
