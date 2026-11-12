"""Inward-normal boundary sampling for the visual measures (spec B7).

Each side's K points are moved ``depth`` px along the inward normal and the
piece is sampled there with bilinear interpolation. Interpolation is
mask-normalized (values are weighted by alpha), so pixels outside the piece
never leak into a sample. A sample with no inside pixel among its four
bilinear neighbors takes the value of the nearest inside pixel.

Sides run clockwise in image coordinates (y down), so the inward normal of
tangent (tx, ty) is (-ty, tx).
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from jigsaw.cvsetup import cv2
from jigsaw.features.pieces import PieceImage


def to_lab(rgb: np.ndarray) -> np.ndarray:
    """uint8 RGB -> float64 CIELAB (L in 0..100)."""
    return cv2.cvtColor(rgb.astype(np.float32) / 255.0, cv2.COLOR_RGB2Lab).astype(np.float64)


def inward_normals(side: np.ndarray) -> np.ndarray:
    tangent = np.gradient(side, axis=0)
    length = np.linalg.norm(tangent, axis=1, keepdims=True)
    tangent = tangent / np.where(length > 0, length, 1.0)
    return np.column_stack([-tangent[:, 1], tangent[:, 0]])


def sample(values: np.ndarray, mask: np.ndarray, points: np.ndarray,
           nearest_inside: tuple[np.ndarray, np.ndarray]) -> np.ndarray:
    """Mask-normalized bilinear samples of ``values`` (H, W, C) at continuous points (M, 2)."""
    height, width = mask.shape
    # Continuous (x, y) -> array coordinates: pixel (i, j) has its center at (j + 0.5, i + 0.5).
    cx = np.clip(points[:, 0] - 0.5, 0, width - 1)
    cy = np.clip(points[:, 1] - 0.5, 0, height - 1)
    x0 = np.clip(np.floor(cx).astype(np.int64), 0, width - 2)
    y0 = np.clip(np.floor(cy).astype(np.int64), 0, height - 2)
    fx, fy = cx - x0, cy - y0
    weight_sum = np.zeros(points.shape[0])
    total = np.zeros((points.shape[0], values.shape[2]))
    for dy, dx, w in ((0, 0, (1 - fy) * (1 - fx)), (0, 1, (1 - fy) * fx),
                      (1, 0, fy * (1 - fx)), (1, 1, fy * fx)):
        yy, xx = y0 + dy, x0 + dx
        w = w * mask[yy, xx]
        weight_sum += w
        total += w[:, None] * values[yy, xx]
    out = np.empty_like(total)
    good = weight_sum > 1e-9
    out[good] = total[good] / weight_sum[good, None]
    if not good.all():
        ii, jj = nearest_inside
        yi = np.clip(np.rint(cy[~good]).astype(np.int64), 0, height - 1)
        xi = np.clip(np.rint(cx[~good]).astype(np.int64), 0, width - 1)
        out[~good] = values[ii[yi, xi], jj[yi, xi]]
    return out


def side_samples(piece: PieceImage, sides: np.ndarray, depth: float,
                 values: np.ndarray | None = None) -> np.ndarray:
    """(4, K, C) samples ``depth`` px inside each of a piece's four sides (default: CIELAB)."""
    mask = piece.mask
    if values is None:
        values = to_lab(piece.rgb)
    _, nearest = ndimage.distance_transform_edt(~mask, return_indices=True)
    out = np.empty((4, sides.shape[1], values.shape[2]))
    for s in range(4):
        pts = sides[s] + depth * inward_normals(sides[s])
        out[s] = sample(values, mask, pts, (nearest[0], nearest[1]))
    return out
