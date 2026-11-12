"""Evaluator (spec B9). The only module that reads an instance's ``private/`` folder.

Tie rules (spec B7):
- AP treats tied scores as one threshold: all tied pairs enter the ranking together.
- Top-1 counts a tie as 1 / (number of candidates tied for best).
- At the top-E cut-off, pairs tied across the cut-off get fractional credit:
  the remaining slots are shared evenly among them (the expected value under a
  random tie-break). Relation accuracy weights each true pair by that share.
- When relations tie for a pair's best score, a true pair's direction credit is
  1 / (tied relations) if the true relation is among them, else 0.

Sums of fractional credits use ``math.fsum`` (exactly rounded), so metrics do
not depend on the order of piece IDs at all, not even in the last bit (gate G4).

Top-1 side accuracy follows proposed default 4: each non-border side ranks its
candidates by that side's own relation score, not by the best-of-four pair score.
"""

from __future__ import annotations

import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from jigsaw.relations import FLIP, PAIR_RELATIONS, validate_relation_scores
from jigsaw.run.pairs import PairScores, to_pair_scores


@dataclass(frozen=True)
class Truth:
    piece_ids: tuple[str, ...]          # sorted, defines matrix index order
    rows: int
    cols: int
    pairs: tuple[tuple[int, int, str], ...]  # (i, j, relation) with i < j, relation from PAIR_RELATIONS

    @property
    def n(self) -> int:
        return len(self.piece_ids)


@dataclass(frozen=True)
class Metrics:
    ap: float
    top1: float
    f1_at_e: float
    accuracy_at_e: float
    relation_accuracy: float
    filter_recall: float
    base_rate: float               # = AP of a random ranking
    all_negative_accuracy: float
    candidates: int
    true_pairs: int
    non_border_sides: int

    def to_dict(self) -> dict:
        return asdict(self)


def load_truth(instance_dir: Path) -> Truth:
    data = json.loads((Path(instance_dir) / "private" / "truth.json").read_text(encoding="utf-8"))
    ids = tuple(sorted(data["pieces"]))
    return truth_from_dict(data, ids)


def truth_from_dict(data: dict, ids: tuple[str, ...]) -> Truth:
    index = {pid: k for k, pid in enumerate(ids)}
    pairs = []
    for pair in data["true_pairs"]:
        a, b, rel = index[pair["a"]], index[pair["b"]], pair["relation"]
        if rel not in ("b_right_of_a", "b_below_a"):
            raise ValueError(f"unexpected truth relation {rel}")
        if a > b:
            a, b, rel = b, a, FLIP[rel]
        pairs.append((a, b, rel))
    return Truth(ids, data["rows"], data["cols"], tuple(sorted(pairs)))


def average_precision(scores: np.ndarray, labels: np.ndarray) -> float:
    """Non-interpolated AP with tied scores treated as one threshold."""
    scores = np.asarray(scores, dtype=np.float64)
    labels = np.asarray(labels, dtype=bool)
    positives = int(labels.sum())
    if positives == 0:
        raise ValueError("AP needs at least one positive")
    if np.isnan(scores).any():
        raise ValueError("scores contain NaN")
    order = np.argsort(-scores, kind="stable")
    s, y = scores[order], labels[order]
    ends = np.append(np.flatnonzero(s[1:] != s[:-1]), s.size - 1)  # last index of each tie group
    tp = np.cumsum(y)[ends].astype(np.float64)
    precision = tp / (ends + 1)
    recall = tp / positives
    return float(np.sum(np.diff(np.concatenate(([0.0], recall))) * precision))


def top_e_weights(scores: np.ndarray, e: int) -> np.ndarray:
    """Share of each item inside the top ``e``, splitting the cut-off tie group evenly."""
    threshold = np.partition(scores, scores.size - e)[scores.size - e]  # e-th largest
    above = scores > threshold
    tied = scores == threshold
    weights = above.astype(np.float64)
    remaining = e - int(above.sum())
    weights[tied] = remaining / int(tied.sum())
    return weights


def _top1_credit(row: np.ndarray, partner: int, self_index: int) -> float:
    candidates = np.delete(row, self_index)
    target = row[partner]
    best = candidates.max()
    if target < best:
        return 0.0
    return 1.0 / int(np.count_nonzero(candidates == best))


def top1_side_accuracy(relation_scores: dict[str, np.ndarray], truth: Truth) -> tuple[float, int]:
    right, below = relation_scores["right"], relation_scores["below"]
    credits = []
    for i, j, rel in truth.pairs:
        # Canonical truth relation says how i and j sit; get the (left/upper, right/lower) pieces.
        if rel == "b_right_of_a":
            left, rgt = i, j
        elif rel == "b_left_of_a":
            left, rgt = j, i
        else:
            left, rgt = None, None
        if left is not None:
            credits.append(_top1_credit(right[left, :], rgt, left))   # left piece's R side
            credits.append(_top1_credit(right[:, rgt], left, rgt))    # right piece's L side
            continue
        upper, lower = (i, j) if rel == "b_below_a" else (j, i)
        credits.append(_top1_credit(below[upper, :], lower, upper))   # upper piece's B side
        credits.append(_top1_credit(below[:, lower], upper, lower))   # lower piece's T side
    return math.fsum(credits) / len(credits), len(credits)


def evaluate(relation_scores: dict[str, np.ndarray], truth: Truth,
             pairs: PairScores | None = None) -> Metrics:
    validate_relation_scores(relation_scores, truth.n)
    if pairs is None:
        pairs = to_pair_scores(relation_scores)
    n = truth.n
    candidates = pairs.size
    flat = pairs.i * n + pairs.j
    true_flat = np.array([i * n + j for i, j, _ in truth.pairs])
    position = np.searchsorted(flat, true_flat)  # pairs are in triu (row-major) order, so sorted
    labels = np.zeros(candidates, dtype=bool)
    labels[position] = True
    e = len(truth.pairs)

    ap = average_precision(pairs.score, labels)
    weights = top_e_weights(pairs.score, e)
    tp = math.fsum(weights[labels].tolist())
    f1 = tp / e  # precision = recall = F1 when exactly E pairs are predicted
    accuracy = (candidates - 2 * (e - tp)) / candidates

    rel_bits = np.array([1 << PAIR_RELATIONS.index(rel) for _, _, rel in truth.pairs], dtype=np.uint8)
    masks = pairs.winner_mask[position]
    tie_counts = np.array([bin(int(m)).count("1") for m in masks], dtype=np.float64)
    direction = np.where((masks & rel_bits) != 0, 1.0 / tie_counts, 0.0)
    true_weights = weights[position]
    weight_total = math.fsum(true_weights.tolist())
    relation_accuracy = (math.fsum((true_weights * direction).tolist()) / weight_total
                         if weight_total > 0 else float("nan"))

    right, below = relation_scores["right"], relation_scores["below"]
    scored = []
    for i, j, rel in truth.pairs:
        value = {"b_right_of_a": right[i, j], "b_left_of_a": right[j, i],
                 "b_below_a": below[i, j], "b_above_a": below[j, i]}[rel]
        scored.append(np.isfinite(value))
    top1, sides = top1_side_accuracy(relation_scores, truth)

    return Metrics(
        ap=ap, top1=top1, f1_at_e=f1, accuracy_at_e=accuracy,
        relation_accuracy=relation_accuracy, filter_recall=sum(scored) / len(scored),
        base_rate=e / candidates, all_negative_accuracy=(candidates - e) / candidates,
        candidates=candidates, true_pairs=e, non_border_sides=sides,
    )
