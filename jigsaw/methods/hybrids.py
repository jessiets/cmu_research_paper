"""Hybrid methods (spec B7).

HYB-GC      Rank fusion of GEO and COLOR.
HYB-FILTER  Keep GEO's top 10 candidates per side, then score only those with
            GRAD. A relation is kept if either of its two sides keeps it
            (D13); ties at rank 10 are kept. Everything else gets the worst
            score. GRAD is computed for kept relations only, so the runtime
            reflects the filter's savings.

Each hybrid exposes its evidence ``channels`` separately, so a reference arm
can add R as one more equal-weight channel (D9: HYB-GC+R fuses GEO, COLOR,
and R in thirds; HYB-FILTER+R fuses R only among the kept relations).
"""

from __future__ import annotations

import numpy as np

from jigsaw.features.color import ColorMatcher
from jigsaw.features.geometric import GeoMatcher
from jigsaw.features.gradient import GradMatcher, mgc_pairs
from jigsaw.methods.base import Features, PuzzleInput, ScoreResult, finish
from jigsaw.methods.fusion import rank_fuse
from jigsaw.relations import RELATION_KEYS, WORST

FILTER_TOP = 10  # [pilot]


def _merge(prefix_features: dict[str, Features]) -> Features:
    return Features({f"{prefix}/{key}": value for prefix, feats in prefix_features.items()
                     for key, value in feats.arrays.items()})


def _split(features: Features, prefix: str) -> Features:
    start = prefix + "/"
    return Features({k[len(start):]: v for k, v in features.arrays.items() if k.startswith(start)})


def top_k_mask(scores: np.ndarray, k: int) -> np.ndarray:
    """Relations in the top k of their row (first side) or their column (second side), ties kept."""
    finite = np.isfinite(scores)
    keep = np.zeros_like(finite)
    for axis in (1, 0):
        ordered = np.sort(np.where(finite, scores, -np.inf), axis=axis)
        counts = finite.sum(axis=axis)
        index = np.clip(scores.shape[axis] - np.minimum(counts, k), 0, scores.shape[axis] - 1)
        if axis == 1:
            threshold = ordered[np.arange(scores.shape[0]), index][:, None]
        else:
            threshold = ordered[index, np.arange(scores.shape[1])][None, :]
        keep |= finite & (scores >= threshold)
    return keep


def fuse_channels(channels: dict[str, dict[str, np.ndarray]],
                  kept: dict[str, np.ndarray] | None = None) -> dict[str, np.ndarray]:
    """Raw scores for a single channel; equal-weight rank fusion for several.

    With ``kept``, every channel is restricted to the kept relations before
    ranking, so fused ranks are computed among kept relations only.
    """
    out = {}
    for key in RELATION_KEYS:
        mats = [ch[key] if kept is None else np.where(kept[key], ch[key], WORST)
                for ch in channels.values()]
        fused = mats[0].copy() if len(mats) == 1 else rank_fuse(mats)
        if kept is not None:
            fused[~kept[key]] = WORST
        out[key] = fused
    return out


class HybGCMatcher:
    name = "HYB-GC"
    uses_reference = False

    def __init__(self) -> None:
        self.geo, self.color = GeoMatcher(), ColorMatcher()

    def extract(self, puzzle: PuzzleInput) -> Features:
        return _merge({"geo": self.geo.extract(puzzle), "color": self.color.extract(puzzle)})

    def channels(self, puzzle: PuzzleInput, features: Features):
        geo = self.geo.score(puzzle, _split(features, "geo")).relation_scores
        color = self.color.score(puzzle, _split(features, "color")).relation_scores
        return {"GEO": dict(geo), "COLOR": dict(color)}, None

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult:
        channels, kept = self.channels(puzzle, features)
        return finish(fuse_channels(channels, kept), puzzle.sides.usable)


class HybFilterMatcher:
    name = "HYB-FILTER"
    uses_reference = False

    def __init__(self, top: int = FILTER_TOP) -> None:
        self.top = top
        self.geo, self.grad = GeoMatcher(), GradMatcher()

    def extract(self, puzzle: PuzzleInput) -> Features:
        return _merge({"geo": self.geo.extract(puzzle), "grad": self.grad.extract(puzzle)})

    def channels(self, puzzle: PuzzleInput, features: Features):
        geo = self.geo.score(puzzle, _split(features, "geo")).relation_scores
        f = _split(features, "grad").arrays
        pairs = {"right": ("right", "left_rev"), "below": ("bottom", "top_rev")}
        kept, grad = {}, {}
        for key, (first, second) in pairs.items():
            kept[key] = top_k_mask(geo[key], self.top)
            a_idx, b_idx = np.nonzero(kept[key])
            matrix = np.full(geo[key].shape, WORST)
            matrix[a_idx, b_idx] = mgc_pairs(
                a_idx, b_idx, f[f"{first}_inner"], (f[f"{first}_mean"], f[f"{first}_inv_cov"]),
                f[f"{second}_inner"], (f[f"{second}_mean"], f[f"{second}_inv_cov"]))
            grad[key] = matrix
        return {"GRAD": grad}, kept

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult:
        channels, kept = self.channels(puzzle, features)
        result = finish(fuse_channels(channels, kept), puzzle.sides.usable)
        result.metadata.update(storage="filtered", filter_top=self.top,
                               relations_kept=int(sum(m.sum() for m in kept.values())))
        return result
