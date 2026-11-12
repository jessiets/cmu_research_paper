"""Complexity overlay (D11) and uniform_fraction tests."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage

from jigsaw.generate.gates import check_instance
from jigsaw.generate.instance import generate_image
from jigsaw.generate.overlay import apply_overlay, grow_region, overlay_seed, uniform_fraction
from tests.test_generate import synthetic_source


def test_region_is_connected_exact_and_seeded() -> None:
    a, start = grow_region(60, 80, 2400, seed=7)
    b, _ = grow_region(60, 80, 2400, seed=7)
    c, _ = grow_region(60, 80, 2400, seed=8)
    assert a.sum() == 2400 and np.array_equal(a, b) and not np.array_equal(a, c)
    assert ndimage.label(a, structure=ndimage.generate_binary_structure(2, 1))[1] == 1
    assert a[start]


def test_seed_ignores_wear() -> None:
    assert overlay_seed("0001", 6, 9, 50) == overlay_seed("0001", 6, 9, 50)
    assert overlay_seed("0001", 6, 9, 50) != overlay_seed("0001", 12, 18, 50)


def test_overlay_uses_mean_color_and_raises_uniform_fraction() -> None:
    rng = np.random.default_rng(0)
    image = rng.integers(0, 256, (128, 192, 3), dtype=np.uint8)
    out, record = apply_overlay(image, "x", 2, 3, 50)
    assert record["pixels"] == record["target_pixels"] == round(0.5 * 128 * 192)
    assert record["color_rgb"] == np.rint(image.reshape(-1, 3).mean(axis=0)).astype(int).tolist()
    assert uniform_fraction(out) > uniform_fraction(image) + 0.25
    same, zero = apply_overlay(image, "x", 2, 3, 0)
    assert same is image and zero == {"complexity": 0}


def test_uniform_fraction_extremes() -> None:
    assert uniform_fraction(np.full((64, 64, 3), 90, dtype=np.uint8)) == 1.0
    noise = np.random.default_rng(1).integers(0, 256, (64, 64, 3), dtype=np.uint8)
    assert uniform_fraction(noise) == 0.0


def test_overlay_instances_pass_g1_g2_and_share_overlay(tmp_path: Path) -> None:
    entries = generate_image(synthetic_source(tmp_path / "9999.png"), tmp_path / "inst", [(3, 4)], [50], [0, 1], 64)
    manifests = [json.loads((tmp_path / "inst" / e["instance_id"] / "private" / "manifest.json")
                            .read_text(encoding="utf-8")) for e in entries]
    assert manifests[0]["overlay"] == manifests[1]["overlay"] and manifests[0]["overlay"]["complexity"] == 50
    assert manifests[0]["curves"] == manifests[1]["curves"]
    for e in entries:
        result = check_instance(tmp_path / "inst" / e["instance_id"])
        assert result["G1"]["pass"] and result["G2"]["pass"]


def test_manipulation_report(tmp_path: Path) -> None:
    import csv
    import subprocess
    import sys

    from jigsaw.generate.instance import update_index

    sources = tmp_path / "sources"
    sources.mkdir()
    synthetic_source(sources / "9999.png")
    entries = generate_image(sources / "9999.png", tmp_path / "inst", [(3, 4)], [0, 50], [0, 1], 64)
    update_index(tmp_path / "inst", entries)
    root = Path(__file__).parents[1]
    text = (root / "configs" / "pilot.yaml").read_text(encoding="utf-8")
    text = text.replace("source_dir: data/sources", f"source_dir: {sources.as_posix()}")
    text = text.replace("  - 0269.png\n  - 0251.png\n  - 0731.png\n", "  - 9999.png\n  - 9998.png\n  - 9997.png\n")
    text = text.replace("  - [6, 9]\n  - [12, 18]\n  - [20, 30]\n", "  - [3, 4]\n")
    (tmp_path / "pilot.yaml").write_text(text, encoding="utf-8")
    out = tmp_path / "uf.csv"
    subprocess.run([sys.executable, "-m", "jigsaw.evaluate.manipulation", "--config", str(tmp_path / "pilot.yaml"),
                    "--instances", str(tmp_path / "inst"), "--out", str(out)], check=True, capture_output=True)
    with out.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4
    overlay = [r for r in rows if r["complexity"] == "50"]
    assert all(float(r["absolute_gain"]) > 0 and 0 < float(r["relative_gain"]) <= 1 for r in overlay)
