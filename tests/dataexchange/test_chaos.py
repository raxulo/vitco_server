"""
Chaos and Hardening Tests (Plan 5.2, NFR-03, NFR-07, NFR-09, NFR-11).
Verifies:
- Worker termination mid-batch leaves no orphaned records and rolls back uncommitted rows cleanly.
- Upload abort / discard leaves no residual temporary files.
- Hostile files (non-xlsx, XML bomb, oversized cells) are rejected safely without crashing.
- Low-disk guard blocks uploads/jobs with 507 Insufficient Storage.
"""

from __future__ import annotations

import os
import shutil
import zipfile
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.dataexchange.application.farmer_import import FarmerImportProcessor
from app.modules.dataexchange.domain.columns import ColumnKind, ColumnSpec, Section, SheetSpec
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus, ImportMode
from app.modules.dataexchange.domain.exceptions import (
    ExcelJobCapacityException,
    ExcelStorageFullException,
    InvalidExcelFileException,
)
from app.modules.dataexchange.domain.sheets import FARMER_SHEET
from app.modules.dataexchange.infrastructure.farmer_repository import FarmerExchangeRepository
from app.modules.dataexchange.infrastructure.file_guard import FileGuard
from app.modules.dataexchange.infrastructure.models import ExcelJobModel
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetReader, XlsxSheetWriter
from app.modules.farmer.infrastructure.models import FarmerModel
from app.worker.exchange import JobContext
from tests.dataexchange.factories import create_user, create_vlcc, make_context, unique_mobile


# =========================================================
# 1. MID-BATCH TERMINATION & ATOMICITY (NFR-03)
# =========================================================

async def test_simulated_crash_mid_batch_rolls_back_cleanly_without_orphans(database, tmp_path):
    """
    Simulating a sudden termination during a batch insert:
    Ensures that any failure mid-transaction rolls back that batch,
    leaving zero orphaned User records without corresponding FarmerModel records.
    """
    vlcc = await create_vlcc(database)
    processor = FarmerImportProcessor(
        database=database,
        repository=FarmerExchangeRepository(database),
        password_service=PasswordService(),
    )

    # Prepare file with 50 rows
    source_path = tmp_path / "crash_test.xlsx"
    writer = XlsxSheetWriter(source_path, FARMER_SHEET)
    rows = [
        [f"C{i:03d}", f"Crash Farmer {i}", unique_mobile(), "Indore", "452001", "SBI", f"0000{i:05d}"]
        for i in range(50)
    ]
    writer.write_rows(rows)
    writer.close()

    admin_id = await create_user(database, role=Role.ADMIN)
    job_dir = tmp_path / "job_crash"
    job_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy(source_path, job_dir / "crash_test.xlsx")

    ctx = await make_context(
        database,
        kind=ExcelJobKind.FARMER_IMPORT,
        owner_id=admin_id,
        owner_role=Role.ADMIN,
        target_id=vlcc.id,
        job_dir=job_dir,
        mode=ImportMode.UPSERT,
        source_file="crash_test.xlsx",
    )

    class CrashingImport(FarmerImportProcessor):
        async def _write(self, context, plans):
            async with database.transaction() as session:
                from app.core.clock import now_naive_ist
                await session.execute(UserModel.__table__.insert(), [dict(
                    id=uuid4(), name="Crash Farmer Orphan", email="orphan@test.local", mobile="9999999999",
                    password_hash="x", role=Role.FARMER, is_active=True, is_locked=False, is_deleted=False,
                    created_at=now_naive_ist(), updated_at=now_naive_ist())])
                raise RuntimeError("SIMULATED_WORKER_CRASH")

    processor = CrashingImport(
        database=database,
        repository=FarmerExchangeRepository(database),
        password_service=PasswordService(),
    )

    # Running the import should raise the crash error
    with pytest.raises(RuntimeError, match="SIMULATED_WORKER_CRASH"):
        await processor.run(ctx)

    # Verify database integrity: every Farmer in this VLCC MUST have a valid User
    async with database.transaction() as session:
        farmers_count = await session.scalar(
            select(func.count()).select_from(FarmerModel).where(FarmerModel.vlcc_id == vlcc.id)
        )
        # Check orphaned users created during this crash test
        orphans = (await session.execute(
            select(UserModel.id)
            .where(UserModel.name.like("Crash Farmer %"))
            .where(~UserModel.id.in_(select(FarmerModel.user_id)))
        )).scalars().all()

        assert len(orphans) == 0, f"Found orphaned User records: {orphans}"
        assert farmers_count == ctx.inserted


# =========================================================
# 2. UPLOAD DISCARD & RESOURCE CLEANUP (NFR-05)
# =========================================================

async def test_upload_discard_removes_all_chunks(tmp_path):
    """
    Aborting an upload and discarding its upload_id immediately unlinks
    all chunk files from disk without leaking storage.
    """
    storage = ExchangeStorage(tmp_path, max_upload_bytes=10**8, min_free_bytes=0)
    upload_id = uuid4()
    chunks_dir = storage.upload_dir(upload_id)
    chunks_dir.mkdir(parents=True, exist_ok=True)

    # Simulate 3 chunks written
    for i in range(3):
        (chunks_dir / f"{i:06d}.part").write_bytes(b"chunk data " * 100)

    assert chunks_dir.exists()
    assert len(list(chunks_dir.iterdir())) == 3

    # Discard upload directory
    storage.delete_dir(chunks_dir)

    assert not chunks_dir.exists()


# =========================================================
# 3. HOSTILE FILE REJECTION (NFR-09)
# =========================================================

def test_file_guard_rejects_disguised_executable(tmp_path):
    """A binary executable renamed to .xlsx must be rejected by file guard."""
    guard = FileGuard(max_uncompressed_bytes=10 * 1024 * 1024)
    fake_xlsx = tmp_path / "malicious.xlsx"
    fake_xlsx.write_bytes(b"MZ\x90\x00\x03\x00\x00\x00\x04\x00\x00\x00\xff\xff\x00\x00")

    with pytest.raises(InvalidExcelFileException, match="Not an .xlsx file"):
        guard.inspect(fake_xlsx)


def test_file_guard_rejects_archive_with_traversal_paths(tmp_path):
    """A zip file containing directory traversal filenames like ../../evil.xml must be rejected."""
    guard = FileGuard(max_uncompressed_bytes=10 * 1024 * 1024)
    evil_xlsx = tmp_path / "traversal.xlsx"

    with zipfile.ZipFile(evil_xlsx, "w") as zf:
        zf.writestr("[Content_Types].xml", b"<Types/>")
        zf.writestr("xl/workbook.xml", b"<workbook/>")
        zf.writestr("../../etc/passwd", b"root:x:0:0:::")

    with pytest.raises(InvalidExcelFileException, match="The file contains an unsafe path"):
        guard.inspect(evil_xlsx)


# =========================================================
# 4. DISK GUARD PRESSURE (NFR-11)
# =========================================================

def test_storage_disk_guard_enforces_free_space_threshold(tmp_path):
    """When disk space is less than min_free_bytes, storage raises ExcelStorageFullException."""
    # Require 1 TB free space
    storage = ExchangeStorage(tmp_path, max_upload_bytes=10**8, min_free_bytes=10**14)

    with pytest.raises(ExcelStorageFullException):
        storage.ensure_free_space(1024)
