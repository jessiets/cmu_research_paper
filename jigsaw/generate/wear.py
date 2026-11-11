"""Boundary wear (spec B3).

For wear level a > 0, in a padded crop around the piece:

    sd    = signed distance to the piece boundary (positive inside)
    f     = Gaussian-smoothed white noise, sigma = pitch / 10, scaled to unit std
    mask' = (sd - 1 + a * f) > 0

then keep only the largest 4-connected component. Level 0 leaves the mask unchanged.

Implementation choices (reported in the step 2 gate report):
- ``sd`` is measured from pixel centers to the boundary between pixels, so a
  boundary pixel is 0.5 px inside: sd = edt(inside) - 0.5 inside and
  -(edt(outside) - 0.5) outside.
- ``remove_only``: when True, mask' is intersected with the original mask, so
  wear can only remove material and never takes a neighbor's pixels.
"""

from __future__ import annotations

import numpy as np
from scipy import ndimage

from jigsaw.seeds import grid_label, seed_int

FOUR_CONNECTED = ndimage.generate_binary_structure(2, 1)


def wear_seed(image_id: str, rows: int, cols: int, wear: int, piece_grid_index: int) -> int:
    return seed_int(image_id, grid_label(rows, cols), wear, piece_grid_index)


def wear_padding(pitch: int) -> int:
    """Room for the noise filter (3 sigma) plus the material that can be removed."""
    return int(np.ceil(3 * pitch / 10)) + 2


def signed_distance(mask: np.ndarray) -> np.ndarray:
    inside = ndimage.distance_transform_edt(mask)
    outside = ndimage.distance_transform_edt(~mask)
    return np.where(mask, inside - 0.5, -(outside - 0.5))


def largest_component(mask: np.ndarray) -> np.ndarray:
    components, count = ndimage.label(mask, structure=FOUR_CONNECTED)
    if count <= 1:
        return mask.copy()
    sizes = np.bincount(components.ravel())[1:]
    return components == (int(np.argmax(sizes)) + 1)


def apply_wear(mask: np.ndarray, level: int, seed: int, pitch: int,
               remove_only: bool = True) -> tuple[np.ndarray, dict]:
    """Worn mask for a padded piece crop, plus pixel statistics.

    ``mask`` must have ``wear_padding`` pixels of background on every side.
    """
    original = int(mask.sum())
    if level == 0:
        return mask.copy(), {"removed": 0, "grown": 0, "growth_suppressed": 0,
                             "dropped_components": 0, "original": original}
    sd = signed_distance(mask)
    rng = np.random.default_rng(seed)
    noise = ndimage.gaussian_filter(rng.standard_normal(mask.shape), sigma=pitch / 10, mode="reflect")
    noise /= noise.std()
    worn = (sd - 1.0 + level * noise) > 0
    outside = worn & ~mask
    suppressed = int(outside.sum()) if remove_only else 0
    if remove_only:
        worn &= mask
    _, count = ndimage.label(worn, structure=FOUR_CONNECTED)
    kept = largest_component(worn)
    stats = {
        "removed": int((mask & ~kept).sum()),
        "grown": int((kept & ~mask).sum()),
        "growth_suppressed": suppressed,
        "dropped_components": max(count - 1, 0),
        "original": original,
    }
    return kept, stats
