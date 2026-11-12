"""Runtime and memory measurement helpers (spec B9; D12).

Peak process memory:
- Windows: ``PeakWorkingSetSize`` from ``GetProcessMemoryInfo`` (D12), in bytes.
- Unix: ``resource.getrusage(RUSAGE_SELF).ru_maxrss`` (kilobytes on Linux,
  bytes on macOS), converted to bytes.
The delta is the peak after the measured phase minus the peak at the
baseline, which is taken after imports and loading. Memory runs happen in
their own processes, separate from timing runs, because profiling adds
overhead.
"""

from __future__ import annotations

import sys

import numpy as np


def peak_memory_bytes() -> int:
    if sys.platform == "win32":
        import ctypes
        from ctypes import wintypes

        class ProcessMemoryCounters(ctypes.Structure):
            _fields_ = [("cb", wintypes.DWORD), ("PageFaultCount", wintypes.DWORD),
                        ("PeakWorkingSetSize", ctypes.c_size_t), ("WorkingSetSize", ctypes.c_size_t),
                        ("QuotaPeakPagedPoolUsage", ctypes.c_size_t), ("QuotaPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaPeakNonPagedPoolUsage", ctypes.c_size_t),
                        ("QuotaNonPagedPoolUsage", ctypes.c_size_t),
                        ("PagefileUsage", ctypes.c_size_t), ("PeakPagefileUsage", ctypes.c_size_t)]

        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        psapi = ctypes.WinDLL("psapi", use_last_error=True)
        kernel32.GetCurrentProcess.restype = wintypes.HANDLE
        psapi.GetProcessMemoryInfo.argtypes = [wintypes.HANDLE, ctypes.POINTER(ProcessMemoryCounters),
                                               wintypes.DWORD]
        psapi.GetProcessMemoryInfo.restype = wintypes.BOOL
        counters = ProcessMemoryCounters()
        counters.cb = ctypes.sizeof(ProcessMemoryCounters)
        if not psapi.GetProcessMemoryInfo(kernel32.GetCurrentProcess(), ctypes.byref(counters), counters.cb):
            raise OSError(f"GetProcessMemoryInfo failed (error {ctypes.get_last_error()})")
        return int(counters.PeakWorkingSetSize)
    import resource

    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def coefficient_of_variation(values) -> float:
    values = np.asarray(values, dtype=np.float64)
    if values.size < 2 or values.mean() == 0:
        return float("nan")
    return float(values.std(ddof=1) / values.mean())
