"""Rank fusion (spec B7).

For each relation matrix, each candidate gets its row rank plus its column
rank (average ranks for ties; higher score = higher rank). Channels are then
added with equal weights. Weights are never tuned. Ranks depend only on
values, never on piece order, so fusion keeps gate G4's permutation
invariance.
"""

from __future__ import annotations

import numpy as np
from scipy.stats import rankdata


def row_col_rank(matrix: np.ndarray) -> np.ndarray:
    return rankdata(matrix, axis=1, method="average") + rankdata(matrix, axis=0, method="average")


def rank_fuse(channels: list[np.ndarray]) -> np.ndarray:
    """Equal-weight sum of row + column ranks across evidence channels."""
    if not channels:
        raise ValueError("rank fusion needs at least one channel")
    return np.sum([row_col_rank(c) for c in channels], axis=0).astype(np.float64)
