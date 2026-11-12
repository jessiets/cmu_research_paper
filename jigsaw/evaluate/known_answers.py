"""Known-answer relation scores for gate G5 (spec B10)."""

from __future__ import annotations

import numpy as np

from jigsaw.evaluate.metrics import Truth
from jigsaw.relations import WORST


def _blank(n: int, value: float) -> dict[str, np.ndarray]:
    scores = {key: np.full((n, n), value, dtype=np.float64) for key in ("right", "below")}
    for matrix in scores.values():
        np.fill_diagonal(matrix, WORST)
    return scores


def _true_cell(rel: str, i: int, j: int) -> tuple[str, int, int]:
    return {"b_right_of_a": ("right", i, j), "b_left_of_a": ("right", j, i),
            "b_below_a": ("below", i, j), "b_above_a": ("below", j, i)}[rel]


def oracle(truth: Truth) -> dict[str, np.ndarray]:
    """1 on each true relation, 0 elsewhere."""
    scores = _blank(truth.n, 0.0)
    for i, j, rel in truth.pairs:
        key, a, b = _true_cell(rel, i, j)
        scores[key][a, b] = 1.0
    return scores


def reversed_oracle(truth: Truth) -> dict[str, np.ndarray]:
    """0 on all four relations of every true pair, 1 elsewhere: true pairs rank last."""
    scores = _blank(truth.n, 1.0)
    for i, j, _ in truth.pairs:
        scores["right"][i, j] = scores["right"][j, i] = 0.0
        scores["below"][i, j] = scores["below"][j, i] = 0.0
    return scores


def random_scores(truth: Truth, seed: int) -> dict[str, np.ndarray]:
    rng = np.random.default_rng(seed)
    scores = {key: rng.random((truth.n, truth.n)) for key in ("right", "below")}
    for matrix in scores.values():
        np.fill_diagonal(matrix, WORST)
    return scores


def all_tied(truth: Truth) -> dict[str, np.ndarray]:
    return _blank(truth.n, 0.0)
