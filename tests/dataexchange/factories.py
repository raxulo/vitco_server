"""
Test data factories: real VLCC / farmer / user / address / bank rows (bulk Core inserts)
and a real JobContext for running processors outside the worker loop.
"""

from __future__ import annotations

import itertools
from dataclasses import dataclass
from pathlib import Path
from uuid import UUID, uuid4

from app.core.clock import now_naive_ist
from app.core.database.manager import DatabaseManager
from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.common.address.infrastructure.models import AddressModel
from app.modules.common.bank.infrastructure.models import BankAccountModel
from app.modules.dataexchange.application.batching import AdaptiveBatcher, MemoryGuard
from app.modules.dataexchange.application.processor import JobContext
from app.modules.dataexchange.domain.entities import ExcelJob
from app.modules.dataexchange.domain.enums import ExcelJobKind, ExcelJobStatus, ImportMode
from app.modules.dataexchange.infrastructure.repository import ExcelJobRepository
from app.modules.dataexchange.infrastructure.storage import ExchangeStorage
from app.modules.farmer.domain.enums import MilkType
from app.modules.farmer.infrastructure.models import FarmerModel
from app.modules.vlcc.infrastructure.models import VlccModel

_sequence = itertools.count(1)


def unique_mobile() -> str:
    """A 10-digit mobile unique within the test session."""
    return f"6{next(_sequence) + 100_000_000 * 3:09d}"[-10:]


@dataclass(slots=True)
class VlccRef:
    id: UUID
    user_id: UUID
    code: str


async def create_vlcc(database: DatabaseManager, *, created_by: UUID | None = None, farmer_enabled: bool = True) -> VlccRef:
    now = now_naive_ist()
    user_id, vlcc_id = uuid4(), uuid4()
    code = f"V{next(_sequence):06d}"
    async with database.transaction() as session:
        await session.execute(UserModel.__table__.insert(), [dict(
            id=user_id, name=f"VLCC {code}", email=f"{code.lower()}-{user_id.hex[:6]}@vlcc.test",
            mobile=unique_mobile(), password_hash="x", role=Role.VLCC, is_active=True, is_locked=False,
            created_by=created_by, created_at=now, updated_at=now, is_deleted=False,
        )])
        await session.execute(VlccModel.__table__.insert(), [dict(
            id=vlcc_id, user_id=user_id, uic_code=f"U{code}", vlcc_code=code, name=f"Center {code}",
            farmer_enabled=farmer_enabled, is_active=True, created_by=created_by, created_at=now, updated_at=now,
            is_deleted=False, soc_percentage=0.0, assigned_chart_rank=1,
        )])
    return VlccRef(id=vlcc_id, user_id=user_id, code=code)


async def create_farmers(
    database: DatabaseManager,
    vlcc: VlccRef,
    count: int,
    *,
    prefix: str = "F",
    with_address: bool = True,
    with_bank: bool = True,
    deleted: bool = False,
) -> list[dict]:
    """Insert `count` farmers; returns their sheet-shaped values (keys as in FARMER_SHEET)."""
    now = now_naive_ist()
    created = []
    for start in range(0, count, 500):
        users, addresses, banks, farmers = [], [], [], []
        for i in range(start, min(start + 500, count)):
            user_id = uuid4()
            address_id = uuid4() if with_address else None
            bank_id = uuid4() if with_bank else None
            code = f"{prefix}{i:06d}"
            mobile = unique_mobile()
            values = dict(farmer_code=code, name=f"Farmer {code}", mobile=mobile,
                          email=f"{code.lower()}-{user_id.hex[:8]}@farmer.test", milk_type=MilkType.COW,
                          assigned_chart_rank=2, sms_enabled=True, is_active=True,
                          address_line="Main Road" if with_address else None, city="Indore" if with_address else None,
                          state="MP" if with_address else None, pincode="452001" if with_address else None,
                          account_holder=f"Farmer {code}" if with_bank else None, bank_name="SBI" if with_bank else None,
                          account_number=f"{i:016d}" if with_bank else None,
                          ifsc_code="SBIN0001234" if with_bank else None, upi_id=None,
                          user_id=user_id, address_id=address_id, bank_account_id=bank_id)
            created.append(values)
            users.append(dict(id=user_id, name=values["name"], email=values["email"], mobile=mobile,
                              password_hash="x", role=Role.FARMER, is_active=True, is_locked=False,
                              created_by=vlcc.user_id, created_at=now, updated_at=now, is_deleted=False))
            if with_address:
                addresses.append(dict(id=address_id, user_id=user_id, line="Main Road", city="Indore", state="MP",
                                      pincode="452001", created_at=now, updated_at=now))
            if with_bank:
                banks.append(dict(id=bank_id, user_id=user_id, account_holder=values["name"], bank_name="SBI",
                                  account_number=values["account_number"], ifsc_code="SBIN0001234",
                                  created_at=now, updated_at=now))
            farmers.append(dict(id=uuid4(), user_id=user_id, farmer_code=code, vlcc_id=vlcc.id,
                                address_id=address_id, bank_account_id=bank_id, milk_type=MilkType.COW,
                                assigned_chart_rank=2, sms_enabled=True, is_active=True, created_by=vlcc.user_id,
                                created_at=now, updated_at=now, is_deleted=deleted))
        async with database.transaction() as session:
            await session.execute(UserModel.__table__.insert(), users)
            if addresses:
                await session.execute(AddressModel.__table__.insert(), addresses)
            if banks:
                await session.execute(BankAccountModel.__table__.insert(), banks)
            await session.execute(FarmerModel.__table__.insert(), farmers)
    return created


async def make_context(
    database: DatabaseManager,
    *,
    kind: ExcelJobKind,
    owner_id: UUID,
    owner_role: Role,
    target_id: UUID | None,
    job_dir: Path,
    mode: ImportMode | None = None,
    dry_run: bool = False,
    source_file: str | None = None,
) -> JobContext:
    repository = ExcelJobRepository(database)
    now = now_naive_ist()
    job = ExcelJob(id=uuid4(), kind=kind, status=ExcelJobStatus.RUNNING, created_by=owner_id,
                   owner_role=int(owner_role), target_id=target_id, mode=mode, dry_run=dry_run,
                   source_file=source_file, created_at=now, started_at=now, heartbeat_at=now)
    async with database.transaction():
        await repository.create(job)
    job_dir.mkdir(parents=True, exist_ok=True)
    storage = ExchangeStorage(job_dir.parent, max_upload_bytes=10 ** 9, min_free_bytes=0)
    return JobContext(
        job=job, job_dir=job_dir, database=database, repository=repository, disk=storage,
        batcher=AdaptiveBatcher(budget_ms=250, maximum=500), memory=MemoryGuard(hard_mb=4096), pause_ms=0,
    )
