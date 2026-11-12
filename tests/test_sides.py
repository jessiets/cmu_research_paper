"""Shared side extraction tests (spec B5)."""

from __future__ import annotations

import numpy as np
import pytest

from jigsaw.features.pieces import PieceImage
from jigsaw.features.sides import chord_deviation, extract_sides, resample, split_sides


def piece(mask: np.ndarray, pid: str = "p0000") -> PieceImage:
    rgba = np.zeros(mask.shape + (4,), dtype=np.uint8)
    rgba[mask] = (100, 150, 200, 255)
    return PieceImage(pid, rgba)


def square(size: int = 64, pad: int = 2) -> np.ndarray:
    mask = np.zeros((size + 2 * pad, size + 2 * pad), dtype=bool)
    mask[pad:pad + size, pad:pad + size] = True
    return mask


@pytest.mark.parametrize("upsample", [1, 2])
def test_square_corners_and_clockwise_sides(upsample: int) -> None:
    raw = split_sides(square(), upsample)
    inset = 0.5 / upsample
    expected = np.array([[2, 2], [66, 2], [66, 66], [2, 66]], dtype=float)
    expected += np.array([[inset, inset], [-inset, inset], [-inset, -inset], [inset, -inset]])
    assert np.allclose(raw.corners, expected)
    top, right, bottom, left = raw.sides
    assert top[0, 1] == top[-1, 1] and top[-1, 0] > top[0, 0]       # T runs left to right
    assert right[-1, 1] > right[0, 1]                               # R runs top to bottom
    assert bottom[-1, 0] < bottom[0, 0]                             # B runs right to left
    assert left[-1, 1] < left[0, 1]                                 # L runs bottom to top
    assert np.allclose(top[-1], right[0]) and np.allclose(left[-1], top[0])


def test_nub_side_is_not_flat_and_straight_sides_are() -> None:
    mask = square(pad=20)
    mask[44:60, 84:96] = True  # a 12 px tab on the right side, smaller than the corners
    pieces = {"p0000": piece(mask), "p0001": piece(square(pad=20))}
    sides = extract_sides(pieces)
    assert sides.flat[0].tolist() == [True, False, True, True]
    assert sides.flat[1].all()
    assert sides.points.shape == (2, 4, 96, 2)


def test_resample_keeps_endpoints_and_even_spacing() -> None:
    line = np.array([[0.0, 0.0], [10.0, 0.0], [10.0, 5.0]])
    out = resample(line, 16)
    assert np.allclose(out[0], line[0]) and np.allclose(out[-1], line[-1])
    steps = np.linalg.norm(np.diff(out, axis=0), axis=1)
    assert np.allclose(steps, 15 / 15)


def test_chord_deviation() -> None:
    assert chord_deviation(np.array([[0.0, 0.0], [5.0, 3.0], [10.0, 0.0]])) == pytest.approx(3.0)


def test_failed_piece_is_logged_and_kept() -> None:
    empty = np.zeros((10, 10), dtype=bool)
    sides = extract_sides({"p0000": piece(square()), "p0001": piece(empty, "p0001")})
    assert sides.failed.tolist() == [False, True]
    assert "p0001" in sides.errors
    assert not sides.usable[1].any()
    assert np.isnan(sides.corners[1]).all()


def test_pitch_is_derived_from_side_lengths() -> None:
    sides = extract_sides({"p0000": piece(square(64)), "p0001": piece(square(64), "p0001")}, upsample=2)
    assert sides.pitch == pytest.approx(63.5)
