"""
Farmer import processor against a real database (Plan 2.2).
"""

from __future__ import annotations

import time
from uuid import uuid4

import pytest
from sqlalchemy import func, select

from app.core.clock import now_naive_ist
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.dataexchange.application.batching import read_rss_bytes
from app.modules.dataexchange.application.farmer_import import FarmerImportProcessor
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.domain.sheets import DEFAULT_FARMER_PASSWORD, FARMER_SHEET
from app.modules.dataexchange.infrastructure.farmer_repository import FarmerExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import XlsxSheetReader, XlsxSheetWriter
from app.modules.farmer.domain.enums import MilkType
from app.modules.farmer.infrastructure.models import FarmerModel
from tests.dataexchange.factories import create_farmers, create_vlcc, make_context, unique_mobile

PASSWORDS = PasswordService()
COLUMNS = FARMER_SHEET.import_columns()


def _file(path, rows: list[dict]) -> str:
    writer = XlsxSheetWriter(path, FARMER_SHEET, columns=COLUMNS)
    writer.write_rows([[row.get(column.key) for column in COLUMNS] for row in rows])
    writer.close()
    return path.name


async def _prepare(database, vlcc, tmp_path, rows, *, mode=ImportMode.UPSERT, dry_run=False):
    job_dir = tmp_path / f"job-{uuid4().hex[:6]}"
    job_dir.mkdir()
    name = _file(job_dir / "source.xlsx", rows)
    return await make_context(database, kind=ExcelJobKind.FARMER_IMPORT, owner_id=vlcc.user_id, owner_role=Role.VLCC,
                              target_id=vlcc.id, job_dir=job_dir, mode=mode, dry_run=dry_run, source_file=name)


def _processor(database):
    return FarmerImportProcessor(database=database, repository=FarmerExchangeRepository(database), password_service=PASSWORDS)


async def _run(database, vlcc, tmp_path, rows, *, mode=ImportMode.UPSERT, dry_run=False, processor=None):
    ctx = await _prepare(database, vlcc, tmp_path, rows, mode=mode, dry_run=dry_run)
    result = await (processor or _processor(database)).run(ctx)
    return ctx, result


def _report(ctx, result, tmp_path) -> list[tuple[int, str, dict]]:
    if result.report_file is None:
        return []
    with XlsxSheetReader(ctx.job_dir / result.report_file, FARMER_SHEET, scratch_dir=tmp_path) as reader:
        rows = [row for batch in reader.iter_batches(1000) for row in batch]
    from openpyxl import load_workbook
    sheet = load_workbook(ctx.job_dir / result.report_file, read_only=True)["Farmers"]
    extra = [(line[-2], line[-1]) for line in sheet.iter_rows(min_row=2, values_only=True)]
    return [(row_no, reason, row.cells) for (row_no, reason), row in zip(extra, rows)]


async def _farmer(database, vlcc, code):
    async with database.transaction() as session:
        row = (await session.execute(
            select(FarmerModel, UserModel, AddressModel, BankAccountModel)
            .join(UserModel, UserModel.id == FarmerModel.user_id)
            .outerjoin(AddressModel, AddressModel.user_id == FarmerModel.user_id)
            .outerjoin(BankAccountModel, BankAccountModel.id == FarmerModel.bank_account_id)
            .where(FarmerModel.vlcc_id == vlcc.id, FarmerModel.farmer_code == code)
        )).first()
    return row


def _new(code, **extra):
    return {"farmer_code": code, "name": f"Farmer {code}", "mobile": unique_mobile(), **extra}


# =========================================================
# INSERT / UPDATE
# =========================================================

async def test_insert_new_farmers_with_defaults(database, tmp_path):
    vlcc = await create_vlcc(database)
    rows = [_new("N1"), _new("N2", milk_type="BUFFALO", sms_enabled="YES", city="Ujjain", bank_name="SBI")]

    ctx, result = await _run(database, vlcc, tmp_path, rows)

    assert (ctx.inserted, ctx.updated, ctx.discarded) == (2, 0, 0) and result.report_file is None
    farmer, user, address, bank = await _farmer(database, vlcc, "N1")
    assert (farmer.milk_type, farmer.assigned_chart_rank, farmer.sms_enabled, farmer.is_active) == (MilkType.MIXED, 1, False, True)
    assert user.role is Role.FARMER and user.mobile == rows[0]["mobile"]
    assert user.email.startswith("farmer_n1_") and user.email.endswith("@dairy.local")
    assert PASSWORDS.verify(user.password_hash, DEFAULT_FARMER_PASSWORD)
    assert address is None and bank is None and farmer.address_id is None
    farmer2, _, address2, bank2 = await _farmer(database, vlcc, "N2")
    assert (farmer2.milk_type, farmer2.sms_enabled) == (MilkType.BUFFALO, True)
    assert address2.city == "Ujjain" and farmer2.address_id == address2.id
    assert bank2.bank_name == "SBI" and bank2.account_holder == "Farmer N2"     # holder defaults to the name


async def test_update_keeps_blank_cells_and_changes_given_ones(database, tmp_path):
    vlcc = await create_vlcc(database)
    [stored] = await create_farmers(database, vlcc, 1, prefix="U")

    ctx, _ = await _run(database, vlcc, tmp_path, [{"farmer_code": stored["farmer_code"], "city": "Bhopal", "milk_type": "MIXED"}])

    assert (ctx.inserted, ctx.updated, ctx.discarded) == (0, 1, 0)
    farmer, user, address, bank = await _farmer(database, vlcc, stored["farmer_code"])
    assert address.city == "Bhopal" and address.line == "Main Road"        # changed / kept
    assert farmer.milk_type is MilkType.MIXED and farmer.assigned_chart_rank == 2
    assert user.name == stored["name"] and user.mobile == stored["mobile"]
    assert bank.account_number == stored["account_number"]


async def test_reuploading_an_unchanged_row_writes_nothing(database, tmp_path):
    vlcc = await create_vlcc(database)
    [stored] = await create_farmers(database, vlcc, 1, prefix="S")
    before = (await _farmer(database, vlcc, stored["farmer_code"]))[0].updated_at

    ctx, _ = await _run(database, vlcc, tmp_path, [{"farmer_code": stored["farmer_code"], "name": stored["name"],
                                                     "mobile": stored["mobile"], "city": "Indore"}])

    assert (ctx.processed, ctx.inserted, ctx.updated, ctx.discarded) == (1, 0, 0, 0)   # 1 unchanged
    assert (await _farmer(database, vlcc, stored["farmer_code"]))[0].updated_at == before


async def test_custom_password_is_hashed(database, tmp_path):
    vlcc = await create_vlcc(database)
    [stored] = await create_farmers(database, vlcc, 1, prefix="P")

    await _run(database, vlcc, tmp_path, [_new("P-new", password="Custom@111"),
                                          {"farmer_code": stored["farmer_code"], "password": "Changed@222"}])

    assert PASSWORDS.verify((await _farmer(database, vlcc, "P-new"))[1].password_hash, "Custom@111")
    assert PASSWORDS.verify((await _farmer(database, vlcc, stored["farmer_code"]))[1].password_hash, "Changed@222")


async def test_address_of_user_is_reused_when_farmer_link_is_missing(database, tmp_path):
    vlcc = await create_vlcc(database)
    [stored] = await create_farmers(database, vlcc, 1, prefix="L")
    async with database.transaction() as session:                       # break the link, keep the row
        await session.execute(FarmerModel.__table__.update().where(FarmerModel.user_id == stored["user_id"]).values(address_id=None))

    ctx, _ = await _run(database, vlcc, tmp_path, [{"farmer_code": stored["farmer_code"], "city": "Dewas"}])

    farmer, _, address, _ = await _farmer(database, vlcc, stored["farmer_code"])
    assert ctx.updated == 1 and ctx.discarded == 0
    assert address.city == "Dewas" and farmer.address_id == address.id


# =========================================================
# DISCARD RULES
# =========================================================

async def test_create_only_discards_existing_codes(database, tmp_path):
    vlcc = await create_vlcc(database)
    [stored] = await create_farmers(database, vlcc, 1, prefix="C")

    ctx, result = await _run(database, vlcc, tmp_path, [_new(stored["farmer_code"]), _new("C-new")], mode=ImportMode.CREATE_ONLY)

    assert (ctx.inserted, ctx.discarded) == (1, 1)
    assert _report(ctx, result, tmp_path)[0][1] == f"Farmer code {stored['farmer_code']} already exists"


async def test_deleted_code_missing_fields_and_parse_errors(database, tmp_path):
    vlcc = await create_vlcc(database)
    [deleted] = await create_farmers(database, vlcc, 1, prefix="D", deleted=True)
    rows = [
        _new(deleted["farmer_code"]),
        {"farmer_code": "NO-NAME", "mobile": unique_mobile()},
        {"farmer_code": "NOTHING"},
        {"name": "No Code", "mobile": unique_mobile()},
        _new("BAD", mobile="12345", pincode="12"),
    ]

    ctx, result = await _run(database, vlcc, tmp_path, rows)
    reasons = {cells.get("farmer_code"): reason for _, reason, cells in _report(ctx, result, tmp_path)}

    assert (ctx.inserted, ctx.discarded) == (0, 5)
    assert reasons[deleted["farmer_code"]] == f"Farmer code {deleted['farmer_code']} belongs to a deleted farmer"
    assert reasons["NO-NAME"] == "Name is required for a new farmer"
    assert reasons["NOTHING"] == "Name and Mobile are required for a new farmer"
    assert reasons[None] == "Farmer Code is required"
    assert reasons["BAD"] == "Mobile: must be exactly 10 digits; Pincode: must be a 6-digit pincode"


async def test_mobile_or_email_of_another_user_is_discarded(database, tmp_path, user_factory):
    vlcc = await create_vlcc(database)
    other_vlcc = await create_vlcc(database)
    [other] = await create_farmers(database, other_vlcc, 1, prefix="O")
    deleted_user = uuid4()
    async with database.transaction() as session:
        await session.execute(UserModel.__table__.insert(), [dict(
            id=deleted_user, name="Gone", email="gone@Example.com", mobile="9123456780", password_hash="x",
            role=Role.FARMER, is_active=False, is_locked=False, is_deleted=True,
            created_at=now_naive_ist(), updated_at=now_naive_ist())])

    ctx, result = await _run(database, vlcc, tmp_path, [
        _new("M1", mobile=other["mobile"]),
        _new("M2", mobile="9123456780"),                    # belongs to a deleted user: still taken
        _new("M3", email="GONE@example.com"),                # case-insensitive clash
    ])
    reasons = [reason for _, reason, _ in _report(ctx, result, tmp_path)]

    assert ctx.inserted == 0
    assert reasons == [f"Mobile {other['mobile']} is already used by another user",
                       "Mobile 9123456780 is already used by another user",
                       "Email gone@example.com is already used by another user"]


async def test_repeats_inside_the_file_report_the_first_row(database, tmp_path):
    vlcc = await create_vlcc(database)
    mobile = unique_mobile()
    rows = [_new("R1", mobile=mobile, email="r@x.in"), _new("R1"), _new("R2", mobile=mobile), _new("R3", email="R@x.in")]

    ctx, result = await _run(database, vlcc, tmp_path, rows)

    assert (ctx.inserted, ctx.discarded) == (1, 3)
    assert [(row_no, reason) for row_no, reason, _ in _report(ctx, result, tmp_path)] == [
        (3, "Farmer Code repeats row 2"), (4, "Mobile repeats row 2"), (5, "Email repeats row 2"),
    ]


async def test_repeat_of_a_row_saved_in_an_earlier_batch_names_that_row(database, tmp_path):
    vlcc = await create_vlcc(database)
    rows = [_new(f"B{i:04d}") for i in range(600)]                      # read batch = 500 rows
    rows.append(_new("LATE", mobile=rows[4]["mobile"]))                # mobile of Excel row 6, saved in batch 1

    ctx, result = await _run(database, vlcc, tmp_path, rows)

    assert (ctx.inserted, ctx.discarded) == (600, 1)
    assert _report(ctx, result, tmp_path)[0][:2] == (602, "Mobile repeats row 6")


async def test_discarded_row_does_not_claim_its_keys(database, tmp_path):
    vlcc = await create_vlcc(database)
    mobile = unique_mobile()

    ctx, _ = await _run(database, vlcc, tmp_path, [_new("K1", mobile=mobile, pincode="1"), _new("K2", mobile=mobile)])

    assert (ctx.inserted, ctx.discarded) == (1, 1)                    # K1 invalid, K2 may use the mobile
    assert (await _farmer(database, vlcc, "K2"))[1].mobile == mobile


async def test_report_keeps_columns_blanks_passwords_and_can_be_reuploaded(database, tmp_path):
    vlcc = await create_vlcc(database)

    ctx, result = await _run(database, vlcc, tmp_path, [_new("RP", password="Secret@99", pincode="12")])
    [(row_no, reason, cells)] = _report(ctx, result, tmp_path)

    assert row_no == 2 and reason.startswith("Pincode")
    assert cells["farmer_code"] == "RP" and cells.get("password") is None   # never echoed back


async def test_dry_run_validates_and_writes_nothing(database, tmp_path):
    vlcc = await create_vlcc(database)

    ctx, _ = await _run(database, vlcc, tmp_path, [_new("DRY1"), _new("DRY2", mobile="1")], dry_run=True)

    assert (ctx.inserted, ctx.discarded) == (1, 1)
    assert await _farmer(database, vlcc, "DRY1") is None


async def test_other_vlcc_with_same_code_is_untouched(database, tmp_path):
    vlcc_a = await create_vlcc(database)
    vlcc_b = await create_vlcc(database)
    [b_farmer] = await create_farmers(database, vlcc_b, 1, prefix="SAME")

    ctx, _ = await _run(database, vlcc_a, tmp_path, [_new(b_farmer["farmer_code"])])

    assert ctx.inserted == 1                                             # new in A, B's farmer not updated
    assert (await _farmer(database, vlcc_b, b_farmer["farmer_code"]))[1].name == b_farmer["name"]


async def test_concurrent_clash_discards_only_that_row(database, tmp_path):
    vlcc = await create_vlcc(database)
    clash = unique_mobile()
    rows = [_new("X1"), _new("X2", mobile=clash), _new("X3")]

    class RacingImport(FarmerImportProcessor):
        """Another request saves `clash` after the pre-check but before the write."""

        async def _write(self, ctx, plans):
            async with database.transaction() as session:
                await session.execute(UserModel.__table__.insert(), [dict(
                    id=uuid4(), name="Racer", email=f"racer-{uuid4().hex[:6]}@x.in", mobile=clash,
                    password_hash="x", role=Role.FARMER, is_active=True, is_locked=False, is_deleted=False,
                    created_at=now_naive_ist(), updated_at=now_naive_ist())])
            return await super()._write(ctx, plans)

    processor = RacingImport(database=database, repository=FarmerExchangeRepository(database), password_service=PASSWORDS)
    ctx, result = await _run(database, vlcc, tmp_path, rows, processor=processor)

    assert (ctx.inserted, ctx.discarded) == (2, 1)
    [(row_no, reason, _)] = _report(ctx, result, tmp_path)
    assert row_no == 3 and reason.startswith("Saved by someone else at the same time")
    assert await _farmer(database, vlcc, "X1") is not None and await _farmer(database, vlcc, "X3") is not None


# =========================================================
# THROUGHPUT
# =========================================================

@pytest.mark.parametrize("rows_count", [100_000])
async def test_large_import_throughput(database, tmp_path, rows_count):
    vlcc = await create_vlcc(database)
    rows = [{"farmer_code": f"T{i:07d}", "name": f"Farmer {i}", "mobile": f"5{i:09d}",
             "city": "Indore", "pincode": "452001", "bank_name": "SBI", "account_number": f"{i:012d}"}
            for i in range(rows_count)]
    ctx = await _prepare(database, vlcc, tmp_path, rows)            # building the file is not timed
    del rows
    rss_before = read_rss_bytes()

    started = time.perf_counter()
    await _processor(database).run(ctx)
    elapsed = time.perf_counter() - started
    rss_after = read_rss_bytes()

    async with database.transaction() as session:
        stored = await session.scalar(select(func.count()).select_from(FarmerModel).where(FarmerModel.vlcc_id == vlcc.id))
    print(f"\n{rows_count:,} farmers imported in {elapsed:.1f}s = {rows_count / elapsed:,.0f} rows/s; "
          f"RSS {rss_before / 1e6:.0f} -> {rss_after / 1e6:.0f} MB")
    assert (ctx.inserted, ctx.discarded, stored) == (rows_count, 0, rows_count)
    # SQLite + 4 indexed tables per farmer at the 250 ms fairness budget (RESEARCH / 2-SUMMARY)
    assert rows_count / elapsed >= 1000
    assert rss_after - rss_before < 150e6                             # flat memory (NFR-01)
