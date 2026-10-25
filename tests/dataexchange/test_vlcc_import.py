"""
VLCC import processor tests (Plan 3.2).
"""

from __future__ import annotations

from uuid import uuid4

import pytest
from openpyxl import load_workbook
from sqlalchemy import func, select

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.common.milk_quality.infrastructure.models import MilkQualityConfigModel
from app.modules.common.settings.infrastructure.models import SettingsModel
from app.modules.dataexchange.application.vlcc_import import VlccImportProcessor
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.domain.sheets import VLCC_SHEET
from app.modules.dataexchange.infrastructure.vlcc_repository import VlccExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetWriter
from app.modules.vlcc.infrastructure.models import VlccModel
from tests.dataexchange.factories import create_full_vlccs, create_user, make_context, unique_mobile

PASSWORDS = PasswordService()
COLUMNS = VLCC_SHEET.import_columns()


def _file(path, rows: list[dict]) -> str:
    writer = XlsxSheetWriter(path, VLCC_SHEET, columns=COLUMNS)
    writer.write_rows([[row.get(column.key) for column in COLUMNS] for row in rows])
    writer.close()
    return path.name


async def _prepare(database, owner_id, tmp_path, rows, *, mode=ImportMode.UPSERT, dry_run=False):
    job_dir = tmp_path / f"job-{uuid4().hex[:6]}"
    job_dir.mkdir(parents=True, exist_ok=True)
    name = _file(job_dir / "source.xlsx", rows)
    return await make_context(
        database,
        kind=ExcelJobKind.VLCC_IMPORT,
        owner_id=owner_id,
        owner_role=Role.ADMIN,
        target_id=owner_id,
        job_dir=job_dir,
        mode=mode,
        dry_run=dry_run,
        source_file=name,
    )


def _processor(database):
    return VlccImportProcessor(
        database=database,
        repository=VlccExchangeRepository(database),
        password_service=PASSWORDS,
    )


async def _run(database, owner_id, tmp_path, rows, *, mode=ImportMode.UPSERT, dry_run=False, processor=None):
    ctx = await _prepare(database, owner_id, tmp_path, rows, mode=mode, dry_run=dry_run)
    result = await (processor or _processor(database)).run(ctx)
    return ctx, result


async def test_import_inserts_new_vlccs_with_all_relations(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN, name="Admin Owner")
    m1, m2 = unique_mobile(), unique_mobile()
    rows = [
        {
            "vlcc_code": "VLC01", "uic_code": "UIC01", "vlcc_name": "Center One",
            "user_name": "Operator One", "mobile": m1, "email": "v1@test.local",
            "address_line": "Line 1", "city": "Bhopal", "state": "MP", "pincode": "462001",
            "account_holder": "Center One", "bank_name": "SBI", "account_number": "111122223333",
            "ifsc_code": "SBIN0001234", "analyzer_type": "TYPE_B", "weight_unit": "KILOGRAM",
            "receipt_size": "LARGE", "printer_type": "THERMAL", "cow_min_fat": 3.0, "cow_max_fat": 10.0,
        },
        {
            "vlcc_code": "VLC02", "uic_code": "UIC02", "vlcc_name": "Center Two",
            "user_name": "Operator Two", "mobile": m2,
        },
    ]

    ctx, result = await _run(database, owner, tmp_path, rows)

    assert ctx.total == 2
    assert ctx.inserted == 2
    assert ctx.updated == 0
    assert ctx.discarded == 0
    assert result.report_file is None

    async with database.transaction() as session:
        vlccs = (await session.execute(
            select(VlccModel).where(VlccModel.created_by == owner).order_by(VlccModel.vlcc_code)
        )).scalars().all()
        assert len(vlccs) == 2
        v1, v2 = vlccs[0], vlccs[1]

        assert v1.vlcc_code == "VLC01"
        assert v1.name == "Center One"
        assert v1.created_by == owner
        assert v1.address_id is not None
        assert v1.bank_account_id is not None
        assert v1.settings_id is not None
        assert v1.milk_quality_config_id is not None

        # Check settings defaults applied on v2
        st2 = await session.scalar(select(SettingsModel).where(SettingsModel.id == v2.settings_id))
        assert st2 is not None
        assert st2.morning_collection_start == "06:00"

        # Check milk quality config defaults applied on v2
        mq2 = await session.scalar(select(MilkQualityConfigModel).where(MilkQualityConfigModel.id == v2.milk_quality_config_id))
        assert mq2 is not None
        assert mq2.cow_min_fat == 0.0


async def test_import_updates_existing_vlcc_and_keeps_blank_cells(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN)
    created = await create_full_vlccs(database, owner, 1, prefix="U")
    initial = created[0]

    rows = [{
        "vlcc_code": initial["vlcc_code"],
        "uic_code": initial["uic_code"],
        "vlcc_name": "Renamed Center",
        "user_name": initial["user_name"],
        "mobile": initial["mobile"],
        "contact_person": "New Contact Person",
        # address, bank, settings are blank -> keep existing
    }]

    ctx, result = await _run(database, owner, tmp_path, rows)

    assert ctx.total == 1
    assert ctx.inserted == 0
    assert ctx.updated == 1
    assert ctx.discarded == 0

    async with database.transaction() as session:
        updated_vlcc = await session.scalar(
            select(VlccModel).where(VlccModel.vlcc_code == initial["vlcc_code"])
        )
        assert updated_vlcc.name == "Renamed Center"
        assert updated_vlcc.contact_person == "New Contact Person"

        # Address kept
        addr = await session.scalar(select(AddressModel).where(AddressModel.id == updated_vlcc.address_id))
        assert addr.city == "Ujjain"
        assert addr.line == "Station Road"


async def test_import_discards_duplicate_in_file(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN)
    m = unique_mobile()
    rows = [
        {"vlcc_code": "DUP01", "uic_code": "U01", "vlcc_name": "First", "user_name": "Op 1", "mobile": m},
        {"vlcc_code": "DUP01", "uic_code": "U02", "vlcc_name": "Second", "user_name": "Op 2", "mobile": unique_mobile()},
    ]

    ctx, result = await _run(database, owner, tmp_path, rows)

    assert ctx.inserted == 1
    assert ctx.discarded == 1
    assert result.report_file is not None

    book = load_workbook(ctx.job_dir / result.report_file, read_only=True)
    report_rows = list(book["VLCCs"].iter_rows(min_row=2, values_only=True))
    assert len(report_rows) == 1
    assert "repeats row 2" in report_rows[0][-1]


async def test_import_discards_existing_mobile_from_another_user(database, tmp_path):
    existing_user_id = await create_user(database, role=Role.FARMER, name="Existing Guy")
    async with database.transaction() as session:
        existing_mobile = (await session.scalar(select(UserModel.mobile).where(UserModel.id == existing_user_id)))

    owner = await create_user(database, role=Role.ADMIN)
    rows = [
        {"vlcc_code": "MOB01", "uic_code": "U01", "vlcc_name": "Center", "user_name": "Op", "mobile": existing_mobile},
    ]

    ctx, result = await _run(database, owner, tmp_path, rows)

    assert ctx.inserted == 0
    assert ctx.discarded == 1
    book = load_workbook(ctx.job_dir / result.report_file, read_only=True)
    report_rows = list(book["VLCCs"].iter_rows(min_row=2, values_only=True))
    assert "already registered" in report_rows[0][-1]


async def test_import_discards_deleted_vlcc_code(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN)
    created = await create_full_vlccs(database, owner, 1, prefix="DEL", deleted=True)
    del_code = created[0]["vlcc_code"]

    rows = [
        {"vlcc_code": del_code, "uic_code": "U99", "vlcc_name": "Reused", "user_name": "Op", "mobile": unique_mobile()},
    ]

    ctx, result = await _run(database, owner, tmp_path, rows)

    assert ctx.inserted == 0
    assert ctx.discarded == 1
    book = load_workbook(ctx.job_dir / result.report_file, read_only=True)
    report_rows = list(book["VLCCs"].iter_rows(min_row=2, values_only=True))
    assert "belongs to a deleted VLCC" in report_rows[0][-1]


async def test_import_discards_code_conflict_in_hierarchy(database, tmp_path):
    super_admin = await create_user(database, role=Role.SUPER_ADMIN, name="Super Admin")
    created = await create_full_vlccs(database, super_admin, 1, prefix="SA")
    sa_code = created[0]["vlcc_code"]

    owner = await create_user(database, role=Role.ADMIN, name="Admin")
    rows = [
        {"vlcc_code": sa_code, "uic_code": "U11", "vlcc_name": "Clash Center", "user_name": "Op", "mobile": unique_mobile()},
    ]

    ctx, result = await _run(database, owner, tmp_path, rows)

    assert ctx.inserted == 0
    assert ctx.discarded == 1
    book = load_workbook(ctx.job_dir / result.report_file, read_only=True)
    report_rows = list(book["VLCCs"].iter_rows(min_row=2, values_only=True))
    assert "already used in this hierarchy" in report_rows[0][-1]


async def test_dry_run_validates_without_writing(database, tmp_path):
    owner = await create_user(database, role=Role.ADMIN)
    rows = [
        {"vlcc_code": "DRY01", "uic_code": "U01", "vlcc_name": "Dry Center", "user_name": "Op", "mobile": unique_mobile()},
    ]

    ctx, result = await _run(database, owner, tmp_path, rows, dry_run=True)

    assert ctx.inserted == 1
    assert ctx.discarded == 0
    assert result.report_file is None

    async with database.transaction() as session:
        count = await session.scalar(select(func.count()).select_from(VlccModel).where(VlccModel.vlcc_code == "DRY01"))
        assert count == 0
