"""Reference channel R, REF-ONLY, and +R arms (spec A5, B7; D9, D10)."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from jigsaw.cvsetup import cv2
from jigsaw.evaluate.metrics import evaluate, load_truth
from jigsaw.features.reference import locate_pieces, reference_scale, reference_scores
from jigsaw.generate.instance import generate_image
from jigsaw.methods.base import PuzzleInput, load_puzzle
from jigsaw.methods.registry import get_matcher
from jigsaw.relations import WORST
from tests.test_generate import synthetic_source


@pytest.fixture(scope="module")
def instance(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("reference")
    entries = generate_image(synthetic_source(base / "9999.png"), base / "inst", [(4, 5)], [0], [0], 64)
    return base / "inst" / entries[0]["instance_id"]


def load_reference(instance: Path, level: str) -> np.ndarray:
    bgr = cv2.imread(str(instance / "reference" / f"{level}.png"))
    return cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)


def test_reference_scores_hand_example() -> None:
    locations = np.array([[0.0, 0.0], [64.0, 0.0], [0.0, 70.0]])
    s = reference_scores(locations, 64.0)
    assert s["right"][0, 1] == 0.0                 # exactly one pitch to the right
    assert s["below"][0, 2] == pytest.approx(-6.0)  # 70 px below, expected 64
    assert s["right"][0, 0] == WORST and s["below"][1, 1] == WORST


def test_reference_scores_mark_unlocated_pieces_worst() -> None:
    s = reference_scores(np.array([[0.0, 0.0], [np.nan, np.nan]]), 64.0)
    assert s["right"][0, 1] == WORST and s["right"][1, 0] == WORST


@pytest.mark.parametrize(("level", "expected_scale"), [("exact", 1.0), ("degraded", 0.5)])
def test_scale_and_locations_on_clean_instance(instance: Path, level: str, expected_scale: float) -> None:
    puzzle = load_puzzle(instance / "public", instance.name)
    reference = load_reference(instance, level)
    assert reference_scale(reference, puzzle.pieces) == pytest.approx(expected_scale, rel=0.02)
    found = locate_pieces(puzzle.pieces, puzzle.sides, reference)
    assert np.isfinite(found["locations"]).all()


def test_ref_only_and_plus_r_arms(instance: Path) -> None:
    puzzle = load_puzzle(instance / "public", instance.name)
    found = locate_pieces(puzzle.pieces, puzzle.sides, load_reference(instance, "exact"))
    puzzle = PuzzleInput(puzzle.instance_id, puzzle.pieces, puzzle.sides, None, found["locations"])
    truth = load_truth(instance)

    ref_only = get_matcher("REF-ONLY", reference=True)
    m = evaluate(dict(ref_only.score(puzzle, ref_only.extract(puzzle)).relation_scores), truth)
    assert m.ap > 0.95 and m.top1 > 0.95  # an exact reference is close to decisive

    for name, channels in (("GEO", ["GEO", "R"]), ("HYB-GC", ["GEO", "COLOR", "R"]),
                           ("HYB-FILTER", ["GRAD", "R"])):
        arm = get_matcher(name, reference=True)
        assert arm.name == f"{name}+R" and arm.uses_reference
        result = arm.score(puzzle, arm.extract(puzzle))
        assert result.metadata["channels"] == channels
        assert result.metadata["filtered"] == (name == "HYB-FILTER")


def test_hyb_filter_plus_r_stays_inside_the_filter(instance: Path) -> None:
    puzzle = load_puzzle(instance / "public", instance.name)
    found = locate_pieces(puzzle.pieces, puzzle.sides, load_reference(instance, "exact"))
    puzzle = PuzzleInput(puzzle.instance_id, puzzle.pieces, puzzle.sides, None, found["locations"])
    plain = get_matcher("HYB-FILTER")
    with_r = get_matcher("HYB-FILTER", reference=True)
    a = plain.score(puzzle, plain.extract(puzzle)).relation_scores
    b = with_r.score(puzzle, with_r.extract(puzzle)).relation_scores
    for key in ("right", "below"):
        assert np.array_equal(np.isfinite(a[key]), np.isfinite(b[key]))  # R rescues nothing (D9)


def test_ref_only_needs_a_reference() -> None:
    with pytest.raises(ValueError, match="only where a reference exists"):
        get_matcher("REF-ONLY")
