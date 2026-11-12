"""Evaluator known-answer and hand-computed tests (gate G5)."""

from __future__ import annotations

import numpy as np
import pytest
from sklearn.metrics import average_precision_score

from jigsaw.evaluate import known_answers as ka
from jigsaw.evaluate.gates import check_truth, expected_random_ap
from jigsaw.evaluate.metrics import (average_precision, evaluate, top_e_weights,
                                     truth_from_dict)
from jigsaw.relations import WORST
from jigsaw.run.pairs import to_pair_scores


def grid_truth(rows: int, cols: int, seed: int = 0):
    """Truth for a rows x cols grid with shuffled piece IDs."""
    perm = np.random.default_rng(seed).permutation(rows * cols)
    ids = {(r, c): f"p{perm[r * cols + c]:04d}" for r in range(rows) for c in range(cols)}
    pairs = []
    for r in range(rows):
        for c in range(cols):
            if c + 1 < cols:
                pairs.append({"a": ids[(r, c)], "b": ids[(r, c + 1)], "relation": "b_right_of_a"})
            if r + 1 < rows:
                pairs.append({"a": ids[(r, c)], "b": ids[(r + 1, c)], "relation": "b_below_a"})
    data = {"rows": rows, "cols": cols, "pieces": {v: {} for v in ids.values()}, "true_pairs": pairs}
    return truth_from_dict(data, tuple(sorted(ids.values())))


def blank(n: int, value: float = 0.0) -> dict[str, np.ndarray]:
    scores = {k: np.full((n, n), value) for k in ("right", "below")}
    for m in scores.values():
        np.fill_diagonal(m, WORST)
    return scores


# ---- AP ------------------------------------------------------------------------------

def test_ap_hand_computed() -> None:
    # Ranks: T, F, T, F  ->  AP = (1/1 + 2/3) / 2
    assert average_precision(np.array([0.9, 0.8, 0.7, 0.6]), np.array([1, 0, 1, 0])) == pytest.approx(5 / 6)


def test_ap_ties_form_one_threshold() -> None:
    # {0.9: T} then {0.5: F, T} together: AP = 0.5 * 1 + 0.5 * (2/3)
    assert average_precision(np.array([0.9, 0.5, 0.5]), np.array([1, 0, 1])) == pytest.approx(5 / 6)
    # Order inside a tie must not matter.
    assert average_precision(np.array([0.5, 0.5, 0.9]), np.array([1, 0, 1])) == pytest.approx(5 / 6)


def test_ap_handles_worst_scores_and_matches_sklearn() -> None:
    rng = np.random.default_rng(3)
    scores = np.round(rng.random(500), 2)  # many ties
    labels = rng.random(500) < 0.1
    assert average_precision(scores, labels) == pytest.approx(average_precision_score(labels, scores), abs=1e-12)
    with_worst = np.where(rng.random(500) < 0.3, WORST, scores)
    finite = np.where(np.isinf(with_worst), -1.0, with_worst)
    assert average_precision(with_worst, labels) == pytest.approx(average_precision(finite, labels))


def test_expected_random_ap_matches_simulation() -> None:
    rng = np.random.default_rng(0)
    labels = np.zeros(60, dtype=bool)
    labels[:6] = True
    sims = [average_precision(rng.random(60), labels) for _ in range(4000)]
    assert np.mean(sims) == pytest.approx(expected_random_ap(60, 6), abs=0.005)


# ---- top-E cut-off and top-1 ties ---------------------------------------------------

def test_top_e_weights_split_cutoff_ties() -> None:
    w = top_e_weights(np.array([3.0, 2.0, 2.0, 2.0, 1.0]), 2)
    assert w.tolist() == pytest.approx([1.0, 1 / 3, 1 / 3, 1 / 3, 0.0])
    assert w.sum() == pytest.approx(2.0)


def test_top1_counts_ties_fractionally() -> None:
    truth = grid_truth(1, 3)  # a row of three pieces: four non-border sides
    # Every side's two candidates tie at 0, so each side earns 1/2.
    m = evaluate(blank(3), truth)
    assert m.top1 == pytest.approx(0.5)
    assert m.non_border_sides == 4
    # Lift one side's true partner above its rival: that side now earns 1.
    i, j, rel = truth.pairs[0]
    left, right = (i, j) if rel == "b_right_of_a" else (j, i)
    scores = blank(3)
    scores["right"][left, right] = 1.0
    m = evaluate(scores, truth)
    # left piece's R side: 1; right piece's L side: 1 (its column now has a unique best); others 1/2.
    assert m.top1 == pytest.approx((1 + 1 + 0.5 + 0.5) / 4)


# ---- known answers ------------------------------------------------------------------

@pytest.mark.parametrize(("rows", "cols"), [(2, 3), (6, 9), (12, 18)])
def test_known_answers(rows: int, cols: int) -> None:
    truth = grid_truth(rows, cols, seed=rows)
    result = check_truth(truth)
    assert result["pass"], result["checks"]
    assert result["true_pairs"] == 2 * rows * cols - rows - cols


def test_oracle_direction_and_reversed_direction() -> None:
    truth = grid_truth(3, 4)
    o = evaluate(ka.oracle(truth), truth)
    assert o.relation_accuracy == 1.0
    # Transposed oracle: right and below swapped -> every true pair found with the wrong direction.
    swapped = ka.oracle(truth)
    swapped = {"right": swapped["below"], "below": swapped["right"]}
    m = evaluate(swapped, truth)
    assert m.ap == 1.0 and m.relation_accuracy == 0.0


def test_relation_ties_split_direction_credit() -> None:
    truth = grid_truth(1, 2)
    scores = blank(2, 0.0)  # all four relations tie
    m = evaluate(scores, truth)
    assert m.relation_accuracy == pytest.approx(0.25)


def test_filter_recall_counts_excluded_true_relations() -> None:
    truth = grid_truth(2, 2)
    scores = ka.oracle(truth)
    i, j, rel = truth.pairs[0]
    cell = {"b_right_of_a": ("right", i, j), "b_left_of_a": ("right", j, i),
            "b_below_a": ("below", i, j), "b_above_a": ("below", j, i)}[rel]
    scores[cell[0]][cell[1], cell[2]] = WORST
    assert evaluate(scores, truth).filter_recall == pytest.approx(3 / 4)


# ---- validation ---------------------------------------------------------------------

def test_rejects_bad_scores() -> None:
    truth = grid_truth(2, 2)
    bad = blank(4)
    bad["right"][0, 1] = np.nan
    with pytest.raises(ValueError, match="NaN"):
        evaluate(bad, truth)
    bad = blank(4)
    bad["below"][2, 2] = 0.0
    with pytest.raises(ValueError, match="diagonal"):
        evaluate(bad, truth)
    with pytest.raises(ValueError, match="keys"):
        evaluate({"right": blank(4)["right"]}, truth)


def test_pair_scores_take_best_of_four() -> None:
    scores = blank(2, 0.0)
    scores["below"][1, 0] = 5.0  # "piece 1 is above piece 0" relation for pair (0, 1)
    pairs = to_pair_scores(scores)
    assert pairs.score.tolist() == [5.0]
    assert pairs.winner_mask.tolist() == [1 << 3]  # b_above_a
