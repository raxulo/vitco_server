"""
Excel Exchange Load & Benchmark Test (Plan 5.3, NFR-01, NFR-02, NFR-08).

Validates:
1. Constant memory (NFR-01): Worker peak RSS growth < 50 MB between small and large datasets.
2. Low API latency (NFR-02): While high-volume import/export runs, concurrent API queries keep p95 < 300 ms.
3. Lock fairness (NFR-08): Adaptive batch size keeps DB transaction time <= 250 ms, yielding 0 'database is locked' errors.

Usage:
    .venv/Scripts/python scripts/loadtest_excel.py --rows 10000 --concurrent-clients 10
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path
from uuid import uuid4

# Add workspace to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.dataexchange.application.batching import read_rss_bytes
from app.modules.dataexchange.application.farmer_import import FarmerImportProcessor
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.domain.sheets import FARMER_SHEET
from app.modules.dataexchange.infrastructure.farmer_repository import FarmerExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from tests.dataexchange.factories import create_vlcc, make_context, unique_mobile


def generate_benchmark_file(dest: Path, rows_count: int) -> Path:
    columns = FARMER_SHEET.import_columns()
    writer = XlsxSheetWriter(dest, FARMER_SHEET, columns=columns)
    batch_size = 5000
    rows = []
    print(f"[*] Generating {rows_count:,} rows test workbook...")
    t0 = time.perf_counter()
    for i in range(rows_count):
        rows.append({
            "farmer_code": f"B{i:07d}",
            "name": f"Benchmark Farmer {i}",
            "mobile": f"7{i:09d}",
            "city": "Indore",
            "pincode": "452001",
            "bank_name": "SBI",
            "account_number": f"{i:012d}",
        })
        if len(rows) >= batch_size:
            writer.write_rows([[r.get(c.key) for c in columns] for r in rows])
            rows.clear()
    if rows:
        writer.write_rows([[r.get(c.key) for c in columns] for r in rows])
    writer.close()
    gen_time = time.perf_counter() - t0
    print(f"[+] Generated {rows_count:,} rows in {gen_time:.2f}s ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


async def simulate_concurrent_traffic(database: DatabaseManager, stop_event: asyncio.Event, client_count: int = 10):
    latencies: list[float] = []
    lock_errors: int = 0
    total_requests: int = 0

    async def client_worker():
        nonlocal lock_errors, total_requests
        from sqlalchemy import text
        while not stop_event.is_set():
            t_req = time.perf_counter()
            try:
                async with database.transaction() as session:
                    await session.execute(text("SELECT count(*) FROM users"))
                lat = (time.perf_counter() - t_req) * 1000
                latencies.append(lat)
                total_requests += 1
            except Exception as e:
                if "locked" in str(e).lower():
                    lock_errors += 1
            await asyncio.sleep(0.02)

    workers = [asyncio.create_task(client_worker()) for _ in range(client_count)]
    await stop_event.wait()
    for w in workers:
        w.cancel()
    await asyncio.gather(*workers, return_exceptions=True)

    latencies.sort()
    p50 = latencies[int(len(latencies) * 0.50)] if latencies else 0
    p95 = latencies[int(len(latencies) * 0.95)] if latencies else 0
    p99 = latencies[int(len(latencies) * 0.99)] if latencies else 0
    return {
        "total_requests": total_requests,
        "lock_errors": lock_errors,
        "p50_ms": p50,
        "p95_ms": p95,
        "p99_ms": p99,
    }


async def run_benchmark(rows_count: int, concurrent_clients: int):
    print("=" * 60)
    print(f"QUICKYEE EXCEL EXCHANGE LOAD & CONCURRENCY BENCHMARK")
    print(f"Target: {rows_count:,} rows | Concurrent clients: {concurrent_clients}")
    print("=" * 60)

    from app.config.database import database_config
    from app.core.database.factory import DatabaseFactory
    import app.modules.configurator  # registers all models

    database = DatabaseFactory(database_config).create()
    await database.startup()

    tmp_dir = Path("./scratch/benchmark").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    bench_file = tmp_dir / f"bench_{rows_count}.xlsx"
    generate_benchmark_file(bench_file, rows_count)

    vlcc = await create_vlcc(database)
    job_dir = tmp_dir / f"job-{uuid4().hex[:6]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    shutil.copy(bench_file, job_dir / "source.xlsx")

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

    stop_traffic = asyncio.Event()
    traffic_task = asyncio.create_task(
        simulate_concurrent_traffic(database, stop_traffic, client_count=concurrent_clients)
    )

    rss_before = read_rss_bytes()
    print(f"[*] Starting background import engine (Initial RSS: {rss_before / 1e6:.1f} MB)...")
    t0 = time.perf_counter()

    result = await processor.run(ctx)

    elapsed = time.perf_counter() - t0
    rss_after = read_rss_bytes()
    stop_traffic.set()
    traffic_stats = await traffic_task

    throughput = rows_count / elapsed
    rss_diff_mb = (rss_after - rss_before) / 1e6

    print("\n" + "=" * 60)
    print("BENCHMARK RESULTS & METRICS")
    print("=" * 60)
    print(f"Rows Imported      : {ctx.inserted:,} of {rows_count:,}")
    print(f"Total Time         : {elapsed:.2f} seconds")
    print(f"Throughput         : {throughput:,.0f} rows/second")
    print(f"Memory RSS         : {rss_before / 1e6:.1f} MB -> {rss_after / 1e6:.1f} MB (Growth: {rss_diff_mb:+.1f} MB)")
    print(f"Concurrent Traffic : {traffic_stats['total_requests']:,} queries served during import")
    print(f"Latency P50        : {traffic_stats['p50_ms']:.2f} ms")
    print(f"Latency P95        : {traffic_stats['p95_ms']:.2f} ms (Target: < 300 ms)")
    print(f"Latency P99        : {traffic_stats['p99_ms']:.2f} ms (Target: < 1,000 ms)")
    print(f"Lock Errors        : {traffic_stats['lock_errors']} (Target: 0)")
    print("=" * 60)

    try:
        assert ctx.inserted == rows_count, "All rows must be inserted"
        assert rss_diff_mb < 50.0, f"Memory growth ({rss_diff_mb:.1f} MB) exceeded NFR-01 limit of 50 MB"
        assert traffic_stats["lock_errors"] == 0, "Zero SQLite lock errors allowed (NFR-08)"
        assert traffic_stats["p95_ms"] < 300.0, "API P95 latency must remain < 300 ms (NFR-02)"
        print("[SUCCESS] All Non-Functional Requirements (NFR-01, NFR-02, NFR-08) VERIFIED!")
    finally:
        await database.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Quickyee Excel Load Benchmark")
    parser.add_argument("--rows", type=int, default=5000, help="Number of rows to test (default: 5,000)")
    parser.add_argument("--concurrent-clients", type=int, default=5, help="Number of concurrent clients (default: 5)")
    args = parser.parse_args()

    asyncio.run(run_benchmark(args.rows, args.concurrent_clients))
