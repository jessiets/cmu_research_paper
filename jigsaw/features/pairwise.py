"""Chunked all-pairs side comparisons, shared by the per-side measures."""

from __future__ import annotations

import numpy as np

CHUNK_ROWS = 32  # keeps the (chunk, n, K, d) intermediate under ~150 MB at n = 600


def mean_l1(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """out[i, j] = mean_k sum_d |a[i, k, d] - b[j, k, d]|.  a, b: (n, K, d)."""
    return _pairwise(a, b, lambda diff: np.abs(diff).sum(axis=-1).mean(axis=-1))


def mean_squared(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """out[i, j] = mean_k sum_d (a[i, k, d] - b[j, k, d])^2.  a, b: (n, K, d)."""
    return _pairwise(a, b, lambda diff: np.square(diff).sum(axis=-1).mean(axis=-1))


def _pairwise(a: np.ndarray, b: np.ndarray, reduce) -> np.ndarray:
    n = a.shape[0]
    out = np.empty((n, b.shape[0]), dtype=np.float64)
    for start in range(0, n, CHUNK_ROWS):
        stop = min(start + CHUNK_ROWS, n)
        out[start:stop] = reduce(a[start:stop, None, :, :] - b[None, :, :, :])
    return out
