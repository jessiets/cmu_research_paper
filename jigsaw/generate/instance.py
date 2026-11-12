"""Instance export: pieces, ground truth, references, and manifest (spec B2 step 6, B4).

Layout per instance (spec B4)::

    <out>/<instance_id>/public/pieces/pXXXX.png     RGBA, tight crop with 2 px padding
    <out>/<instance_id>/public/piece_index.json     piece IDs only
    <out>/<instance_id>/reference/exact.png
    <out>/<instance_id>/reference/degraded.png
    <out>/<instance_id>/private/truth.json
    <out>/<instance_id>/private/manifest.json

Instance IDs are opaque hashes so that a directory name reveals no condition.
``<out>/index.json`` maps IDs to conditions for the runner and evaluator.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import scipy
from scipy import ndimage

from jigsaw.config import ExperimentConfig, load_config
from jigsaw.cvsetup import cv2
from jigsaw.generate.curves import Edge, cut_seed, generate_edges
from jigsaw.generate.cut import CutResult, build_label_map
from jigsaw.generate.overlay import apply_overlay
from jigsaw.generate.sources import center_crop, file_sha256, image_id_for, load_oriented
from jigsaw.generate.wear import apply_wear, wear_padding, wear_seed
from jigsaw.seeds import grid_label, seed_hex, seed_int

GENERATOR_VERSION = "1"
PIECE_PADDING = 2
PNG_PARAMS = [cv2.IMWRITE_PNG_COMPRESSION, 6]
SIDES = ("T", "R", "B", "L")

# Degraded reference, spec A5 [pilot].
DEGRADE_BLUR_SIGMA = 2.0
DEGRADE_SCALE = 0.5
DEGRADE_JPEG_QUALITY = 40
DEGRADE_GAIN = 0.9
DEGRADE_OFFSET = 15.0


@dataclass(frozen=True)
class Condition:
    image_id: str
    rows: int
    cols: int
    complexity: int
    wear: int

    @property
    def instance_id(self) -> str:
        return "i" + seed_hex("instance", self.image_id, grid_label(self.rows, self.cols),
                              self.complexity, self.wear)[:12]

    def to_json(self) -> dict:
        return {"image_id": self.image_id, "rows": self.rows, "cols": self.cols,
                "n": self.rows * self.cols, "complexity": self.complexity, "wear": self.wear}


def _json_bytes(data: object) -> bytes:
    return (json.dumps(data, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _png_bytes(array: np.ndarray) -> bytes:
    ok, encoded = cv2.imencode(".png", array, PNG_PARAMS)
    if not ok:
        raise RuntimeError("PNG encoding failed")
    return encoded.tobytes()


def _write(path: Path, data: bytes, hashes: dict[str, str], root: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    hashes[path.relative_to(root).as_posix()] = hashlib.sha256(data).hexdigest()


def piece_id_permutation(cond: Condition) -> np.ndarray:
    """perm[grid_index] = numeric piece ID. Seeded, so ID order reveals nothing."""
    seed = seed_int(cond.image_id, grid_label(cond.rows, cond.cols), cond.complexity, cond.wear,
                    "piece_ids")
    return np.random.default_rng(seed).permutation(cond.rows * cond.cols)


def degrade_reference(rgb: np.ndarray) -> np.ndarray:
    """Spec A5: blur sigma 2, 0.5x downscale, JPEG quality 40, gain 0.9, offset +15."""
    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
    blurred = cv2.GaussianBlur(bgr, (0, 0), sigmaX=DEGRADE_BLUR_SIGMA, sigmaY=DEGRADE_BLUR_SIGMA)
    small = cv2.resize(blurred, (round(bgr.shape[1] * DEGRADE_SCALE), round(bgr.shape[0] * DEGRADE_SCALE)),
                       interpolation=cv2.INTER_AREA)
    ok, jpeg = cv2.imencode(".jpg", small, [cv2.IMWRITE_JPEG_QUALITY, DEGRADE_JPEG_QUALITY])
    if not ok:
        raise RuntimeError("JPEG encoding failed")
    decoded = cv2.imdecode(jpeg, cv2.IMREAD_COLOR).astype(np.float64)
    adjusted = np.clip(np.rint(DEGRADE_GAIN * decoded + DEGRADE_OFFSET), 0, 255).astype(np.uint8)
    return cv2.cvtColor(adjusted, cv2.COLOR_BGR2RGB)


def software_versions() -> dict[str, str]:
    return {"python": platform.python_version(), "numpy": np.__version__,
            "scipy": scipy.__version__, "opencv": cv2.__version__}


def export_instance(out_root: Path, cond: Condition, image: np.ndarray, cut: CutResult,
                    edges: list[Edge], source_meta: dict, remove_only: bool = True,
                    overlay: dict | None = None) -> dict:
    """Write one instance. ``image`` is the cropped RGB image after any overlay."""
    rows, cols, pitch = cond.rows, cond.cols, cut.pitch
    n = rows * cols
    height, width = image.shape[:2]
    root = out_root / cond.instance_id
    if root.exists():
        shutil.rmtree(root)
    hashes: dict[str, str] = {}

    perm = piece_id_permutation(cond)
    ids = [f"p{perm[g]:04d}" for g in range(n)]
    pad = wear_padding(pitch)
    slices = ndimage.find_objects(cut.labels + 1)
    truth_pieces: dict[str, dict] = {}
    wear_totals = {"removed": 0, "grown": 0, "growth_suppressed": 0, "dropped_components": 0,
                   "original": 0}

    for g in range(n):
        r, c = divmod(g, cols)
        sy, sx = slices[g]
        y0, y1 = sy.start - pad, sy.stop + pad
        x0, x1 = sx.start - pad, sx.stop + pad
        window = np.full((y1 - y0, x1 - x0), -1, dtype=np.int32)
        vy0, vy1, vx0, vx1 = max(y0, 0), min(y1, height), max(x0, 0), min(x1, width)
        window[vy0 - y0:vy1 - y0, vx0 - x0:vx1 - x0] = cut.labels[vy0:vy1, vx0:vx1]
        mask = window == g
        worn, stats = apply_wear(mask, cond.wear, wear_seed(cond.image_id, rows, cols, cond.wear, g),
                                 pitch, remove_only=remove_only)
        worn &= window >= 0  # never outside the image
        for key in wear_totals:
            wear_totals[key] += stats[key]

        ii, jj = np.nonzero(worn)
        top = int(ii.min()) + y0 - PIECE_PADDING
        left = int(jj.min()) + x0 - PIECE_PADDING
        bottom = int(ii.max()) + y0 + PIECE_PADDING + 1
        right = int(jj.max()) + x0 + PIECE_PADDING + 1
        rgba = np.zeros((bottom - top, right - left, 4), dtype=np.uint8)
        local = np.zeros(rgba.shape[:2], dtype=bool)
        local[ii + y0 - top, jj + x0 - left] = True
        iy, ix = np.nonzero(local)
        rgba[iy, ix, :3] = image[iy + top, ix + left]
        rgba[iy, ix, 3] = 255
        bgra = cv2.cvtColor(rgba, cv2.COLOR_RGBA2BGRA)
        _write(root / "public" / "pieces" / f"{ids[g]}.png", _png_bytes(bgra), hashes, root)

        truth_pieces[ids[g]] = {
            "grid_index": g, "row": r, "col": c,
            "origin_xy": [left, top],
            "corners_xy": {
                "TL": [c * pitch - left, r * pitch - top],
                "TR": [(c + 1) * pitch - left, r * pitch - top],
                "BR": [(c + 1) * pitch - left, (r + 1) * pitch - top],
                "BL": [c * pitch - left, (r + 1) * pitch - top],
            },
            "border_sides": {"T": r == 0, "R": c == cols - 1, "B": r == rows - 1, "L": c == 0},
            "area_px": int(worn.sum()),
        }

    pairs = []
    for r in range(rows):
        for c in range(cols):
            g = r * cols + c
            if c + 1 < cols:
                pairs.append({"a": ids[g], "b": ids[g + 1], "relation": "b_right_of_a"})
            if r + 1 < rows:
                pairs.append({"a": ids[g], "b": ids[g + cols], "relation": "b_below_a"})

    _write(root / "public" / "piece_index.json",
           _json_bytes({"instance_id": cond.instance_id, "pieces": sorted(ids)}), hashes, root)
    _write(root / "reference" / "exact.png", _png_bytes(cv2.cvtColor(image, cv2.COLOR_RGB2BGR)),
           hashes, root)
    _write(root / "reference" / "degraded.png",
           _png_bytes(cv2.cvtColor(degrade_reference(image), cv2.COLOR_RGB2BGR)), hashes, root)
    truth = {"instance_id": cond.instance_id, "rows": rows, "cols": cols, "n": n, "pitch": pitch,
             "pieces": truth_pieces, "true_pairs": pairs, "true_pair_count": len(pairs)}
    _write(root / "private" / "truth.json", _json_bytes(truth), hashes, root)

    manifest = {
        "generator_version": GENERATOR_VERSION,
        "instance_id": cond.instance_id,
        "condition": cond.to_json(),
        "pitch": pitch,
        "source": source_meta,
        "overlay": overlay,
        "seeds": {
            "rule": "sha256 of '|'-joined values; first 8 bytes as an integer",
            "cut_seed": cut_seed(cond.image_id, rows, cols),
            "cut_seed_parts": [cond.image_id, grid_label(rows, cols)],
            "piece_id_seed_parts": [cond.image_id, grid_label(rows, cols), cond.complexity, cond.wear,
                                    "piece_ids"],
            "wear_seed_parts": [cond.image_id, grid_label(rows, cols), cond.wear, "piece_grid_index"],
        },
        "wear": {"level_px": cond.wear, "signed_distance": "pixel center to pixel boundary (half-pixel)",
                 "remove_only": remove_only, "padding_px": pad, "totals": wear_totals},
        "cut": {"raw_overlap_pixels": cut.raw_overlap_pixels, "raw_gap_pixels": cut.raw_gap_pixels,
                "island_reassignment_count": len(cut.island_reassignments),
                "island_reassignments": cut.island_reassignments},
        "curves": [edge.to_json() for edge in edges],
        "software": software_versions(),
        "hashes": hashes,
    }
    (root / "private" / "manifest.json").write_bytes(_json_bytes(manifest))
    return {"instance_id": cond.instance_id, **cond.to_json()}


def generate_image(source_path: Path, out_root: Path, grids, complexity_levels, wear_levels,
                   pitch: int = 64, remove_only: bool = True) -> list[dict]:
    image_id = image_id_for(source_path.name)
    oriented, rotated = load_oriented(source_path)
    source_sha = file_sha256(source_path)
    written = []
    for rows, cols in grids:
        crop, (top, left) = center_crop(oriented, rows * pitch, cols * pitch)
        edges = generate_edges(image_id, rows, cols, pitch)
        cut = build_label_map(edges, rows, cols, pitch)
        for complexity in complexity_levels:
            image, overlay = apply_overlay(crop, image_id, rows, cols, complexity)  # D11
            overlay = overlay if complexity else None  # complexity-0 manifests stay unchanged
            for wear in wear_levels:
                cond = Condition(image_id, rows, cols, complexity, wear)
                meta = {"file": source_path.name, "sha256": source_sha, "rotated_ccw_90": rotated,
                        "oriented_size_rows_cols": list(oriented.shape[:2]),
                        "crop": {"top": top, "left": left, "height": rows * pitch,
                                 "width": cols * pitch}}
                written.append(export_instance(out_root, cond, image, cut, edges, meta, remove_only, overlay))
    return written


def update_index(out_root: Path, entries: list[dict]) -> None:
    path = out_root / "index.json"
    index = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}
    for entry in entries:
        index[entry["instance_id"]] = {k: v for k, v in entry.items() if k != "instance_id"}
    path.write_bytes(_json_bytes(dict(sorted(index.items()))))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Generate puzzle instances for a config's images.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=Path("data/instances"))
    parser.add_argument("--complexity", type=int, nargs="*", help="subset of complexity levels")
    args = parser.parse_args(argv)
    config: ExperimentConfig = load_config(args.config)
    if not config.source_images:
        sys.exit("config has no source_images; run jigsaw.generate.sources first")
    levels = args.complexity if args.complexity is not None else config.complexity_levels
    entries = []
    for name in config.source_images:
        entries += generate_image(Path(config.source_dir) / name, args.out, config.grids, levels,
                                  config.wear_levels_px, config.pitch_px)
        print(f"{name}: {len(entries)} instances so far")
    update_index(args.out, entries)


if __name__ == "__main__":
    main()
