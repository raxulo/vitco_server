"""
VLCC Import Processor

Upserts the VLCCs owned by one selected owner (Admin, Sub Admin, MCC) from an xlsx file (REQ-12 … REQ-16):

  read batch (thread, next batch prefetched)
    → parse cells → classify insert / update → check hierarchy code conflicts
    → check user contact collisions (emails, mobiles) → in-file duplicates (SeenKeys)
    → hash custom passwords in parallel
    → Core bulk INSERT / UPDATE across 6 tables, sub-batched to the lock budget
    → discarded rows streamed to report file

Python 3.13+
"""

from __future__ import annotations

import asyncio
import os
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from types import SimpleNamespace
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
    DEFAULT_VLCC_PASSWORD,
    VLCC_ADDRESS_KEYS,
    VLCC_BANK_KEYS,
    VLCC_MILK_QUALITY_KEYS,
    VLCC_SETTINGS_KEYS,
    VLCC_SHEET,
)
from app.modules.dataexchange.infrastructure.seen_keys import SeenKeys
from app.modules.dataexchange.infrastructure.vlcc_repository import ExistingVlcc, VlccExchangeRepository
from app.modules.dataexchange.infrastructure.xlsx import ExtraColumn, RawRow, XlsxSheetReader, XlsxSheetWriter

_REPORT_FILE = "discarded_rows.xlsx"
_IMPORT_COLUMNS = VLCC_SHEET.import_columns()
_HEADERS = {column.key: column.header for column in VLCC_SHEET.columns}

_VLCC_REQUIRED_INSERT = ("vlcc_code", "uic_code", "vlcc_name", "user_name", "mobile")
_USER_FIELDS = ("name", "email", "mobile", "is_active")
_ADDRESS_COLUMNS = {"address_line": "line", "city": "city", "state": "state", "pincode": "pincode"}


@dataclass(slots=True)
class _Row:
    raw: RawRow
    values: dict[str, Any]
    errors: list[str]
    existing: ExistingVlcc | None = None
    reason: str | None = None


@dataclass(slots=True)
class _Plan:
    row: _Row
    is_insert: bool
    password: str | None = None
    user_insert: dict | None = None
    address_insert: dict | None = None
    bank_insert: dict | None = None
    settings_insert: dict | None = None
    milk_insert: dict | None = None
    vlcc_insert: dict | None = None

    user_update: dict | None = None
    password_update: dict | None = None
    address_update: dict | None = None
    bank_update: dict | None = None
    settings_update: dict | None = None
    milk_update: dict | None = None
    vlcc_update: dict | None = None

    @property
    def changes_something(self) -> bool:
        return self.is_insert or self.password is not None or any((
            self.user_update, self.password_update, self.address_insert, self.address_update,
            self.bank_insert, self.bank_update, self.settings_insert, self.settings_update,
            self.milk_insert, self.milk_update, self.vlcc_update,
        ))


@dataclass(slots=True)
class _Report:
    path: Path
    writer: XlsxSheetWriter | None = None
    pending: list[list] = field(default_factory=list)


class VlccImportProcessor:

    __slots__ = ("_database", "_repository", "_passwords", "_read_batch", "_hash_workers")

    kind = ExcelJobKind.VLCC_IMPORT

    def __init__(
        self,
        *,
        database: DatabaseManager,
        repository: VlccExchangeRepository,
        password_service: PasswordService,
        read_batch: int = 500,
        hash_workers: int | None = None,
    ) -> None:
        self._database = database
        self._repository = repository
        self._passwords = password_service
        self._read_batch = read_batch
        self._hash_workers = hash_workers or max(1, min(4, os.cpu_count() or 1))

    async def run(self, ctx: JobContext) -> ProcessorResult:
        if ctx.job.target_id is None or not ctx.job.source_file:
            raise ValueError("Import job has no owner or no file")
        source = ctx.job_dir / ctx.job.source_file
        default_hash = await asyncio.to_thread(self._passwords.hash, DEFAULT_VLCC_PASSWORD)
        report = _Report(path=ctx.job_dir / _REPORT_FILE)

        reader = XlsxSheetReader(source, VLCC_SHEET, scratch_dir=ctx.job_dir)
        await asyncio.to_thread(reader.__enter__)
        seen = SeenKeys(ctx.job_dir / "seen_keys.bin")
        pool = ThreadPoolExecutor(max_workers=self._hash_workers, thread_name_prefix="vlcc-import-hash")
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

    async def _process(
        self,
        ctx: JobContext,
        batch: list[RawRow],
        seen: SeenKeys,
        report: _Report,
        pool: ThreadPoolExecutor,
        default_hash: str,
    ) -> None:
        rows = [self._parse(raw) for raw in batch]
        mode = ctx.job.mode or ImportMode.UPSERT
        owner_id: UUID = ctx.job.target_id
        owner_obj = SimpleNamespace(id=owner_id, role_type=Role(ctx.job.owner_role))

        codes = sorted({row.values["vlcc_code"] for row in rows if not row.errors and "vlcc_code" in row.values})
        async with self._database.transaction():
            existing = await self._repository.existing_by_codes(owner_id, codes) if codes else {}
            conflicts = await self._repository.code_conflicts_in_hierarchy(owner_obj, codes, exclude_owner_id=owner_id) if codes else set()

        for row in rows:
            self._classify(row, existing, conflicts, mode)

        await self._check_contacts([row for row in rows if row.reason is None], seen)
        self._dedupe([row for row in rows if row.reason is None], seen)

        now = now_naive_ist()
        plans = [self._plan(row, ctx, now, default_hash) for row in rows if row.reason is None]
        changed = {id(plan) for plan in plans if plan.changes_something}
        if ctx.job.dry_run:
            written = plans
        else:
            await self._hash_passwords(plans, pool)
            written = await self._write(ctx, plans)
        accepted = {id(plan.row) for plan in written}
        for plan in plans:
            if id(plan.row) not in accepted and plan.row.reason is None:
                plan.row.reason = "Could not be saved"

        ctx.processed += len(rows)
        ctx.inserted += sum(1 for plan in written if plan.is_insert)
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
    def _classify(
        row: _Row,
        existing: dict[str, ExistingVlcc],
        conflicts: set[str],
        mode: ImportMode,
    ) -> None:
        if row.errors:
            row.reason = "; ".join(row.errors[:3])
            return
        code = row.values.get("vlcc_code")
        if not code:
            row.reason = "VLCC Code is required"
            return
        found = existing.get(code)
        if found is not None:
            if found.is_deleted:
                row.reason = f"VLCC code {code} belongs to a deleted VLCC"
            elif mode is ImportMode.CREATE_ONLY:
                row.reason = f"VLCC code {code} already exists"
            else:
                row.existing = found
            return

        # Check hierarchy code conflicts for new VLCCs (REQ-15)
        if code in conflicts:
            row.reason = f"VLCC code {code} is already used in this hierarchy"
            return

        missing = [_HEADERS[key] for key in _VLCC_REQUIRED_INSERT if key not in row.values]
        if missing:
            row.reason = f"{' and '.join(missing)} {'is' if len(missing) == 1 else 'are'} required for a new VLCC"

    async def _check_contacts(self, rows: list[_Row], seen: SeenKeys) -> None:
        emails, mobiles = set(), set()
        for row in rows:
            if "email" in row.values:
                emails.add(row.values["email"].lower())
            if "mobile" in row.values:
                mobiles.add(row.values["mobile"])

        async with self._database.transaction():
            taken_emails = await self._repository.users_by_emails(sorted(emails)) if emails else {}
            taken_mobiles = await self._repository.users_by_mobiles(sorted(mobiles)) if mobiles else {}

        for row in rows:
            if row.reason is not None:
                continue
            email = row.values.get("email")
            if email:
                owner = taken_emails.get(email.lower())
                if owner is not None and (row.existing is None or owner != row.existing.user_id):
                    row.reason = f"Email {email} is already registered"
                    continue
            mobile = row.values.get("mobile")
            if mobile:
                owner = taken_mobiles.get(mobile)
                if owner is not None and (row.existing is None or owner != row.existing.user_id):
                    row.reason = f"Mobile {mobile} is already registered"

    @staticmethod
    def _dedupe(rows: list[_Row], seen: SeenKeys) -> None:
        keyed = []
        for row in rows:
            keys = [("vlcc_code", row.values["vlcc_code"])]
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

    def _plan(self, row: _Row, ctx: JobContext, now, default_hash: str) -> _Plan:
        owner_id: UUID = ctx.job.target_id
        if row.existing is None:
            return self._plan_insert(row, owner_id, now, default_hash)
        return self._plan_update(row, owner_id, now)

    def _plan_insert(self, row: _Row, owner_id: UUID, now, default_hash: str) -> _Plan:
        plan = _Plan(row=row, is_insert=True)
        user_id = uuid4()
        code = row.values["vlcc_code"]
        email = row.values.get("email") or f"vlcc_{code}_{user_id.hex[:6]}@dairy.local"
        user_name = row.values["user_name"]

        plan.user_insert = dict(
            id=user_id, name=user_name, email=email, mobile=row.values["mobile"],
            password_hash=default_hash, role=Role.VLCC, is_active=row.values.get("is_active", True),
            is_locked=False, created_by=owner_id, created_at=now, updated_at=now, is_deleted=False,
        )
        if "password" in row.values:
            plan.password = row.values["password"]

        # Address
        address_id: UUID | None = None
        if any(key in row.values for key in VLCC_ADDRESS_KEYS):
            address_id = uuid4()
            plan.address_insert = dict(
                id=address_id, user_id=user_id,
                line=row.values.get("address_line"), city=row.values.get("city"),
                state=row.values.get("state"), pincode=row.values.get("pincode"),
                created_at=now, updated_at=now,
            )

        # Bank
        bank_id: UUID | None = None
        if any(key in row.values for key in VLCC_BANK_KEYS):
            bank_id = uuid4()
            plan.bank_insert = dict(
                id=bank_id, user_id=user_id,
                account_holder=row.values.get("account_holder") or user_name,
                bank_name=row.values.get("bank_name"),
                account_number=row.values.get("account_number"),
                ifsc_code=row.values.get("ifsc_code"),
                upi_id=row.values.get("upi_id"),
                created_at=now, updated_at=now,
            )

        # Settings (defaults applied on insert)
        settings_id = uuid4()
        plan.settings_insert = dict(
            id=settings_id, user_id=user_id,
            analyzer_type=row.values.get("analyzer_type", 0),
            analyzer_collection_mode=row.values.get("analyzer_collection_mode", 0),
            weight_unit=row.values.get("weight_unit", 0),
            weight_collection_mode=row.values.get("weight_collection_mode", 0),
            auto_tare_enabled=row.values.get("auto_tare_enabled", False),
            morning_collection_start=row.values.get("morning_collection_start", "06:00"),
            morning_collection_end=row.values.get("morning_collection_end", "10:00"),
            evening_collection_start=row.values.get("evening_collection_start", "12:00"),
            evening_collection_end=row.values.get("evening_collection_end", "22:00"),
            receipt_size=row.values.get("receipt_size", 0),
            printer_type=row.values.get("printer_type", 0),
            printer_enabled=row.values.get("printer_enabled", False),
            supported_cattle_type=row.values.get("cattle_type", 0),
            max_rate_chart_count=5, settings_edit_enabled=False,
            rate_chart_edit_enabled=False, master_enabled=False,
            created_at=now, updated_at=now,
        )

        # Milk Quality (defaults applied on insert)
        milk_id = uuid4()
        plan.milk_insert = dict(
            id=milk_id, user_id=user_id,
            cow_min_fat=row.values.get("cow_min_fat", 0.0),
            cow_max_fat=row.values.get("cow_max_fat", 0.0),
            cow_min_snf=row.values.get("cow_min_snf", 0.0),
            cow_max_snf=row.values.get("cow_max_snf", 0.0),
            buffalo_min_fat=row.values.get("buffalo_min_fat", 0.0),
            buffalo_max_fat=row.values.get("buffalo_max_fat", 0.0),
            buffalo_min_snf=row.values.get("buffalo_min_snf", 0.0),
            buffalo_max_snf=row.values.get("buffalo_max_snf", 0.0),
        )

        # VLCC
        plan.vlcc_insert = dict(
            id=uuid4(), user_id=user_id, uic_code=row.values["uic_code"],
            vlcc_code=code, name=row.values["vlcc_name"],
            contact_person=row.values.get("contact_person"),
            entry_mode=row.values.get("entry_mode", 0),
            route_code=row.values.get("route_code"),
            soc_percentage=row.values.get("soc_percentage", 0.0),
            farmer_enabled=row.values.get("farmer_enabled", True),
            is_active=row.values.get("is_active", True),
            assigned_chart_rank=row.values.get("assigned_chart_rank", 1),
            created_by=owner_id, address_id=address_id, bank_account_id=bank_id,
            settings_id=settings_id, milk_quality_config_id=milk_id,
            created_at=now, updated_at=now, is_deleted=False,
        )
        return plan

    def _plan_update(self, row: _Row, owner_id: UUID, now) -> _Plan:
        plan = _Plan(row=row, is_insert=False)
        existing = row.existing
        current = existing.values
        merged = {**current, **row.values}

        if "password" in row.values:
            plan.password = row.values["password"]

        # User update
        user_differs = (
            merged["user_name"] != current["user_name"]
            or merged["mobile"] != current["mobile"]
            or merged.get("email") != current.get("email")
            or merged["is_active"] != current["is_active"]
        )
        if user_differs:
            plan.user_update = dict(
                b_id=existing.user_id, name=merged["user_name"],
                email=merged.get("email") or current.get("email"),
                mobile=merged["mobile"], is_active=merged["is_active"],
                updated_at=now,
            )

        # Address
        address_id = existing.address_id
        if any(key in row.values for key in VLCC_ADDRESS_KEYS):
            addr = {dest: merged[src] for src, dest in _ADDRESS_COLUMNS.items()}
            if address_id is None:
                address_id = uuid4()
                plan.address_insert = dict(id=address_id, user_id=existing.user_id, created_at=now, updated_at=now, **addr)
            elif any(merged[k] != current.get(k) for k in VLCC_ADDRESS_KEYS):
                plan.address_update = dict(b_id=address_id, updated_at=now, **addr)

        # Bank
        bank_id = existing.bank_account_id
        if any(key in row.values for key in VLCC_BANK_KEYS):
            bank = {key: merged[key] for key in VLCC_BANK_KEYS}
            bank["account_holder"] = bank["account_holder"] or merged["user_name"]
            if bank_id is None:
                bank_id = uuid4()
                plan.bank_insert = dict(id=bank_id, user_id=existing.user_id, created_at=now, updated_at=now, **bank)
            elif any(merged[k] != current.get(k) for k in VLCC_BANK_KEYS):
                plan.bank_update = dict(b_id=bank_id, updated_at=now, **bank)

        # Settings
        settings_id = existing.settings_id
        if any(key in row.values for key in VLCC_SETTINGS_KEYS):
            st = dict(
                analyzer_type=merged.get("analyzer_type", current.get("analyzer_type", 0)),
                analyzer_collection_mode=merged.get("analyzer_collection_mode", current.get("analyzer_collection_mode", 0)),
                weight_unit=merged.get("weight_unit", current.get("weight_unit", 0)),
                weight_collection_mode=merged.get("weight_collection_mode", current.get("weight_collection_mode", 0)),
                auto_tare_enabled=merged.get("auto_tare_enabled", current.get("auto_tare_enabled", False)),
                morning_collection_start=merged.get("morning_collection_start", current.get("morning_collection_start", "06:00")),
                morning_collection_end=merged.get("morning_collection_end", current.get("morning_collection_end", "10:00")),
                evening_collection_start=merged.get("evening_collection_start", current.get("evening_collection_start", "12:00")),
                evening_collection_end=merged.get("evening_collection_end", current.get("evening_collection_end", "22:00")),
                receipt_size=merged.get("receipt_size", current.get("receipt_size", 0)),
                printer_type=merged.get("printer_type", current.get("printer_type", 0)),
                printer_enabled=merged.get("printer_enabled", current.get("printer_enabled", False)),
                supported_cattle_type=merged.get("cattle_type", current.get("cattle_type", 0)),
            )
            if settings_id is None:
                settings_id = uuid4()
                plan.settings_insert = dict(
                    id=settings_id, user_id=existing.user_id, max_rate_chart_count=5,
                    settings_edit_enabled=False, rate_chart_edit_enabled=False, master_enabled=False,
                    created_at=now, updated_at=now, **st,
                )
            elif any(merged.get(k) != current.get(k) for k in VLCC_SETTINGS_KEYS):
                plan.settings_update = dict(b_id=settings_id, updated_at=now, **st)

        # Milk Quality
        milk_id = existing.milk_quality_config_id
        if any(key in row.values for key in VLCC_MILK_QUALITY_KEYS):
            mq = {k: merged.get(k, current.get(k, 0.0)) for k in VLCC_MILK_QUALITY_KEYS}
            if milk_id is None:
                milk_id = uuid4()
                plan.milk_insert = dict(id=milk_id, user_id=existing.user_id, **mq)
            elif any(merged.get(k) != current.get(k) for k in VLCC_MILK_QUALITY_KEYS):
                plan.milk_update = dict(b_id=milk_id, **mq)

        # VLCC update
        vlcc_differs = (
            merged["uic_code"] != current["uic_code"]
            or merged["vlcc_name"] != current["vlcc_name"]
            or merged.get("contact_person") != current.get("contact_person")
            or merged.get("entry_mode") != current.get("entry_mode")
            or merged.get("route_code") != current.get("route_code")
            or merged.get("soc_percentage") != current.get("soc_percentage")
            or merged.get("farmer_enabled") != current.get("farmer_enabled")
            or merged["is_active"] != current["is_active"]
            or merged.get("assigned_chart_rank") != current.get("assigned_chart_rank")
            or address_id != existing.address_id
            or bank_id != existing.bank_account_id
            or settings_id != existing.settings_id
            or milk_id != existing.milk_quality_config_id
        )
        if vlcc_differs:
            plan.vlcc_update = dict(
                b_id=existing.vlcc_id, uic_code=merged["uic_code"],
                name=merged["vlcc_name"], contact_person=merged.get("contact_person"),
                entry_mode=merged.get("entry_mode", 0), route_code=merged.get("route_code"),
                soc_percentage=merged.get("soc_percentage", 0.0),
                farmer_enabled=merged.get("farmer_enabled", True),
                is_active=merged["is_active"],
                assigned_chart_rank=merged.get("assigned_chart_rank", 1),
                address_id=address_id, bank_account_id=bank_id,
                settings_id=settings_id, milk_quality_config_id=milk_id,
                updated_at=now,
            )
        return plan

    async def _hash_passwords(self, plans: list[_Plan], pool: ThreadPoolExecutor) -> None:
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
                written.extend(await ctx.run_batch(lambda chunk=chunk: self._write_one_by_one(chunk)))
        return written

    async def _write_plans(self, plans: list[_Plan]) -> None:
        await self._repository.insert_many(
            users=[plan.user_insert for plan in plans if plan.user_insert],
            addresses=[plan.address_insert for plan in plans if plan.address_insert],
            banks=[plan.bank_insert for plan in plans if plan.bank_insert],
            settings=[plan.settings_insert for plan in plans if plan.settings_insert],
            milk_configs=[plan.milk_insert for plan in plans if plan.milk_insert],
            vlccs=[plan.vlcc_insert for plan in plans if plan.vlcc_insert],
        )
        await self._repository.update_many(
            users=[plan.user_update for plan in plans if plan.user_update],
            passwords=[plan.password_update for plan in plans if plan.password_update],
            addresses=[plan.address_update for plan in plans if plan.address_update],
            banks=[plan.bank_update for plan in plans if plan.bank_update],
            settings=[plan.settings_update for plan in plans if plan.settings_update],
            milk_configs=[plan.milk_update for plan in plans if plan.milk_update],
            vlccs=[plan.vlcc_update for plan in plans if plan.vlcc_update],
        )

    async def _write_one_by_one(self, plans: list[_Plan]) -> list[_Plan]:
        written = []
        for plan in plans:
            try:
                async with self._database.transaction():
                    await self._write_plans([plan])
                written.append(plan)
            except IntegrityError as error:
                plan.row.reason = f"Saved by someone else at the same time ({_short(error)})"
        return written

    async def _append_report(self, report: _Report, rows: list[_Row]) -> None:
        lines = []
        for row in rows:
            cells = [None if column.key == "password" else row.raw.cells.get(column.key) for column in _IMPORT_COLUMNS]
            lines.append([*cells, row.raw.row_no, row.reason])
        if report.writer is None:
            report.writer = await asyncio.to_thread(
                XlsxSheetWriter, report.path, VLCC_SHEET, columns=_IMPORT_COLUMNS,
                extra_columns=(ExtraColumn("Row No", 10), ExtraColumn("Reason", 60)), tmpdir=report.path.parent,
            )
        await asyncio.to_thread(report.writer.write_rows, lines)

    async def _close_report(self, report: _Report) -> None:
        if report.writer is not None:
            await asyncio.to_thread(report.writer.write_instructions)
            await asyncio.to_thread(report.writer.close)


def _short(error: Exception) -> str:
    message = str(error)
    return message.split("\n")[0][:120]
