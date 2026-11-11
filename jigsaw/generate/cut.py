"""Piece polygons, label-map rasterization, and stray-island repair (spec B2 steps 3-5, D5).

Each piece is a closed polygon from its four edges (border sides are straight).
Every polygon is rasterized on its own with an even-odd crossing test at pixel
centers. Shared edges use the identical sample array in both neighbors, and
each segment is put in a canonical order before intersecting, so a pixel center
gets the same answer from both sides of an edge. That makes the polygons
partition the image exactly unless a curve self-intersects; any pixel covered
zero or several times is counted, reported, and given to its nearest uniquely
covered neighbor.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np
from scipy import ndimage

from jigsaw.generate.curves import Edge

FOUR_CONNECTED = ndimage.generate_binary_structure(2, 1)


@dataclass
class CutResult:
    rows: int
    cols: int
    pitch: int
    labels: np.ndarray            # (H, W) int32, piece grid index r * cols + c
    raw_overlap_pixels: int       # covered by more than one polygon before repair
    raw_gap_pixels: int           # covered by no polygon before repair
    island_reassignments: list[dict] = field(default_factory=list)

    @property
    def n(self) -> int:
        return self.rows * self.cols


def _straight(a: tuple[float, float], b: tuple[float, float]) -> np.ndarray:
    return np.array([a, b], dtype=np.float64)


def piece_polygon(r: int, c: int, rows: int, cols: int, pitch: int,
                  lines: dict[str, np.ndarray]) -> np.ndarray:
    """Clockwise (in image coordinates) polygon: top, right, bottom, left."""
    x0, x1 = float(c * pitch), float((c + 1) * pitch)
    y0, y1 = float(r * pitch), float((r + 1) * pitch)
    top = _straight((x0, y0), (x1, y0)) if r == 0 else lines[f"h{r}_{c}"]
    right = _straight((x1, y0), (x1, y1)) if c == cols - 1 else lines[f"v{r}_{c + 1}"]
    bottom = _straight((x0, y1), (x1, y1)) if r == rows - 1 else lines[f"h{r + 1}_{c}"]
    left = _straight((x0, y0), (x0, y1)) if c == 0 else lines[f"v{r}_{c}"]
    return np.vstack([top[:-1], right[:-1], bottom[::-1][:-1], left[::-1][:-1]])


def rasterize_polygon(poly: np.ndarray, height: int, width: int) -> tuple[int, int, np.ndarray]:
    """Even-odd fill at pixel centers. Returns (top, left, mask) for the clipped bounding box."""
    xa, ya = poly[:, 0], poly[:, 1]
    xb, yb = np.roll(xa, -1), np.roll(ya, -1)
    swap = xa > xb
    x1 = np.where(swap, xb, xa)
    y1 = np.where(swap, yb, ya)
    x2 = np.where(swap, xa, xb)
    y2 = np.where(swap, ya, yb)
    keep = x1 < x2
    x1, y1, x2, y2 = x1[keep], y1[keep], x2[keep], y2[keep]

    # Columns j whose center j + 0.5 satisfies x1 <= j + 0.5 < x2.
    j_start = np.clip(np.ceil(x1 - 0.5).astype(np.int64), 0, width)
    j_end = np.clip(np.ceil(x2 - 0.5).astype(np.int64), 0, width)
    counts = np.maximum(j_end - j_start, 0)
    total = int(counts.sum())

    top = max(int(np.floor(poly[:, 1].min())), 0)
    bottom = min(int(np.ceil(poly[:, 1].max())), height)
    left = max(int(np.floor(poly[:, 0].min())), 0)
    right = min(int(np.ceil(poly[:, 0].max())), width)
    mask = np.zeros((bottom - top, right - left), dtype=bool)
    if total == 0 or mask.size == 0:
        return top, left, mask

    seg = np.repeat(np.arange(counts.size), counts)
    offsets = np.concatenate(([0], np.cumsum(counts)[:-1]))
    cols = j_start[seg] + (np.arange(total) - offsets[seg])
    px = cols + 0.5
    ys = y1[seg] + (px - x1[seg]) * (y2[seg] - y1[seg]) / (x2[seg] - x1[seg])

    order = np.lexsort((ys, cols))
    cols, ys = cols[order], ys[order]
    centers = np.arange(top, bottom) + 0.5
    unique_cols, starts = np.unique(cols, return_index=True)
    ends = np.append(starts[1:], cols.size)
    for col, s, e in zip(unique_cols, starts, ends):
        below = np.searchsorted(ys[s:e], centers, side="left")  # crossings with y < center
        mask[:, col - left] = (below % 2) == 1
    return top, left, mask


def build_label_map(edges: list[Edge], rows: int, cols: int, pitch: int) -> CutResult:
    height, width = rows * pitch, cols * pitch
    lines = {edge.key: edge.polyline() for edge in edges}
    coverage = np.zeros((height, width), dtype=np.uint8)
    labels = np.full((height, width), -1, dtype=np.int32)
    for r in range(rows):
        for c in range(cols):
            poly = piece_polygon(r, c, rows, cols, pitch, lines)
            top, left, mask = rasterize_polygon(poly, height, width)
            h, w = mask.shape
            coverage[top:top + h, left:left + w] += mask
            labels[top:top + h, left:left + w][mask] = r * cols + c

    overlap = int((coverage > 1).sum())
    gap = int((coverage == 0).sum())
    if overlap or gap:
        bad = coverage != 1
        labels[bad] = -1
        _, (ii, jj) = ndimage.distance_transform_edt(bad, return_indices=True)
        labels = labels[ii, jj]

    result = CutResult(rows, cols, pitch, labels, overlap, gap)
    result.island_reassignments = repair_islands(labels)
    return result


def repair_islands(labels: np.ndarray) -> list[dict]:
    """D5: give each disconnected stray island to the neighbor with the longest shared border.

    Connectivity is 4-neighbor. The largest component of each piece stays (ties:
    the first in scan order). Border length is the count of 4-neighbor pixel
    contacts; ties go to the smaller piece index. Modifies ``labels`` in place.
    """
    records: list[dict] = []
    changed = True
    while changed:
        changed = False
        slices = ndimage.find_objects(labels + 1)
        for index, region in enumerate(slices):
            if region is None:
                continue
            region = tuple(slice(max(s.start - 1, 0), s.stop + 1) for s in region)
            window = labels[region]
            components, count = ndimage.label(window == index, structure=FOUR_CONNECTED)
            if count <= 1:
                continue
            sizes = np.bincount(components.ravel())[1:]
            keep = int(np.argmax(sizes)) + 1
            for comp in range(1, count + 1):
                if comp == keep:
                    continue
                island = components == comp
                # Contacts: (island pixel, 4-neighbor of another piece) pairs, by neighbor label.
                neighbor_values = [
                    window[1:, :][island[:-1, :]], window[:-1, :][island[1:, :]],
                    window[:, 1:][island[:, :-1]], window[:, :-1][island[:, 1:]],
                ]
                values = np.concatenate(neighbor_values)
                values = values[(values != index) & (values >= 0)]
                if values.size == 0:
                    continue
                labels_found, counts_found = np.unique(values, return_counts=True)
                contacts = dict(zip(labels_found.tolist(), counts_found.tolist()))
                target = min(contacts, key=lambda k: (-contacts[k], k))
                window[island] = target
                records.append({"from_piece": index, "to_piece": target,
                                "pixels": int(island.sum()), "shared_border": contacts[target]})
                changed = True
                break
            if changed:
                break  # bounding boxes are stale after a reassignment; recompute
    return records


def adjacency_pairs(labels: np.ndarray) -> set[tuple[int, int]]:
    """Unordered pairs of pieces that share a 4-neighbor pixel contact (used only as a check)."""
    pairs = set()
    for a, b in ((labels[:, :-1], labels[:, 1:]), (labels[:-1, :], labels[1:, :])):
        diff = a != b
        lo = np.minimum(a[diff], b[diff])
        hi = np.maximum(a[diff], b[diff])
        pairs.update(zip(lo.tolist(), hi.tolist()))
    return pairs
