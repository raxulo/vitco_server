"""
Test worker process: the real exchange worker plus two test processors.

    python -m tests.dataexchange.worker_fixture --parent-pid <pid>

Used by the supervisor tests so they can kill / restart a real process
without adding test-only code to `app.worker.exchange`.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from uuid import uuid4

from app.modules.administration.domain.enums import Role
from app.modules.administration.infrastructure.models import UserModel
from app.modules.dataexchange.application.processor import JobContext, ProcessorResult
from app.modules.dataexchange.domain.enums import ExcelJobKind
from app.worker.exchange import _configure_logging, build_worker


class SlowInsert:
    """FARMER_IMPORT: 400 batches of 5 users, 0.1 s apart — long enough to be killed mid-way."""

    kind = ExcelJobKind.FARMER_IMPORT

    def __init__(self, database) -> None:
        self.database = database

    async def run(self, ctx: JobContext) -> ProcessorResult:
        ctx.total = 2000
        for number in range(400):
            async def write(number=number):
                session = self.database.session
                for i in range(5):
                    uid = uuid4()
                    session.add(UserModel(
                        id=uid, name="Supervisor Test", email=f"sv-{ctx.job.id.hex}-{number}-{i}@w.test",
                        mobile=f"6{str(uid.int)[-9:]}", password_hash="x", role=Role.FARMER,
                    ))
                await session.flush()

            await ctx.run_batch(write)
            ctx.processed += 5
            ctx.inserted += 5
            await asyncio.sleep(0.1)
            await ctx.checkpoint()
        return ProcessorResult()


class QuickExport:
    """VLCC_EXPORT: finishes at once."""

    kind = ExcelJobKind.VLCC_EXPORT

    async def run(self, ctx: JobContext) -> ProcessorResult:
        ctx.total = ctx.processed = 1
        return ProcessorResult(result_file="result.xlsx")


async def _main(parent_pid: int | None) -> None:
    worker, database = build_worker(parent_pid)
    worker.register(SlowInsert(database))
    worker.register(QuickExport())
    await database.startup()
    try:
        await worker.run()
    finally:
        await database.shutdown()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--parent-pid", type=int, default=None)
    args = parser.parse_args()
    _configure_logging()
    asyncio.run(_main(args.parent_pid))
    return 0


if __name__ == "__main__":
    sys.exit(main())
