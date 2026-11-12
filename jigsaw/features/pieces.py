"""Public piece images, loaded from an instance's ``public/`` folder only."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from jigsaw.cvsetup import cv2


@dataclass(frozen=True)
class PieceImage:
    piece_id: str
    rgba: np.ndarray  # (H, W, 4) uint8, RGB order, alpha 0 outside the piece

    @property
    def rgb(self) -> np.ndarray:
        return self.rgba[..., :3]

    @property
    def mask(self) -> np.ndarray:
        return self.rgba[..., 3] > 0


def load_public_pieces(public_dir: Path) -> dict[str, PieceImage]:
    """Pieces in sorted ID order (the matrix index order used everywhere)."""
    public_dir = Path(public_dir)
    index = json.loads((public_dir / "piece_index.json").read_text(encoding="utf-8"))
    pieces = {}
    for pid in sorted(index["pieces"]):
        bgra = cv2.imread(str(public_dir / "pieces" / f"{pid}.png"), cv2.IMREAD_UNCHANGED)
        if bgra is None or bgra.ndim != 3 or bgra.shape[2] != 4:
            raise ValueError(f"piece {pid} is not an RGBA PNG")
        pieces[pid] = PieceImage(pid, cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA))
    return pieces
