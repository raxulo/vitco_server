"""
SeenKeys (Plan 1.3, task 3).
"""

from __future__ import annotations

import tracemalloc

from app.modules.dataexchange.infrastructure.seen_keys import SeenKeys


def test_duplicates_within_one_batch_report_the_first_row(tmp_path):
    with SeenKeys(tmp_path / "seen.sqlite3") as seen:
        duplicates = seen.check_and_add([
            ("code", "F1", 2),
            ("mobile", "9876543210", 2),
            ("code", "F2", 3),
            ("mobile", "9876543210", 3),       # repeats row 2
            ("code", "F1", 4),                 # repeats row 2
        ])

    assert duplicates == {("mobile", "9876543210", 3): 2, ("code", "F1", 4): 2}


def test_duplicates_across_batches(tmp_path):
    with SeenKeys(tmp_path / "seen.sqlite3") as seen:
        assert seen.check_and_add([("email", "a@x.in", 2), ("email", "b@x.in", 3)]) == {}
        duplicates = seen.check_and_add([("email", "c@x.in", 600), ("email", "a@x.in", 601)])

    assert duplicates == {("email", "a@x.in", 601): 2}


def test_same_value_in_different_kinds_does_not_collide(tmp_path):
    with SeenKeys(tmp_path / "seen.sqlite3") as seen:
        duplicates = seen.check_and_add([("code", "9876543210", 2), ("mobile", "9876543210", 2)])

    assert duplicates == {}


def test_scratch_file_is_removed_on_close(tmp_path):
    path = tmp_path / "seen.sqlite3"
    seen = SeenKeys(path)
    seen.check_and_add([("code", "F1", 2)])
    assert path.exists()

    seen.close()
    seen.close()                               # idempotent

    assert not path.exists()


def test_one_million_keys_keep_memory_flat(tmp_path):
    tracemalloc.start()
    with SeenKeys(tmp_path / "seen.sqlite3") as seen:
        for start in range(0, 1_000_000, 500):
            batch = [("mobile", f"9{row:09d}", row + 2) for row in range(start, start + 500)]
            assert seen.check_and_add(batch) == {}
        repeated = seen.check_and_add([("mobile", "9000000123", 2_000_000)])
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()

    print(f"\n1M keys: tracemalloc peak {peak / 1e6:.1f} MB")
    assert repeated == {("mobile", "9000000123", 2_000_000): 125}
    assert peak < 30e6
