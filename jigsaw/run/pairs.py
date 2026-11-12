"""Runner step: convert relation scores to pair scores (spec B6, B8).

The pair score of an unordered pair {i, j} (i < j) is the best of its four
relation scores. The winning relation is stored so direction can be scored
separately. When relations tie for best, all tied relations are recorded as a
bitmask over ``PAIR_RELATIONS``, so the evaluator can split credit evenly
instead of letting array order break the tie.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from jigsaw.relations import PAIR_RELATIONS, validate_relation_scores


@dataclass(frozen=True)
class PairScores:
    i: np.ndarray            # (N,) int, first piece index (i < j)
    j: np.ndarray            # (N,) int
    score: np.ndarray        # (N,) float64, best relation score
    winner_mask: np.ndarray  # (N,) uint8, bit k set if PAIR_RELATIONS[k] ties for best

    @property
    def size(self) -> int:
        return int(self.score.size)


def to_pair_scores(relation_scores: dict[str, np.ndarray]) -> PairScores:
    right, below = relation_scores["right"], relation_scores["below"]
    n = right.shape[0]
    validate_relation_scores(relation_scores, n)
    i, j = np.triu_indices(n, k=1)
    stacked = np.stack([right[i, j], right[j, i], below[i, j], below[j, i]])  # order = PAIR_RELATIONS
    best = stacked.max(axis=0)
    ties = stacked == best
    mask = np.zeros(best.shape, dtype=np.uint8)
    for k in range(len(PAIR_RELATIONS)):
        mask |= (ties[k].astype(np.uint8) << k)
    return PairScores(i.astype(np.int64), j.astype(np.int64), best.astype(np.float64), mask)
