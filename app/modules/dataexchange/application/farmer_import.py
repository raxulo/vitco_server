"""
Farmer Import Processor

Upserts the farmers of one VLCC from an xlsx file (REQ-08 … REQ-11):

  read batch (thread, next batch prefetched)
    → parse cells → classify insert / update → 3 indexed pre-check queries
    → in-file duplicates (disk-backed) → hash custom passwords in parallel
    → Core bulk INSERT / UPDATE per table, sub-batched to the lock budget
    → discarded rows streamed to a report

Rows whose values did not change are not written at all, so re-uploading an
exported file costs reads only. A batch that collides with a concurrent API
write (IntegrityError) is retried row by row in savepoints, so only the
clashing rows are discarded.

Python 3.13+
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.exc import IntegrityError

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.auth.infrastructure.password import PasswordService
from app.modules.dataexchange.application.processor import JobContext, ProcessorResult
from app.modules.dataexchange.domain.columns import parse_cell
from app.modules.dataexchange.domain.enums import ExcelJobKind, ImportMode
from app.modules.dataexchange.domain.sheets import (
    DEFAULT_FARMER_PASSWORD,
    FARMER_ADDRESS_KEYS,
    FARMER_BANK_KEYS,
    FARMER_SHEET,
)
from app.modules.dataexchange.infrastructure.farmer_repository import ExistingFarmer, FarmerExchangeRepository
from app.modules.dataexchange.infrastructure.seen_keys import SeenKeys
from app.modules.dataexchange.infrastructure.xlsx import ExtraColumn, RawRow, XlsxSheetReader, XlsxSheetWriter
from app.modules.farmer.domain.enums import MilkType

_REPORT_FILE = "discarded_rows.xlsx"
_IMPORT_COLUMNS = FARMER_SHEET.import_columns()
_HEADERS = {column.key: column.header for column in FARMER_SHEET.columns}
_USER_FIELDS = ("name", "email", "mobile", "is_active")
_FARMER_FIELDS = ("milk_type", "assigned_chart_rank", "sms_enabled", "is_active")
_ADDRESS_COLUMNS = {"address_line": "line", "city": "city", "state": "state", "pincode": "pincode"}


@dataclass(slots=True)
class _Row:
    raw: RawRow
    values: dict[str, Any]
    errors: list[str]
    existing: ExistingFarmer | None = None
    reason: str | None = None


@dataclass(slots=True)
class _Plan:
    """Everything one accepted row writes; plans are merged per sub-batch."""

    row: _Row
    is_insert: bool
    password: str | None = None                  # custom password still to hash
    user_insert: dict | None = None
    address_insert: dict | None = None
    bank_insert: dict | None = None
    farmer_insert: dict | None = None
    user_update: dict | None = None
    password_update: dict | None = None
    address_update: dict | None = None
    bank_update: dict | None = None
    farmer_update: dict | None = None

    @property
    def changes_something(self) -> bool:
        """False for an update whose values all match the stored ones (counted as unchanged)."""
        return self.is_insert or self.password is not None or any((
            self.user_update, self.password_update, self.address_insert, self.address_update,
            self.bank_insert, self.bank_update, self.farmer_update,
        ))


@dataclass(slots=True)
class _Report:
    path: Path
    writer: XlsxSheetWriter | None = None
    pending: list[list] = field(default_factory=list)


class FarmerImportProcessor:

    __slots__ = ("_database", "_repository", "_passwords", "_read_batch", "_hash_workers")

    kind = ExcelJobKind.FARMER_IMPORT

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: FarmerExchangeRepository,
        password_service: PasswordService,
        read_batch: int = 500,
        hash_workers: int | None = None,
    ) -> None:
        self._database = database
        self._repository = repository
        self._passwords = password_service
        self._read_batch = read_batch
        self._hash_workers = hash_workers or max(1, min(4, os.cpu_count() or 1))

    # =========================================================
    # JOB
    # =========================================================

    async def run(self, ctx: JobContext) -> ProcessorResult:
        if ctx.job.target_id is None or not ctx.job.source_file:
            raise ValueError("Import job has no VLCC or no file")
        source = ctx.job_dir / ctx.job.source_file
        default_hash = await asyncio.to_thread(self._passwords.hash, DEFAULT_FARMER_PASSWORD)
        report = _Report(path=ctx.job_dir / _REPORT_FILE)

        reader = XlsxSheetReader(source, FARMER_SHEET, scratch_dir=ctx.job_dir)
        await asyncio.to_thread(reader.__enter__)
        seen = SeenKeys(ctx.job_dir / "seen_keys.sqlite3")
        pool = ThreadPoolExecutor(max_workers=self._hash_workers, thread_name_prefix="farmer-import-hash")
        batches = reader.iter_batches(self._read_batch)
        prefetch: asyncio.Future | None = None
        try:
            ctx.total = reader.estimated_rows
            await ctx.report()
            prefetch = asyncio.ensure_future(asyncio.to_thread(next, batches, None))
            while True:
                batch = await prefetch
                prefetch = None
                if batch is None:
                    break
                # The next file batch is parsed in a thread while this one hits the database
                prefetch = asyncio.ensure_future(asyncio.to_thread(next, batches, None))
                await self._process(ctx, batch, seen, report, pool, default_hash)
                await ctx.checkpoint()
        finally:
            if prefetch is not None:
                await asyncio.gather(prefetch, return_exceptions=True)
            pool.shutdown(wait=True, cancel_futures=True)
            seen.close()
            await asyncio.to_thread(reader.close)
            await self._close_report(report)

        return ProcessorResult(report_file=_REPORT_FILE if ctx.discarded else None)

    # =========================================================
    # BATCH
    # =========================================================

    async def _process(self, ctx: JobContext, batch: list[RawRow], seen: SeenKeys, report: _Report,
                       pool: ThreadPoolExecutor, default_hash: str) -> None:
        rows = [self._parse(raw) for raw in batch]
        mode = ctx.job.mode or ImportMode.UPSERT
        vlcc_id: UUID = ctx.job.target_id

        codes = sorted({row.values["farmer_code"] for row in rows if not row.errors and "farmer_code" in row.values})
        async with self._database.transaction():
            existing = await self._repository.existing_by_codes(vlcc_id, codes) if codes else {}
        for row in rows:
            self._classify(row, existing, mode)

        await self._check_contacts([row for row in rows if row.reason is None], seen)
        self._dedupe([row for row in rows if row.reason is None], seen)

        now = now_naive_ist()
        plans = [self._plan(row, ctx, now, default_hash) for row in rows if row.reason is None]
        changed = {id(plan) for plan in plans if plan.changes_something}   # before hashing clears passwords
        if ctx.job.dry_run:
            written = plans                                   # validated, nothing hashed or written
        else:
            await self._hash_passwords(plans, pool)
            written = await self._write(ctx, plans)
        accepted = {id(plan.row) for plan in written}
        for plan in plans:
            if id(plan.row) not in accepted and plan.row.reason is None:
                plan.row.reason = "Could not be saved"

        ctx.processed += len(rows)
        ctx.inserted += sum(1 for plan in written if plan.is_insert)
        # Matched rows whose values were all the same count as unchanged (processed - inserted - updated - discarded)
        ctx.updated += sum(1 for plan in written if not plan.is_insert and id(plan) in changed)
        discarded = [row for row in rows if row.reason is not None]
        ctx.discarded += len(discarded)
        if discarded:
            await self._append_report(report, discarded)

    @staticmethod
    def _parse(raw: RawRow) -> _Row:
        values: dict[str, Any] = {}
        errors: list[str] = []
        for column in _IMPORT_COLUMNS:
            if column.key not in raw.cells:
                continue
            parsed = parse_cell(column, raw.cells[column.key])
            if parsed.error:
                errors.append(parsed.error)
            elif not parsed.blank:
                values[column.key] = parsed.value
        return _Row(raw=raw, values=values, errors=errors)

    @staticmethod
    def _classify(row: _Row, existing: dict[str, ExistingFarmer], mode: ImportMode) -> None:
        if row.errors:
            row.reason = "; ".join(row.errors[:3])
            return
        code = row.values.get("farmer_code")
        if not code:
            row.reason = "Farmer Code is required"
            return
        found = existing.get(code)
        if found is not None:
            if found.is_deleted:
                row.reason = f"Farmer code {code} belongs to a deleted farmer"
            elif mode is ImportMode.CREATE_ONLY:
                row.reason = f"Farmer code {code} already exists"
            else:
                row.existing = found
            return
        missing = [_HEADERS[key] for key in ("name", "mobile") if key not in row.values]
        if missing:
            row.reason = f"{' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} required for a new farmer"

    async def _check_contacts(self, rows: list[_Row], seen: SeenKeys) -> None:
        """Mobile / email must not belong to another user (deleted users included)."""
        emails, mobiles = set(), set()
        for row in rows:
            current = row.existing.values if row.existing else {}
            email = row.values.get("email")
            if email and email != (current.get("email") or "").lower():
                emails.add(email)
            mobile = row.values.get("mobile")
            if mobile and mobile != current.get("mobile"):
                mobiles.add(mobile)
        if not emails and not mobiles:
            return
        async with self._database.transaction():
            by_email = await self._repository.users_by_emails(sorted(emails)) if emails else {}
            by_mobile = await self._repository.users_by_mobiles(sorted(mobiles)) if mobiles else {}
        clashes: list[tuple[_Row, str, str]] = []
        for row in rows:
            own_user = row.existing.user_id if row.existing else None
            mobile, email = row.values.get("mobile"), row.values.get("email")
            if mobile in by_mobile and by_mobile[mobile] != own_user:
                clashes.append((row, "mobile", mobile))
            elif email in by_email and by_email[email] != own_user:
                clashes.append((row, "email", email))
        if not clashes:
            return
        # Taken by a row saved earlier in this same file -> say which row, it is more useful
        earlier = seen.find([(kind, value) for _, kind, value in clashes])
        for row, kind, value in clashes:
            first = earlier.get((kind, value))
            if first is not None:
                row.reason = f"{_HEADERS[kind]} repeats row {first}"
            else:
                row.reason = f"{_HEADERS[kind]} {value} is already used by another user"

    @staticmethod
    def _dedupe(rows: list[_Row], seen: SeenKeys) -> None:
        """A code / mobile / email repeated later in the file is discarded; the first row wins."""
        keyed = []
        for row in rows:
            keys = [("farmer_code", row.values["farmer_code"])]
            for key in ("mobile", "email"):
                if key in row.values:
                    keys.append((key, str(row.values[key])))
            keyed.append((row, keys))
        earlier = seen.find([key for _, keys in keyed for key in keys])
        in_batch: dict[tuple[str, str], int] = {}
        accepted: list[tuple[str, str, int]] = []
        for row, keys in keyed:
            for key in keys:
                first = earlier.get(key) or in_batch.get(key)
                if first is not None:
                    row.reason = f"{_HEADERS[key[0]]} repeats row {first}"
                    break
            else:
                for key in keys:
                    in_batch[key] = row.raw.row_no
                    accepted.append((key[0], key[1], row.raw.row_no))
        seen.add(accepted)

    # =========================================================
    # PLAN
    # =========================================================

    def _plan(self, row: _Row, ctx: JobContext, now, default_hash: str) -> _Plan:
        if row.existing is None:
            return self._plan_insert(row, ctx, now, default_hash)
        return self._plan_update(row, ctx, now)

    @staticmethod
    def _plan_insert(row: _Row, ctx: JobContext, now, default_hash: str) -> _Plan:
        values = row.values
        owner_id = ctx.job.created_by
        user_id = uuid4()
        code = values["farmer_code"]
        is_active = values.get("is_active", True)
        plan = _Plan(row=row, is_insert=True, password=values.get("password"))
        plan.user_insert = dict(
            id=user_id, name=values["name"], email=values.get("email") or f"farmer_{code}_{uuid4().hex[:6]}@dairy.local".lower(),
            mobile=values["mobile"], password_hash=default_hash, role=Role.FARMER, is_active=is_active,
            is_locked=False, created_by=owner_id, created_at=now, updated_at=now, is_deleted=False,
        )
        address_id = bank_id = None
        if any(key in values for key in FARMER_ADDRESS_KEYS):
            address_id = uuid4()
            plan.address_insert = dict(id=address_id, user_id=user_id, created_at=now, updated_at=now,
                                       **{column: values.get(key) for key, column in _ADDRESS_COLUMNS.items()})
        if any(key in values for key in FARMER_BANK_KEYS):
            bank_id = uuid4()
            plan.bank_insert = dict(id=bank_id, user_id=user_id, created_at=now, updated_at=now,
                                    account_holder=values.get("account_holder") or values["name"],
                                    **{key: values.get(key) for key in FARMER_BANK_KEYS if key != "account_holder"})
        plan.farmer_insert = dict(
            id=uuid4(), user_id=user_id, farmer_code=code, vlcc_id=ctx.job.target_id,
            address_id=address_id, bank_account_id=bank_id,
            milk_type=MilkType(values.get("milk_type", MilkType.MIXED)),
            assigned_chart_rank=values.get("assigned_chart_rank", 1), sms_enabled=values.get("sms_enabled", False),
            is_active=is_active, created_by=owner_id, updated_by=owner_id, created_at=now, updated_at=now,
            is_deleted=False,
        )
        return plan

    @staticmethod
    def _plan_update(row: _Row, ctx: JobContext, now) -> _Plan:
        existing = row.existing
        current = existing.values
        merged = {**current, **row.values}               # a blank cell keeps the stored value
        owner_id = ctx.job.created_by
        plan = _Plan(row=row, is_insert=False, password=row.values.get("password"))

        if any(merged[key] != current[key] for key in _USER_FIELDS):
            plan.user_update = dict(b_id=existing.user_id, updated_at=now,
                                    **{key: merged[key] for key in _USER_FIELDS})

        address_id = existing.address_id
        if any(key in row.values for key in FARMER_ADDRESS_KEYS):
            address = {column: merged[key] for key, column in _ADDRESS_COLUMNS.items()}
            if address_id is None:
                address_id = uuid4()
                plan.address_insert = dict(id=address_id, user_id=existing.user_id, created_at=now, updated_at=now, **address)
            elif any(merged[key] != current[key] for key in FARMER_ADDRESS_KEYS):
                plan.address_update = dict(b_id=address_id, updated_at=now, **address)

        bank_id = existing.bank_account_id
        if any(key in row.values for key in FARMER_BANK_KEYS):
            bank = {key: merged[key] for key in FARMER_BANK_KEYS}
            bank["account_holder"] = bank["account_holder"] or merged["name"]
            if bank_id is None:
                bank_id = uuid4()
                plan.bank_insert = dict(id=bank_id, user_id=existing.user_id, created_at=now, updated_at=now, **bank)
            elif any(merged[key] != current[key] for key in FARMER_BANK_KEYS):
                plan.bank_update = dict(b_id=bank_id, updated_at=now, **bank)

        if (any(merged[key] != current[key] for key in _FARMER_FIELDS)
                or address_id != existing.linked_address_id or bank_id != existing.bank_account_id):
            plan.farmer_update = dict(
                b_id=existing.farmer_id, milk_type=MilkType(merged["milk_type"]),
                assigned_chart_rank=merged["assigned_chart_rank"], sms_enabled=merged["sms_enabled"],
                is_active=merged["is_active"], address_id=address_id, bank_account_id=bank_id,
                updated_at=now, updated_by=owner_id,
            )
        return plan

    async def _hash_passwords(self, plans: list[_Plan], pool: ThreadPoolExecutor) -> None:
        """Custom passwords only; argon2 releases the GIL, so the pool hashes on several cores."""
        todo = [plan for plan in plans if plan.password]
        if not todo:
            return
        loop = asyncio.get_running_loop()
        hashes = await asyncio.gather(*(loop.run_in_executor(pool, self._passwords.hash, plan.password) for plan in todo))
        now = now_naive_ist()
        for plan, hashed in zip(todo, hashes):
            if plan.is_insert:
                plan.user_insert["password_hash"] = hashed
            else:
                plan.password_update = dict(b_id=plan.row.existing.user_id, password_hash=hashed, updated_at=now)
            plan.password = None

    # =========================================================
    # WRITE
    # =========================================================

    async def _write(self, ctx: JobContext, plans: list[_Plan]) -> list[_Plan]:
        written: list[_Plan] = []
        start = 0
        while start < len(plans):
            chunk = plans[start:start + ctx.batcher.size]
            start += len(chunk)
            try:
                await ctx.run_batch(lambda chunk=chunk: self._write_plans(chunk))
                written.extend(chunk)
            except IntegrityError:
                # Someone saved a clashing mobile / email / code meanwhile: find the rows one by one
                written.extend(await ctx.run_batch(lambda chunk=chunk: self._write_one_by_one(chunk)))
        return written

    async def _write_plans(self, plans: list[_Plan]) -> None:
        await self._repository.insert_many(
            users=[plan.user_insert for plan in plans if plan.user_insert],
            addresses=[plan.address_insert for plan in plans if plan.address_insert],
            banks=[plan.bank_insert for plan in plans if plan.bank_insert],
            farmers=[plan.farmer_insert for plan in plans if plan.farmer_insert],
        )
        await self._repository.update_many(
            users=[plan.user_update for plan in plans if plan.user_update],
            passwords=[plan.password_update for plan in plans if plan.password_update],
            addresses=[plan.address_update for plan in plans if plan.address_update],
            banks=[plan.bank_update for plan in plans if plan.bank_update],
            farmers=[plan.farmer_update for plan in plans if plan.farmer_update],
        )

    async def _write_one_by_one(self, plans: list[_Plan]) -> list[_Plan]:
        written = []
        for plan in plans:
            try:
                async with self._database.transaction():          # savepoint inside the batch transaction
                    await self._write_plans([plan])
                written.append(plan)
            except IntegrityError as error:
                plan.row.reason = f"Saved by someone else at the same time ({_short(error)})"
        return written

    # =========================================================
    # REPORT
    # =========================================================

    async def _append_report(self, report: _Report, rows: list[_Row]) -> None:
        lines = []
        for row in rows:
            cells = [None if column.key == "password" else row.raw.cells.get(column.key) for column in _IMPORT_COLUMNS]
            lines.append([*cells, row.raw.row_no, row.reason])
        if report.writer is None:
            report.writer = await asyncio.to_thread(
                XlsxSheetWriter, report.path, FARMER_SHEET, columns=_IMPORT_COLUMNS,
                extra_columns=(ExtraColumn("Row No", 10), ExtraColumn("Reason", 60)), tmpdir=report.path.parent,
            )
        await asyncio.to_thread(report.writer.write_rows, lines)

    @staticmethod
    async def _close_report(report: _Report) -> None:
        if report.writer is not None:
            await asyncio.to_thread(report.writer.write_instructions)
            await asyncio.to_thread(report.writer.close)


def _short(error: IntegrityError) -> str:
    text = str(getattr(error, "orig", error))
    return text.split("\n", 1)[0][:120]
