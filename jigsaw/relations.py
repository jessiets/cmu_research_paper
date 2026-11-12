"""Relation-score layout shared by methods, the runner, and the evaluator (spec B6).

A method returns two ordered n x n float64 matrices, indexed by piece position in
the sorted ``piece_index.json`` order:

    right[i, j]  score that piece j is right of piece i  (i's R side vs j's L side)
    below[i, j]  score that piece j is below piece i      (i's B side vs j's T side)

Higher is more compatible. Excluded relations, filtered pairs, and the diagonal
hold ``WORST`` (-inf). These two matrices cover all four relations of an
unordered pair {A, B}: "B left of A" is ``right[B, A]`` and "B above A" is
``below[B, A]``.
"""

from __future__ import annotations

import numpy as np

RELATION_KEYS = ("right", "below")
WORST = -np.inf

# Relations of an unordered pair (a, b), in the order used for the winning relation.
PAIR_RELATIONS = ("b_right_of_a", "b_left_of_a", "b_below_a", "b_above_a")
FLIP = {"b_right_of_a": "b_left_of_a", "b_left_of_a": "b_right_of_a",
        "b_below_a": "b_above_a", "b_above_a": "b_below_a"}


def validate_relation_scores(scores: dict[str, np.ndarray], n: int) -> None:
    if set(scores) != set(RELATION_KEYS):
        raise ValueError(f"relation_scores must have exactly the keys {RELATION_KEYS}")
    for key in RELATION_KEYS:
        matrix = scores[key]
        if matrix.shape != (n, n) or matrix.dtype != np.float64:
            raise ValueError(f"{key} must be a float64 array of shape ({n}, {n})")
        if np.isnan(matrix).any():
            raise ValueError(f"{key} contains NaN; use WORST for excluded relations")
        if np.isposinf(matrix).any():
            raise ValueError(f"{key} contains +inf")
        if not np.all(np.diag(matrix) == WORST):
            raise ValueError(f"{key} diagonal must be WORST (a piece cannot pair with itself)")
