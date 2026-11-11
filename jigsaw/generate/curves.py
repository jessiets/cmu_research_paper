"""Interior edge curves built from Piecemaker's interlocking-nub curve code (spec B2 steps 1-2).

Each interior edge is four cubic Bezier segments produced by the vendored
``HorizontalPath`` / ``VerticalPath`` classes. Their SVG relative ``c`` commands
are parsed back to absolute control points, starting at the edge's first grid
corner, and the last endpoint is forced onto the second grid corner.

Coordinates are continuous image coordinates: x to the right, y down, grid
corner (r, c) at (c * pitch, r * pitch). Pixel (i, j) has its center at
(j + 0.5, i + 0.5).
"""

from __future__ import annotations

import random
from dataclasses import dataclass

import numpy as np

from jigsaw.generate.third_party.piecemaker.interlockingnubs import HorizontalPath, VerticalPath
from jigsaw.seeds import grid_label, seed_int

SAMPLES_PER_SEGMENT = 32


@dataclass(frozen=True)
class Edge:
    """One interior edge. ``kind`` is "h" (between rows r-1 and r) or "v" (between cols c-1 and c).

    For "h" edges, (r, c) is the start corner and the edge runs to corner (r, c + 1).
    For "v" edges, (r, c) is the start corner and the edge runs to corner (r + 1, c).
    """

    kind: str
    r: int
    c: int
    out: bool
    beziers: tuple[tuple[tuple[float, float], ...], ...]  # 4 segments x 4 control points

    @property
    def key(self) -> str:
        return f"{self.kind}{self.r}_{self.c}"

    def polyline(self) -> np.ndarray:
        """Dense samples from start corner to end corner, shape (N, 2), float64."""
        t = np.linspace(0.0, 1.0, SAMPLES_PER_SEGMENT + 1)[:, None]
        parts = []
        for index, (p0, p1, p2, p3) in enumerate(self.beziers):
            p0, p1, p2, p3 = (np.asarray(p, dtype=np.float64) for p in (p0, p1, p2, p3))
            u = 1.0 - t
            pts = (u ** 3) * p0 + 3 * (u ** 2) * t * p1 + 3 * u * (t ** 2) * p2 + (t ** 3) * p3
            parts.append(pts if index == 0 else pts[1:])
        line = np.vstack(parts)
        # Force exact endpoints (Bezier evaluation at t=0 and t=1 can round).
        line[0] = self.beziers[0][0]
        line[-1] = self.beziers[-1][3]
        return line

    def to_json(self) -> dict:
        return {"kind": self.kind, "r": self.r, "c": self.c, "out": self.out,
                "beziers": [[list(point) for point in seg] for seg in self.beziers]}


def cut_seed(image_id: str, rows: int, cols: int) -> int:
    return seed_int(image_id, grid_label(rows, cols))


def _parse_relative(rendered: str) -> list[tuple[tuple[float, float], ...]]:
    segments = []
    for line in rendered.splitlines():
        tokens = line.split()
        if not tokens:
            continue
        if tokens[0] != "c" or len(tokens) != 4:
            raise ValueError(f"unexpected path command: {line!r}")
        segments.append(tuple(tuple(float(v) for v in tok.split(",")) for tok in tokens[1:]))
    if len(segments) != 4:
        raise ValueError("expected four cubic segments")
    return segments


def _absolute(start: tuple[float, float], end: tuple[float, float],
              relative: list[tuple[tuple[float, float], ...]]) -> tuple:
    current = start
    out = []
    for c1, c2, p in relative:
        seg = (
            current,
            (current[0] + c1[0], current[1] + c1[1]),
            (current[0] + c2[0], current[1] + c2[1]),
            (current[0] + p[0], current[1] + p[1]),
        )
        out.append(seg)
        current = seg[3]
    last = out[-1]
    out[-1] = (last[0], last[1], last[2], (float(end[0]), float(end[1])))
    return tuple(out)


def generate_edges(image_id: str, rows: int, cols: int, pitch: int) -> list[Edge]:
    """All interior edges, seeded by ``cut_seed(image_id, grid)``.

    The vendored code draws from Python's module-level ``random``, so the global
    state is seeded here and restored afterwards. Edges are generated in a fixed
    order: horizontal edges row-major, then vertical edges row-major.
    """
    saved = random.getstate()
    random.seed(cut_seed(image_id, rows, cols))
    try:
        edges: list[Edge] = []
        for r in range(1, rows):
            for c in range(cols):
                path = HorizontalPath(width=float(pitch), height=float(pitch))
                start = (float(c * pitch), float(r * pitch))
                end = (float((c + 1) * pitch), float(r * pitch))
                edges.append(Edge("h", r, c, bool(path.out),
                                  _absolute(start, end, _parse_relative(path.render()))))
        for r in range(rows):
            for c in range(1, cols):
                path = VerticalPath(width=float(pitch), height=float(pitch))
                start = (float(c * pitch), float(r * pitch))
                end = (float(c * pitch), float((r + 1) * pitch))
                edges.append(Edge("v", r, c, bool(path.out),
                                  _absolute(start, end, _parse_relative(path.render()))))
    finally:
        random.setstate(saved)
    return edges
