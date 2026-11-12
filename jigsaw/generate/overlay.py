"""Complexity overlay and uniform_fraction (spec B10; D11).

Overlay: one seeded, connected, solid-color region covering exactly
round(fraction x area) pixels of the cropped image.
- Seed: sha256(image_id | grid | complexity). Wear is not part of the seed, so
  the wear 0 and wear 1 instances share the same overlay.
- Shape: randomized region growing (Eden growth) from a seeded start pixel.
  Each step adds a uniformly chosen pixel from the region's 4-neighbor
  frontier, so the region is always connected, and growth stops at the exact
  pixel count.
- Color: the cropped image's mean color (per channel, rounded).

uniform_fraction: the share of pixels in non-overlapping 16 x 16 luma blocks
whose standard deviation is below 4 [pilot].
"""

from __future__ import annotations

import numpy as np

from jigsaw.cvsetup import cv2
from jigsaw.seeds import grid_label, seed_int

UNIFORM_BLOCK = 16       # [pilot]
UNIFORM_STD_LIMIT = 4.0  # [pilot]


def overlay_seed(image_id: str, rows: int, cols: int, complexity: int) -> int:
    return seed_int(image_id, grid_label(rows, cols), complexity)


def grow_region(height: int, width: int, target: int, seed: int) -> tuple[np.ndarray, tuple[int, int]]:
    """Connected boolean mask with exactly ``target`` pixels, grown from a seeded start pixel."""
    rng = np.random.default_rng(seed)
    area = height * width
    if not 0 <= target <= area:
        raise ValueError("target must be between 0 and the image area")
    region = np.zeros(area, dtype=bool)
    if target == 0:
        return region.reshape(height, width), (-1, -1)
    start = int(rng.integers(area))
    queued = np.zeros(area, dtype=bool)
    frontier = [start]
    queued[start] = True
    count = 0
    draws = rng.random(target)  # one uniform draw per added pixel
    for step in range(target):
        k = int(draws[step] * len(frontier))
        pixel = frontier[k]
        frontier[k] = frontier[-1]
        frontier.pop()
        region[pixel] = True
        count += 1
        y, x = divmod(pixel, width)
        for ny, nx in ((y - 1, x), (y + 1, x), (y, x - 1), (y, x + 1)):
            if 0 <= ny < height and 0 <= nx < width:
                q = ny * width + nx
                if not queued[q]:
                    queued[q] = True
                    frontier.append(q)
    return region.reshape(height, width), divmod(start, width)


def apply_overlay(image: np.ndarray, image_id: str, rows: int, cols: int, complexity: int) -> tuple[np.ndarray, dict]:
    """Return the overlaid image and its manifest record. Complexity 0 returns the image unchanged."""
    if complexity == 0:
        return image, {"complexity": 0}
    height, width = image.shape[:2]
    target = round(complexity / 100 * height * width)
    seed = overlay_seed(image_id, rows, cols, complexity)
    mask, start = grow_region(height, width, target, seed)
    color = np.rint(image.reshape(-1, 3).mean(axis=0)).astype(np.uint8)
    out = image.copy()
    out[mask] = color
    import hashlib

    return out, {
        "complexity": complexity, "fraction": complexity / 100, "pixels": int(mask.sum()),
        "target_pixels": target, "seed": seed, "seed_parts": [image_id, grid_label(rows, cols), complexity],
        "start_pixel_yx": [int(start[0]), int(start[1])], "color_rgb": color.tolist(),
        "mask_sha256": hashlib.sha256(np.packbits(mask).tobytes()).hexdigest(),
        "rule": "randomized region growing (4-neighbor frontier) to an exact pixel count",
    }


def uniform_fraction(image: np.ndarray, block: int = UNIFORM_BLOCK, limit: float = UNIFORM_STD_LIMIT) -> float:
    luma = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY).astype(np.float64)
    h, w = (luma.shape[0] // block) * block, (luma.shape[1] // block) * block
    blocks = luma[:h, :w].reshape(h // block, block, w // block, block).swapaxes(1, 2)
    stds = blocks.reshape(blocks.shape[0], blocks.shape[1], -1).std(axis=-1)
    covered = stds.size * block * block
    return float((stds < limit).sum() * block * block / covered)
