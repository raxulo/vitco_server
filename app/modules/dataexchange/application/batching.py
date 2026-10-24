"""
Adaptive Batching & Memory Guard

`AdaptiveBatcher` keeps every worker write transaction near a time budget
(DECISION-010): slow transactions halve the batch, fast ones grow it, so the
SQLite write lock is never held long enough to block API writers.

`MemoryGuard` watches the worker's resident memory: above the soft limit it
shrinks the batch, above the hard limit it stops the job cleanly instead of
letting the OS kill the process (DECISION-008).

Python 3.13+
"""

from __future__ import annotations

import os
import sys
from collections.abc import Callable


class WorkerMemoryLimitError(RuntimeError):
    """The worker process is above its hard memory limit."""


class AdaptiveBatcher:

    __slots__ = ("_budget_ms", "_minimum", "_maximum", "_size")

    def __init__(self, *, budget_ms: int, start: int = 200, minimum: int = 20, maximum: int = 500) -> None:
        self._budget_ms = budget_ms
        self._minimum = minimum
        self._maximum = max(maximum, minimum)
        self._size = min(max(start, minimum), self._maximum)

    @property
    def size(self) -> int:
        return self._size

    def record(self, duration_ms: float) -> None:
        """Feed the duration of the last write transaction."""
        if duration_ms > self._budget_ms:
            self.shrink()
        elif duration_ms < self._budget_ms * 0.4:
            self._size = min(self._maximum, max(self._size + 1, int(self._size * 1.25)))

    def shrink(self) -> None:
        self._size = max(self._minimum, self._size // 2)


class MemoryGuard:

    __slots__ = ("_soft_bytes", "_hard_bytes", "_reader")

    def __init__(self, *, hard_mb: int, reader: Callable[[], int] | None = None) -> None:
        self._hard_bytes = hard_mb * 1024 * 1024
        self._soft_bytes = int(self._hard_bytes * 0.8)
        self._reader = reader or read_rss_bytes

    def check(self, batcher: AdaptiveBatcher) -> int:
        """Return the current RSS; shrink the batch above the soft limit, raise above the hard one."""
        rss = self._reader()
        if rss > self._hard_bytes:
            raise WorkerMemoryLimitError("Worker memory limit reached")
        if rss > self._soft_bytes:
            batcher.shrink()
        return rss


def read_rss_bytes() -> int:
    """Resident memory of this process in bytes (0 when the platform does not tell)."""
    try:
        if sys.platform.startswith("linux"):
            with open("/proc/self/statm", "rb") as handle:
                resident_pages = int(handle.read().split()[1])
            return resident_pages * os.sysconf("SC_PAGE_SIZE")
        if sys.platform == "win32":
            return _windows_rss()
        import resource

        usage = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        return usage if sys.platform == "darwin" else usage * 1024
    except Exception:
        return 0


def _windows_rss() -> int:
    import ctypes
    from ctypes import wintypes

    class ProcessMemoryCounters(ctypes.Structure):
        _fields_ = [
            ("cb", wintypes.DWORD),
            ("PageFaultCount", wintypes.DWORD),
            ("PeakWorkingSetSize", ctypes.c_size_t),
            ("WorkingSetSize", ctypes.c_size_t),
            ("QuotaPeakPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPagedPoolUsage", ctypes.c_size_t),
            ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
            ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
            ("PagefileUsage", ctypes.c_size_t),
            ("PeakPagefileUsage", ctypes.c_size_t),
        ]

    # Explicit types: without them the 64-bit pseudo-handle is truncated and the call fails silently
    kernel32 = ctypes.WinDLL("kernel32")
    kernel32.GetCurrentProcess.restype = wintypes.HANDLE
    psapi = ctypes.WinDLL("psapi")
    psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters), wintypes.DWORD]
    psapi.GetProcessMemoryInfo.restype = wintypes.BOOL

    counters = ProcessMemoryCounters()
    counters.cb = ctypes.sizeof(counters)
    if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
        return 0
    return int(counters.WorkingSetSize)
