"""COLOR: color evidence (spec B7).

Relation score = -(mean squared CIELAB difference between facing boundary
samples), following the form of Cho et al. (2010). Samples sit one pixel
inward along each side's normal; the facing side's samples are reversed so
sample k on one side faces sample k on the other (spec B6).
"""

from __future__ import annotations

import numpy as np

from jigsaw.features.boundary import side_samples
from jigsaw.features.pairwise import mean_squared
from jigsaw.methods.base import B, Features, L, PuzzleInput, R, ScoreResult, T, finish

SAMPLE_DEPTH_PX = 1.0


class ColorMatcher:
    name = "COLOR"
    uses_reference = False

    def extract(self, puzzle: PuzzleInput) -> Features:
        sides = puzzle.sides
        n, k = len(sides.piece_ids), sides.k
        lab = np.zeros((n, 4, k, 3))
        for index, pid in enumerate(sides.piece_ids):
            if not sides.failed[index]:
                lab[index] = side_samples(puzzle.pieces[pid], sides.points[index], SAMPLE_DEPTH_PX)
        return Features({
            "right_side": np.ascontiguousarray(lab[:, R]),
            "left_side_reversed": np.ascontiguousarray(lab[:, L, ::-1]),
            "bottom_side": np.ascontiguousarray(lab[:, B]),
            "top_side_reversed": np.ascontiguousarray(lab[:, T, ::-1]),
        })

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult:
        f = features.arrays
        scores = {
            "right": -mean_squared(f["right_side"], f["left_side_reversed"]),
            "below": -mean_squared(f["bottom_side"], f["top_side_reversed"]),
        }
        return finish(scores, puzzle.sides.usable)
