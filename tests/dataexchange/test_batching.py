"""
AdaptiveBatcher and MemoryGuard (Plan 1.4, task 1).
"""

from __future__ import annotations

import pytest

from app.modules.dataexchange.application.batching import (
    AdaptiveBatcher,
    MemoryGuard,
    WorkerMemoryLimitError,
    read_rss_bytes,
)

MB = 1024 * 1024


def test_slow_transactions_halve_the_batch_but_never_below_minimum():
    batcher = AdaptiveBatcher(budget_ms=250, start=200, minimum=20, maximum=500)

    sizes = []
    for _ in range(6):
        batcher.record(400)
        sizes.append(batcher.size)

    assert sizes == [100, 50, 25, 20, 20, 20]


def test_fast_transactions_grow_the_batch_up_to_maximum():
    batcher = AdaptiveBatcher(budget_ms=250, start=200, minimum=20, maximum=500)

    for _ in range(10):
        batcher.record(10)

    assert batcher.size == 500


def test_transactions_near_budget_keep_the_size():
    batcher = AdaptiveBatcher(budget_ms=250, start=200)

    batcher.record(200)                         # between 40% and 100% of the budget

    assert batcher.size == 200


def test_start_is_clamped_into_bounds():
    assert AdaptiveBatcher(budget_ms=250, start=5000, maximum=500).size == 500
    assert AdaptiveBatcher(budget_ms=250, start=1, minimum=20).size == 20


def test_memory_guard_shrinks_above_soft_limit():
    batcher = AdaptiveBatcher(budget_ms=250, start=200)
    guard = MemoryGuard(hard_mb=1000, reader=lambda: 850 * MB)      # soft limit = 800 MB

    assert guard.check(batcher) == 850 * MB
    assert batcher.size == 100


def test_memory_guard_leaves_batch_alone_below_soft_limit():
    batcher = AdaptiveBatcher(budget_ms=250, start=200)

    MemoryGuard(hard_mb=1000, reader=lambda: 300 * MB).check(batcher)

    assert batcher.size == 200


def test_memory_guard_raises_above_hard_limit():
    with pytest.raises(WorkerMemoryLimitError, match="Worker memory limit reached"):
        MemoryGuard(hard_mb=1000, reader=lambda: 1001 * MB).check(AdaptiveBatcher(budget_ms=250))


def test_real_rss_reader_reports_this_process():
    rss = read_rss_bytes()

    assert 10 * MB < rss < 4096 * MB            # a Python test process is somewhere in here
