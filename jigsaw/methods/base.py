"""Method interface (spec B8).

Methods receive only public data: the piece images, the shared side
extraction, and a reference array when the arm calls for one. They return
relation scores in the layout of ``jigsaw.relations``; the runner turns these
into pair scores and the evaluator scores them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Protocol

import numpy as np

from jigsaw.features.pieces import PieceImage, load_public_pieces
from jigsaw.features.sides import SideSet, extract_sides
from jigsaw.relations import RELATION_KEYS, WORST

# Side indices in SideSet arrays.
T, R, B, L = 0, 1, 2, 3


@dataclass(frozen=True)
class PuzzleInput:
    instance_id: str
    pieces: Mapping[str, PieceImage]   # public data only, sorted ID order
    sides: SideSet                     # output of shared preprocessing
    reference: np.ndarray | None       # None in the reference-free arm
    # Cached piece locations in the reference (D2); set for +R arms and REF-ONLY only.
    locations: np.ndarray | None = None


@dataclass
class Features:
    arrays: dict[str, np.ndarray] = field(default_factory=dict)

    @property
    def nbytes(self) -> int:
        return int(sum(a.nbytes for a in self.arrays.values()))


@dataclass
class ScoreResult:
    relation_scores: Mapping[str, np.ndarray]  # higher is better; float64
    candidates_scored: int
    candidates_excluded: int
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def nbytes(self) -> int:
        return int(sum(a.nbytes for a in self.relation_scores.values()))


class Matcher(Protocol):
    name: str
    uses_reference: bool

    def extract(self, puzzle: PuzzleInput) -> Features: ...

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult: ...


def load_puzzle(public_dir: Path, instance_id: str, reference: np.ndarray | None = None) -> PuzzleInput:
    """Build the method input from ``public/`` only (the runner adds the reference)."""
    pieces = load_public_pieces(public_dir)
    return PuzzleInput(instance_id, pieces, extract_sides(pieces), reference)


def finish(scores: dict[str, np.ndarray], usable: np.ndarray, metadata: dict | None = None) -> ScoreResult:
    """Apply exclusions shared by all methods and count scored candidates.

    ``right[a, b]`` needs a's R side and b's L side usable; ``below[a, b]``
    needs a's B side and b's T side usable. The diagonal is always excluded.
    """
    allowed = {
        "right": usable[:, R][:, None] & usable[:, L][None, :],
        "below": usable[:, B][:, None] & usable[:, T][None, :],
    }
    scored = excluded = 0
    for key in RELATION_KEYS:
        matrix = scores[key]
        ok = allowed[key].copy()
        np.fill_diagonal(ok, False)
        matrix[~ok] = WORST
        n = matrix.shape[0]
        scored += int(ok.sum())
        excluded += n * (n - 1) - int(ok.sum())
    return ScoreResult(scores, scored, excluded, metadata or {})
