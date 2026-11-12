"""GEO: shape evidence (spec B7).

Relation score = -(mean L1 distance between the two side profiles), where a
profile is the side's K resampled points minus its chord midpoint, and the
facing side's points are reversed (spec B6). GEO never reads piece pixels.
"""

from __future__ import annotations

import numpy as np

from jigsaw.features.pairwise import mean_l1
from jigsaw.methods.base import B, Features, L, PuzzleInput, R, ScoreResult, T, finish


def profiles(points: np.ndarray) -> np.ndarray:
    """(n, 4, K, 2) side points -> the same, each side minus its chord midpoint."""
    midpoints = (points[:, :, :1, :] + points[:, :, -1:, :]) / 2
    return points - midpoints


class GeoMatcher:
    name = "GEO"
    uses_reference = False

    def extract(self, puzzle: PuzzleInput) -> Features:
        prof = profiles(puzzle.sides.points)
        return Features({
            "right_side": np.ascontiguousarray(prof[:, R]),
            "left_side_reversed": np.ascontiguousarray(prof[:, L, ::-1]),
            "bottom_side": np.ascontiguousarray(prof[:, B]),
            "top_side_reversed": np.ascontiguousarray(prof[:, T, ::-1]),
        })

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult:
        f = features.arrays
        scores = {
            "right": -mean_l1(f["right_side"], f["left_side_reversed"]),
            "below": -mean_l1(f["bottom_side"], f["top_side_reversed"]),
        }
        return finish(scores, puzzle.sides.usable)
