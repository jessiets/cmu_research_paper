"""Source image eligibility, seeded selection, loading, and center cropping (spec A4, D4)."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from jigsaw.cvsetup import cv2
from jigsaw.seeds import seed_hex

PITCH_PX = 64
# Largest grid is 20 x 30, so every eligible image must cover 1,280 x 1,920 (rows x cols).
REQUIRED_HEIGHT = 20 * PITCH_PX
REQUIRED_WIDTH = 30 * PITCH_PX
MASTER_SEED = 20261106
SELECTION_COUNT = 23
PILOT_COUNT = 3


@dataclass(frozen=True)
class Eligibility:
    filename: str
    width: int
    height: int
    eligible: bool
    rotate: bool  # rotate 90 degrees counterclockwise before cropping


def png_size(path: Path) -> tuple[int, int]:
    """Return (width, height) from a PNG header without decoding the image."""
    with path.open("rb") as file:
        header = file.read(24)
    if header[:8] != b"\x89PNG\r\n\x1a\n" or header[12:16] != b"IHDR":
        raise ValueError(f"{path} is not a PNG file")
    width, height = struct.unpack(">II", header[16:24])
    return width, height


def check_eligibility(filename: str, width: int, height: int) -> Eligibility:
    if height >= REQUIRED_HEIGHT and width >= REQUIRED_WIDTH:
        return Eligibility(filename, width, height, True, False)
    if width >= REQUIRED_HEIGHT and height >= REQUIRED_WIDTH:
        return Eligibility(filename, width, height, True, True)
    return Eligibility(filename, width, height, False, False)


def scan_sources(source_dir: Path) -> list[Eligibility]:
    files = sorted(path for path in source_dir.glob("*.png") if path.is_file())
    return [check_eligibility(path.name, *png_size(path)) for path in files]


def select_images(eligible_filenames: list[str], master_seed: int = MASTER_SEED,
                  count: int = SELECTION_COUNT) -> list[str]:
    """Seeded sample of sorted eligible filenames.

    Each filename gets the key SHA-256(master_seed | filename); the sample is the
    ``count`` filenames with the smallest keys, in key order. The first
    ``PILOT_COUNT`` drawn form the pilot set and the rest form the main set.
    """
    names = sorted(eligible_filenames)
    if len(names) < count:
        raise ValueError(f"only {len(names)} eligible images; {count} required")
    keyed = sorted(names, key=lambda name: seed_hex(master_seed, name))
    return keyed[:count]


def image_id_for(filename: str) -> str:
    return Path(filename).stem


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def load_oriented(path: Path) -> tuple[np.ndarray, bool]:
    """Load an RGB uint8 image, rotated so it covers 1,280 x 1,920 (rows x cols)."""
    bgr = cv2.imread(str(path), cv2.IMREAD_COLOR)
    if bgr is None:
        raise ValueError(f"could not read {path}")
    rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
    status = check_eligibility(path.name, rgb.shape[1], rgb.shape[0])
    if not status.eligible:
        raise ValueError(f"{path.name} is not eligible ({rgb.shape[1]} x {rgb.shape[0]})")
    if status.rotate:
        rgb = np.ascontiguousarray(np.rot90(rgb, k=1))
    return rgb, status.rotate


def center_crop(image: np.ndarray, height: int, width: int) -> tuple[np.ndarray, tuple[int, int]]:
    """Center crop; returns the crop and its (top, left) offset."""
    top = (image.shape[0] - height) // 2
    left = (image.shape[1] - width) // 2
    if top < 0 or left < 0:
        raise ValueError("image is smaller than the crop")
    return np.ascontiguousarray(image[top:top + height, left:left + width]), (top, left)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check eligibility and draw the seeded image sample.")
    parser.add_argument("--source-dir", type=Path, default=Path("data/sources"))
    parser.add_argument("--out", type=Path, default=Path("configs/image_selection.json"))
    args = parser.parse_args()

    scan = scan_sources(args.source_dir)
    eligible = [item.filename for item in scan if item.eligible]
    chosen = select_images(eligible)
    by_name = {item.filename: item for item in scan}
    record = {
        "rule": "sort eligible filenames; key = sha256(master_seed|filename); take the 23 smallest keys in key order; first 3 = pilot, rest = main",
        "master_seed": MASTER_SEED,
        "required_size_rows_cols": [REQUIRED_HEIGHT, REQUIRED_WIDTH],
        "scanned": len(scan),
        "eligible": len(eligible),
        "ineligible": [item.filename for item in scan if not item.eligible],
        "pilot": chosen[:PILOT_COUNT],
        "main": chosen[PILOT_COUNT:],
        "rotated": sorted(name for name in chosen if by_name[name].rotate),
    }
    args.out.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(f"scanned {len(scan)}, eligible {len(eligible)}")
    print("pilot:", ", ".join(record["pilot"]))
    print("main: ", ", ".join(record["main"]))
    print("rotated:", ", ".join(record["rotated"]) or "none")


if __name__ == "__main__":
    main()
