"""Reference channel R (spec A5, B7; D2, D10).

1. Resize each piece and its mask by the derived reference scale
   s = sqrt(reference area / total piece area). Methods never get the grid size.
2. Find the position minimizing the masked sum of squared differences over the
   reference (the masked TM_SQDIFF objective), computed with FFTs (D10):
       SSD(x, y) = sum M I^2  -  2 sum_c corr(I_c, M T_c)  +  sum M T^2
   The three spectra are combined before one inverse FFT, in float32, as
   OpenCV's matchTemplate does internally.
3. Convert the best position to piece coordinates: the piece's center (mean
   of its four extracted corners) placed in the reference, divided by s.
4. A relation's R score is minus the distance between the observed
   displacement and the expected one-pitch displacement.

Locations are computed once per instance and reference level, cached, and
reused by every +R arm and REF-ONLY (D2). Their cost is ``t_reference``.
"""

from __future__ import annotations

import numpy as np
from scipy import fft

from jigsaw.cvsetup import cv2
from jigsaw.features.pieces import PieceImage
from jigsaw.features.sides import SideSet
from jigsaw.relations import WORST

FFT_DTYPE = np.float32


def reference_scale(reference: np.ndarray, pieces: dict[str, PieceImage]) -> float:
    piece_area = sum(int(p.mask.sum()) for p in pieces.values())
    return float(np.sqrt(reference.shape[0] * reference.shape[1] / piece_area))


def piece_centers(pieces: dict[str, PieceImage], sides: SideSet) -> np.ndarray:
    """(n, 2) center of each piece in its own crop: mean of the 4 corners, or the mask's bounding-box center."""
    centers = np.empty((len(sides.piece_ids), 2))
    for index, pid in enumerate(sides.piece_ids):
        if not sides.failed[index]:
            centers[index] = sides.corners[index].mean(axis=0)
        else:
            ii, jj = np.nonzero(pieces[pid].mask)
            centers[index] = ((jj.min() + jj.max() + 1) / 2, (ii.min() + ii.max() + 1) / 2) if ii.size else (0, 0)
    return centers


def _resize(piece: PieceImage, scale: float) -> tuple[np.ndarray, np.ndarray]:
    h, w = piece.mask.shape
    size = (max(1, round(w * scale)), max(1, round(h * scale)))
    interp = cv2.INTER_AREA if scale < 1 else cv2.INTER_LINEAR
    rgb = cv2.resize(piece.rgb, size, interpolation=interp).astype(FFT_DTYPE)
    mask = cv2.resize(piece.mask.astype(np.float32), size, interpolation=interp) > 0.5
    return rgb, mask.astype(FFT_DTYPE)


def locate_pieces(pieces: dict[str, PieceImage], sides: SideSet, reference: np.ndarray) -> dict:
    """Best masked-SSD position of every piece. Returns locations in piece pixel units."""
    scale = reference_scale(reference, pieces)
    centers = piece_centers(pieces, sides)
    ref = reference.astype(FFT_DTYPE)
    height, width = ref.shape[:2]
    templates = [_resize(pieces[pid], scale) for pid in sides.piece_ids]
    h_max = max(t[1].shape[0] for t in templates)
    w_max = max(t[1].shape[1] for t in templates)
    shape = (fft.next_fast_len(height + h_max - 1, real=True), fft.next_fast_len(width + w_max - 1, real=True))
    ref_spectra = [fft.rfft2(ref[..., c], shape) for c in range(3)]
    ref_sq_spectrum = fft.rfft2((ref ** 2).sum(axis=2), shape)

    located = np.full((len(templates), 2), np.nan)
    match_xy = np.full((len(templates), 2), np.nan)
    for index, (rgb, mask) in enumerate(templates):
        h, w = mask.shape
        if h > height or w > width or not mask.any():
            continue
        spectrum = ref_sq_spectrum * fft.rfft2(mask[::-1, ::-1], shape)
        for c in range(3):
            spectrum -= 2 * ref_spectra[c] * fft.rfft2((mask * rgb[..., c])[::-1, ::-1], shape)
        ssd = fft.irfft2(spectrum, shape)[h - 1:height, w - 1:width]
        y, x = np.unravel_index(int(np.argmin(ssd)), ssd.shape)  # first minimum in scan order
        match_xy[index] = (x, y)
        located[index] = (np.array([x, y]) + scale * centers[index]) / scale
    return {"locations": located, "match_xy": match_xy, "scale": scale}


def reference_scores(locations: np.ndarray, pitch: float) -> dict[str, np.ndarray]:
    """R relation scores: minus the distance from the expected one-pitch displacement."""
    disp = locations[None, :, :] - locations[:, None, :]          # disp[a, b] = P_b - P_a
    right = -np.hypot(disp[..., 0] - pitch, disp[..., 1])
    below = -np.hypot(disp[..., 0], disp[..., 1] - pitch)
    out = {}
    for key, matrix in (("right", right), ("below", below)):
        matrix = np.where(np.isfinite(matrix), matrix, WORST)
        np.fill_diagonal(matrix, WORST)
        out[key] = matrix.astype(np.float64)
    return out
