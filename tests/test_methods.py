"""GEO and COLOR tests on synthetic data."""

from __future__ import annotations

from pathlib import Path

import numpy as np
import pytest

from jigsaw.evaluate.metrics import evaluate, load_truth
from jigsaw.features.boundary import inward_normals, side_samples
from jigsaw.features.pairwise import mean_l1, mean_squared
from jigsaw.features.pieces import PieceImage
from jigsaw.features.sides import extract_sides
from jigsaw.generate.instance import generate_image
from jigsaw.methods.base import PuzzleInput, finish, load_puzzle
from jigsaw.methods.registry import available, get_matcher
from jigsaw.relations import WORST, validate_relation_scores
from tests.test_generate import synthetic_source


def square_piece(color, size: int = 40, pad: int = 4, pid: str = "p0000") -> PieceImage:
    rgba = np.zeros((size + 2 * pad, size + 2 * pad, 4), dtype=np.uint8)
    rgba[pad:pad + size, pad:pad + size] = (*color, 255)
    return PieceImage(pid, rgba)


def test_pairwise_helpers_match_direct_computation() -> None:
    rng = np.random.default_rng(0)
    a, b = rng.random((70, 5, 3)), rng.random((70, 5, 3))  # more rows than one chunk
    l1 = mean_l1(a, b)
    sq = mean_squared(a, b)
    assert l1[3, 61] == pytest.approx(np.abs(a[3] - b[61]).sum(axis=1).mean())
    assert sq[69, 0] == pytest.approx(np.square(a[69] - b[0]).sum(axis=1).mean())


def test_inward_normals_point_inside_for_clockwise_sides() -> None:
    top = np.column_stack([np.linspace(0, 10, 11), np.zeros(11)])       # left to right
    right = np.column_stack([np.full(11, 10.0), np.linspace(0, 10, 11)])  # top to bottom
    assert np.allclose(inward_normals(top), [0, 1])
    assert np.allclose(inward_normals(right), [-1, 0])


def test_boundary_samples_never_mix_in_outside_pixels() -> None:
    piece = square_piece((200, 50, 50))
    sides = extract_sides({"p0000": piece})
    samples = side_samples(piece, sides.points[0], depth=1.0)
    lab_inside = samples[0, 0]
    assert np.allclose(samples, lab_inside, atol=1e-6)  # every sample is the inside color
    # Even at depth 0 (on the contour, next to transparent pixels) the color stays pure.
    assert np.allclose(side_samples(piece, sides.points[0], depth=0.0), lab_inside, atol=1e-6)


def test_finish_excludes_flat_failed_and_diagonal() -> None:
    n = 3
    scores = {"right": np.zeros((n, n)), "below": np.zeros((n, n))}
    usable = np.ones((n, 4), dtype=bool)
    usable[1, 1] = False  # piece 1's R side is flat
    result = finish(scores, usable)
    validate_relation_scores(dict(result.relation_scores), n)
    assert (result.relation_scores["right"][1] == WORST).all()
    assert result.relation_scores["right"][0, 2] == 0.0
    assert result.candidates_scored + result.candidates_excluded == 2 * n * (n - 1)


def test_color_identical_colors_score_best() -> None:
    pieces = {"p0000": square_piece((120, 80, 40), pid="p0000"),
              "p0001": square_piece((120, 80, 40), pid="p0001"),
              "p0002": square_piece((10, 200, 90), pid="p0002")}
    # Square pieces have only flat sides, so mark every side usable to test the measure itself.
    sides = extract_sides(pieces)
    sides.flat[:] = False
    puzzle = PuzzleInput("x", pieces, sides, None)
    matcher = get_matcher("COLOR")
    result = matcher.score(puzzle, matcher.extract(puzzle))
    right = result.relation_scores["right"]
    assert right[0, 1] == pytest.approx(0.0, abs=1e-9)
    assert right[0, 2] < right[0, 1]


@pytest.fixture(scope="module")
def synthetic_instance(tmp_path_factory: pytest.TempPathFactory) -> Path:
    base = tmp_path_factory.mktemp("methods")
    entries = generate_image(synthetic_source(base / "9999.png"), base / "inst", [(4, 5)], [0], [0], 64)
    return base / "inst" / entries[0]["instance_id"]


@pytest.mark.parametrize("name", ["GEO", "COLOR"])
def test_methods_find_neighbors_on_clean_synthetic_puzzle(name: str, synthetic_instance: Path) -> None:
    puzzle = load_puzzle(synthetic_instance / "public", synthetic_instance.name)
    matcher = get_matcher(name)
    features = matcher.extract(puzzle)
    result = matcher.score(puzzle, features)
    metrics = evaluate(dict(result.relation_scores), load_truth(synthetic_instance))
    assert metrics.top1 > 0.7  # far above chance (1/19) on a clean 4 x 5 cut
    assert features.nbytes > 0 and result.nbytes > 0
    assert not matcher.uses_reference


@pytest.mark.parametrize("name", ["GEO", "COLOR"])
def test_scores_are_deterministic(name: str, synthetic_instance: Path) -> None:
    runs = []
    for _ in range(2):
        puzzle = load_puzzle(synthetic_instance / "public", synthetic_instance.name)
        matcher = get_matcher(name)
        runs.append(matcher.score(puzzle, matcher.extract(puzzle)).relation_scores)
    for key in ("right", "below"):
        assert np.array_equal(runs[0][key], runs[1][key])


def test_registry_lists_built_methods() -> None:
    assert available() == ("COLOR", "GEO")
    with pytest.raises(KeyError, match="not implemented"):
        get_matcher("GRAD")
