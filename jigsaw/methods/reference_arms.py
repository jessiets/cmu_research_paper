"""Reference arms: REF-ONLY and the +R version of every method (spec A5, B7; D9).

Both read only the cached piece locations (``PuzzleInput.locations``), never
the reference image itself. A +R arm rank-fuses R with the method's own
evidence channels at equal weights: GEO+R fuses GEO and R, HYB-GC+R fuses
GEO, COLOR, and R in thirds, and HYB-FILTER+R fuses GRAD and R among the
relations GEO's filter kept only.
"""

from __future__ import annotations

from jigsaw.features.reference import reference_scores
from jigsaw.methods.base import Features, Matcher, PuzzleInput, ScoreResult, finish
from jigsaw.methods.hybrids import fuse_channels


def _r_channel(puzzle: PuzzleInput):
    if puzzle.locations is None:
        raise ValueError("this arm needs cached reference locations")
    return reference_scores(puzzle.locations, puzzle.sides.pitch)


def method_channels(matcher: Matcher, puzzle: PuzzleInput, features: Features):
    """A method's evidence channels and its kept-relation mask (None unless filtered)."""
    if hasattr(matcher, "channels"):
        return matcher.channels(puzzle, features)
    return {matcher.name: dict(matcher.score(puzzle, features).relation_scores)}, None


class RefOnlyMatcher:
    name = "REF-ONLY"
    uses_reference = True

    def extract(self, puzzle: PuzzleInput) -> Features:
        return Features({"locations": puzzle.locations})

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult:
        return finish(_r_channel(puzzle), puzzle.sides.usable)


class ReferenceArm:
    uses_reference = True

    def __init__(self, base: Matcher) -> None:
        self.base = base
        self.name = f"{base.name}+R"

    def extract(self, puzzle: PuzzleInput) -> Features:
        return self.base.extract(puzzle)

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult:
        channels, kept = method_channels(self.base, puzzle, features)
        channels = dict(channels, R=_r_channel(puzzle))
        result = finish(fuse_channels(channels, kept), puzzle.sides.usable)
        result.metadata.update(channels=list(channels), filtered=kept is not None)
        return result
