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


def test_sustained_slow_transactions_shrink_to_the_minimum_and_not_below():
    batcher = AdaptiveBatcher(budget_ms=250, start=200, minimum=20, maximum=500)

    sizes = []
    for _ in range(40):
        batcher.record(400)
        sizes.append(batcher.size)

    assert sizes[0] == 100                       # first slow sample: halved at once
    assert sizes == sorted(sizes, reverse=True)  # never grows while slow
    assert sizes[-1] == 20


def test_a_single_slow_commit_does_not_shrink_a_healthy_batch():
    batcher = AdaptiveBatcher(budget_ms=250, start=300, maximum=500)
    for _ in range(5):
        batcher.record(150)                      # healthy: inside the budget
    size = batcher.size

    batcher.record(450)                          # one WAL-checkpoint spike

    assert batcher.size == size


def test_cost_proportional_to_size_settles_inside_the_budget():
    batcher = AdaptiveBatcher(budget_ms=250, start=20, minimum=20, maximum=5000)

    for _ in range(200):
        batcher.record(batcher.size * 0.5)       # 0.5 ms per row -> 500 rows fit the budget

    assert 200 <= batcher.size <= 500


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
