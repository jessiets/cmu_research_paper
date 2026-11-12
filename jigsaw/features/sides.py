"""Shared side extraction used by every method (spec B5).

1. Take the largest external contour of the alpha mask, traced on a 2x
   nearest-neighbor enlargement of the mask (D8).
2. Corners are the contour extrema of x + y (TL min, BR max) and x - y (TR max, BL min).
3. Split the contour into sides T, R, B, L, all ordered clockwise:
   T: TL -> TR, R: TR -> BR, B: BR -> BL, L: BL -> TL.
4. Resample each side to K points by arc length. [pilot]
5. A side is flat if its largest deviation from its corner-to-corner chord is
   below FLAT_FRACTION x pitch. [pilot] Flat sides have no neighbor.

Coordinates are continuous piece-crop coordinates: pixel (i, j) has its center
at (j + 0.5, i + 0.5), so they line up with the ground-truth corner positions.

Pitch is not given to methods (spec B4). It is derived as the median
corner-to-corner chord length over all sides of all extracted pieces.

Any failure is logged per piece. The piece stays in the puzzle with
``failed = True``, and methods must score all of its sides worst.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

from jigsaw.cvsetup import cv2
from jigsaw.features.pieces import PieceImage

K_POINTS = 96          # [pilot]
FLAT_FRACTION = 0.05   # [pilot]
SIDE_NAMES = ("T", "R", "B", "L")
CONTOUR_UPSAMPLE = 2  # D8: trace on a 2x mask so contours sit 0.25 px, not 0.5 px, inside the edge


@dataclass(frozen=True)
class RawSides:
    corners: np.ndarray            # (4, 2) TL, TR, BR, BL
    sides: tuple[np.ndarray, ...]  # 4 full-resolution contour polylines, clockwise


@dataclass
class SideSet:
    piece_ids: tuple[str, ...]
    points: np.ndarray        # (n, 4, K, 2) float64; zeros where failed
    corners: np.ndarray       # (n, 4, 2) float64; TL, TR, BR, BL; NaN where failed
    deviation: np.ndarray     # (n, 4) max distance from chord, px; NaN where failed
    flat: np.ndarray          # (n, 4) bool
    failed: np.ndarray        # (n,) bool
    pitch: float
    k: int
    flat_threshold: float
    upsample: int = 1
    errors: dict[str, str] = field(default_factory=dict)

    @property
    def usable(self) -> np.ndarray:
        """(n, 4) bool: sides that may have a neighbor (not failed, not flat)."""
        return ~self.failed[:, None] & ~self.flat


class ExtractionError(ValueError):
    pass


def _clockwise_contour(mask: np.ndarray, upsample: int = 1) -> np.ndarray:
    """Largest external contour in piece-crop coordinates.

    With ``upsample`` f > 1 the mask is enlarged f times (nearest neighbor)
    before tracing, so contour points sit 0.5 / f px inside the true boundary
    instead of 0.5 px.
    """
    image = mask.astype(np.uint8)
    if upsample > 1:
        image = np.kron(image, np.ones((upsample, upsample), dtype=np.uint8))
    contours, _ = cv2.findContours(image, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_NONE)
    if not contours:
        raise ExtractionError("no contour")
    contour = (max(contours, key=cv2.contourArea)[:, 0, :].astype(np.float64) + 0.5) / upsample
    if contour.shape[0] < 8:
        raise ExtractionError("contour too short")
    x, y = contour[:, 0], contour[:, 1]
    signed_area = 0.5 * np.sum(x * np.roll(y, -1) - np.roll(x, -1) * y)
    if signed_area < 0:  # positive = visually clockwise with y pointing down
        contour = contour[::-1]
    return contour


def _extreme_index(values: np.ndarray, use_max: bool) -> int:
    target = values.max() if use_max else values.min()
    tied = np.flatnonzero(values == target)
    return int(tied[len(tied) // 2])  # middle of a tied run, deterministic


def split_sides(mask: np.ndarray, upsample: int = 1) -> RawSides:
    contour = _clockwise_contour(mask, upsample)
    s = contour[:, 0] + contour[:, 1]
    d = contour[:, 0] - contour[:, 1]
    tl, br = _extreme_index(s, False), _extreme_index(s, True)
    tr, bl = _extreme_index(d, True), _extreme_index(d, False)
    count = contour.shape[0]
    contour = np.roll(contour, -tl, axis=0)
    tr, br, bl = (tr - tl) % count, (br - tl) % count, (bl - tl) % count
    if not 0 < tr < br < bl < count:
        raise ExtractionError("corners not in clockwise order")
    closed = np.vstack([contour, contour[:1]])
    bounds = (0, tr, br, bl, count)
    sides = tuple(closed[bounds[k]:bounds[k + 1] + 1] for k in range(4))
    corners = np.array([contour[0], contour[tr], contour[br], contour[bl]])
    return RawSides(corners, sides)


def resample(polyline: np.ndarray, k: int) -> np.ndarray:
    steps = np.linalg.norm(np.diff(polyline, axis=0), axis=1)
    arc = np.concatenate(([0.0], np.cumsum(steps)))
    if arc[-1] <= 0:
        raise ExtractionError("zero-length side")
    targets = np.linspace(0.0, arc[-1], k)
    return np.column_stack([np.interp(targets, arc, polyline[:, 0]),
                            np.interp(targets, arc, polyline[:, 1])])


def chord_deviation(polyline: np.ndarray) -> float:
    start, end = polyline[0], polyline[-1]
    chord = end - start
    length = np.hypot(*chord)
    if length == 0:
        raise ExtractionError("zero-length chord")
    rel = polyline - start
    return float(np.max(np.abs(chord[0] * rel[:, 1] - chord[1] * rel[:, 0]) / length))


def extract_sides(pieces: dict[str, PieceImage], k: int = K_POINTS,
                  flat_fraction: float = FLAT_FRACTION, upsample: int = CONTOUR_UPSAMPLE) -> SideSet:
    ids = tuple(sorted(pieces))
    n = len(ids)
    raw: dict[int, RawSides] = {}
    errors: dict[str, str] = {}
    for index, pid in enumerate(ids):
        try:
            raw[index] = split_sides(pieces[pid].mask, upsample)
        except ExtractionError as exc:
            errors[pid] = str(exc)

    chords = [np.hypot(*(side[-1] - side[0])) for r in raw.values() for side in r.sides]
    if not chords:
        raise ExtractionError("no piece could be extracted")
    pitch = float(np.median(chords))
    threshold = flat_fraction * pitch

    points = np.zeros((n, 4, k, 2))
    corners = np.full((n, 4, 2), np.nan)
    deviation = np.full((n, 4), np.nan)
    flat = np.zeros((n, 4), dtype=bool)
    failed = np.ones(n, dtype=bool)
    for index, r in raw.items():
        try:
            resampled = [resample(side, k) for side in r.sides]
            devs = [chord_deviation(side) for side in r.sides]
        except ExtractionError as exc:
            errors[ids[index]] = str(exc)
            continue
        points[index] = np.stack(resampled)
        corners[index] = r.corners
        deviation[index] = devs
        flat[index] = np.array(devs) < threshold
        failed[index] = False
    return SideSet(ids, points, corners, deviation, flat, failed, pitch, k, threshold,
                   upsample=upsample, errors=errors)
