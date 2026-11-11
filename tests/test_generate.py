"""Generator, ground truth, and export tests on synthetic images (no DIV2K needed)."""

from __future__ import annotations

import json
import random
import re
from pathlib import Path

import numpy as np
import pytest
from scipy import ndimage

from jigsaw.cvsetup import cv2
from jigsaw.generate.curves import generate_edges
from jigsaw.generate.cut import build_label_map, rasterize_polygon, repair_islands
from jigsaw.generate.gates import check_instance, compare_trees
from jigsaw.generate.instance import Condition, generate_image, piece_id_permutation
from jigsaw.generate.sources import check_eligibility, select_images
from jigsaw.generate.wear import apply_wear, wear_padding
from jigsaw.seeds import seed_hex, seed_int

PITCH = 64
FOUR = ndimage.generate_binary_structure(2, 1)


def synthetic_source(path: Path, height: int = 1356, width: int = 2040, seed: int = 0) -> Path:
    rng = np.random.default_rng(seed)
    yy, xx = np.mgrid[0:height, 0:width]
    image = np.stack([(xx * 255 // width), (yy * 255 // height), ((xx + yy) % 256)], axis=-1)
    image = np.clip(image + rng.integers(-20, 21, image.shape), 0, 255).astype(np.uint8)
    cv2.imwrite(str(path), image)
    return path


# ---- seeds and selection -------------------------------------------------------------

def test_seed_is_sha256_of_joined_values() -> None:
    assert seed_hex("0001", "6x9") == seed_hex("0001", "6x9")
    assert seed_hex("0001", "6x9") != seed_hex("0001", "6x10")
    assert seed_int("a", 1) == int(seed_hex("a", 1)[:16], 16)


def test_eligibility_allows_rotation() -> None:
    assert check_eligibility("a.png", 2040, 1356).eligible
    assert not check_eligibility("a.png", 2040, 1356).rotate
    portrait = check_eligibility("b.png", 1356, 2040)
    assert portrait.eligible and portrait.rotate
    assert not check_eligibility("c.png", 2040, 1272).eligible


def test_selection_is_seeded_and_order_independent() -> None:
    names = [f"{i:04d}.png" for i in range(1, 101)]
    first = select_images(names, count=23)
    shuffled = names[:]
    random.Random(1).shuffle(shuffled)
    assert select_images(shuffled, count=23) == first
    assert len(set(first)) == 23
    assert select_images(names, master_seed=1, count=23) != first


# ---- curves and label map ------------------------------------------------------------

def test_curves_are_deterministic_and_restore_global_random() -> None:
    random.seed(123)
    before = random.random()
    random.seed(123)
    a = generate_edges("img", 4, 5, PITCH)
    assert random.random() == before
    b = generate_edges("img", 4, 5, PITCH)
    assert [e.to_json() for e in a] == [e.to_json() for e in b]
    assert [e.to_json() for e in a] != [e.to_json() for e in generate_edges("img2", 4, 5, PITCH)]


def test_curve_endpoints_are_on_grid_corners() -> None:
    for edge in generate_edges("img", 4, 5, PITCH):
        line = edge.polyline()
        start = (edge.c * PITCH, edge.r * PITCH)
        end = ((edge.c + 1) * PITCH, edge.r * PITCH) if edge.kind == "h" else (edge.c * PITCH, (edge.r + 1) * PITCH)
        assert tuple(line[0]) == start and tuple(line[-1]) == end


@pytest.mark.parametrize("image_id", ["a", "b", "c"])
def test_label_map_partitions_image_into_connected_pieces(image_id: str) -> None:
    rows, cols = 6, 9
    cut = build_label_map(generate_edges(image_id, rows, cols, PITCH), rows, cols, PITCH)
    assert cut.raw_overlap_pixels == 0 and cut.raw_gap_pixels == 0
    assert cut.labels.min() == 0 and cut.labels.max() == rows * cols - 1
    for g in range(rows * cols):
        _, count = ndimage.label(cut.labels == g, structure=FOUR)
        assert count == 1


def test_rasterize_square_matches_pixel_centers() -> None:
    square = np.array([[2.0, 3.0], [10.0, 3.0], [10.0, 7.0], [2.0, 7.0]])
    top, left, mask = rasterize_polygon(square, 20, 20)
    full = np.zeros((20, 20), dtype=bool)
    full[top:top + mask.shape[0], left:left + mask.shape[1]] = mask
    expected = np.zeros((20, 20), dtype=bool)
    expected[3:7, 2:10] = True
    assert np.array_equal(full, expected)


def test_island_goes_to_longest_border_neighbor() -> None:
    labels = np.array([
        [0, 0, 0, 1, 1],
        [0, 0, 1, 1, 1],
        [2, 2, 0, 1, 1],   # the lone 0 at (2, 2) touches 1 twice and 2 once
        [2, 2, 2, 1, 1],
    ], dtype=np.int32)
    records = repair_islands(labels)
    assert labels[2, 2] == 1
    assert records == [{"from_piece": 0, "to_piece": 1, "pixels": 1, "shared_border": 2}]


# ---- wear ----------------------------------------------------------------------------

def test_wear_zero_is_identity_and_wear_one_removes_only() -> None:
    cut = build_label_map(generate_edges("w", 3, 3, PITCH), 3, 3, PITCH)
    pad = wear_padding(PITCH)
    mask = np.pad(cut.labels == 4, pad)
    same, stats = apply_wear(mask, 0, 1, PITCH)
    assert np.array_equal(same, mask) and stats["removed"] == 0
    worn, stats = apply_wear(mask, 1, 1, PITCH)
    assert not np.any(worn & ~mask)
    assert stats["removed"] > 0 and stats["grown"] == 0
    _, count = ndimage.label(worn, structure=FOUR)
    assert count == 1
    again, _ = apply_wear(mask, 1, 1, PITCH)
    assert np.array_equal(worn, again)


# ---- export, ground truth, reproducibility ------------------------------------------

@pytest.fixture(scope="module")
def generated(tmp_path_factory: pytest.TempPathFactory) -> tuple[Path, Path, list[dict]]:
    base = tmp_path_factory.mktemp("gen")
    source = synthetic_source(base / "9999.png")
    out = base / "instances"
    entries = generate_image(source, out, [(3, 4), (6, 9)], [0], [0, 1], PITCH)
    return source, out, entries


def test_g1_g2_pass_on_exported_files(generated) -> None:
    _, out, entries = generated
    assert len(entries) == 4
    for entry in entries:
        result = check_instance(out / entry["instance_id"])
        assert result["G1"]["pass"], result["G1"]
        assert result["G2"]["pass"], result["G2"]


def test_g3_regeneration_is_byte_identical(generated, tmp_path: Path) -> None:
    source, out, entries = generated
    generate_image(source, tmp_path, [(3, 4), (6, 9)], [0], [0, 1], PITCH)
    for entry in entries:
        diff = compare_trees(out / entry["instance_id"], tmp_path / entry["instance_id"])
        assert diff["files"] > 0
        assert not diff["differing"] and not diff["only_in_first"] and not diff["only_in_second"]


def test_public_files_do_not_leak_layout(generated) -> None:
    _, out, entries = generated
    for entry in entries:
        root = out / entry["instance_id"]
        names = [p.name for p in (root / "public" / "pieces").iterdir()]
        assert all(re.fullmatch(r"p\d{4}\.png", name) for name in names)
        index = json.loads((root / "public" / "piece_index.json").read_text(encoding="utf-8"))
        assert set(index) == {"instance_id", "pieces"}
        assert not re.search(r"\d+x\d+", entry["instance_id"])
        for path in (root / "public" / "pieces").iterdir():
            data = path.read_bytes()
            assert b"tEXt" not in data and b"iTXt" not in data and b"zTXt" not in data
            rgba = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
            assert not np.any(rgba[rgba[..., 3] == 0])


def test_piece_ids_are_permuted() -> None:
    perm = piece_id_permutation(Condition("x", 6, 9, 0, 0))
    assert sorted(perm.tolist()) == list(range(54))
    assert perm.tolist() != list(range(54))


def test_cuts_shared_across_wear_levels(generated) -> None:
    _, out, entries = generated
    by_grid: dict[tuple, list] = {}
    for entry in entries:
        manifest = json.loads((out / entry["instance_id"] / "private" / "manifest.json").read_text(encoding="utf-8"))
        by_grid.setdefault((entry["rows"], entry["cols"]), []).append(manifest["curves"])
    for curves in by_grid.values():
        assert all(c == curves[0] for c in curves)
