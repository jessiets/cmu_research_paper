"""Gates G1-G3 for build step 2, checked on exported instance files (spec B10).

G1  Instance integrity: exactly n connected pieces; at wear 0 the exported pieces
    tile the image with no overlaps or gaps; interior edges present once each.
G2  Ground truth: true pairs equal 2n - r - c, none diagonal.
G3  Reproducibility: regenerating with the same seeds gives byte-identical files.
    (The "identical scores" half of G3 needs methods and is checked from step 5.)
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
from scipy import ndimage

from jigsaw.config import load_config
from jigsaw.cvsetup import cv2
from jigsaw.generate.instance import generate_image

FOUR_CONNECTED = ndimage.generate_binary_structure(2, 1)


def _read_rgba(path: Path) -> np.ndarray:
    bgra = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    return cv2.cvtColor(bgra, cv2.COLOR_BGRA2RGBA)


def check_instance(root: Path) -> dict:
    truth = json.loads((root / "private" / "truth.json").read_text(encoding="utf-8"))
    manifest = json.loads((root / "private" / "manifest.json").read_text(encoding="utf-8"))
    index = json.loads((root / "public" / "piece_index.json").read_text(encoding="utf-8"))
    rows, cols, n, pitch = truth["rows"], truth["cols"], truth["n"], truth["pitch"]
    wear = manifest["condition"]["wear"]
    exact = cv2.cvtColor(cv2.imread(str(root / "reference" / "exact.png")), cv2.COLOR_BGR2RGB)
    height, width = exact.shape[:2]

    piece_files = sorted((root / "public" / "pieces").glob("*.png"))
    coverage = np.zeros((height, width), dtype=np.int32)
    disconnected, pixel_mismatch, nonzero_outside, out_of_image = [], 0, 0, 0
    for path in piece_files:
        pid = path.stem
        rgba = _read_rgba(path)
        alpha = rgba[..., 3] > 0
        _, components = ndimage.label(alpha, structure=FOUR_CONNECTED)
        if components != 1:
            disconnected.append(pid)
        nonzero_outside += int(np.count_nonzero(rgba[~alpha]))
        left, top = truth["pieces"][pid]["origin_xy"]
        ii, jj = np.nonzero(alpha)
        gy, gx = ii + top, jj + left
        inside = (gy >= 0) & (gy < height) & (gx >= 0) & (gx < width)
        out_of_image += int((~inside).sum())
        np.add.at(coverage, (gy[inside], gx[inside]), 1)
        pixel_mismatch += int(np.any(rgba[ii[inside], jj[inside], :3] != exact[gy[inside], gx[inside]],
                                     axis=1).sum())

    expected_edges = {f"h{r}_{c}" for r in range(1, rows) for c in range(cols)} | \
                     {f"v{r}_{c}" for r in range(rows) for c in range(1, cols)}
    curve_keys = [f"{e['kind']}{e['r']}_{e['c']}" for e in manifest["curves"]]

    pairs = truth["true_pairs"]
    pos = {pid: (p["row"], p["col"]) for pid, p in truth["pieces"].items()}
    diagonal = [p for p in pairs if abs(pos[p["a"]][0] - pos[p["b"]][0])
                + abs(pos[p["a"]][1] - pos[p["b"]][1]) != 1]
    unordered = {frozenset((p["a"], p["b"])) for p in pairs}
    grid_ids = {v: k for k, v in pos.items()}
    expected_pairs = {frozenset((grid_ids[(r, c)], grid_ids[(r, c + 1)]))
                      for r in range(rows) for c in range(cols - 1)} | \
                     {frozenset((grid_ids[(r, c)], grid_ids[(r + 1, c)]))
                      for r in range(rows - 1) for c in range(cols)}

    islands = manifest["cut"]["island_reassignments"]
    g1 = {
        "pieces": len(piece_files),
        "piece_index_matches_files": index["pieces"] == [p.stem for p in piece_files],
        "disconnected_pieces": disconnected,
        "overlap_pixels": int((coverage > 1).sum()),
        "gap_pixels": int((coverage == 0).sum()),
        "piece_pixels_differing_from_image": pixel_mismatch,
        "piece_pixels_outside_image": out_of_image,
        "nonzero_values_outside_alpha": nonzero_outside,
        "interior_edges": len(curve_keys),
        "interior_edges_expected": len(expected_edges),
        "edges_unique_and_complete": len(curve_keys) == len(set(curve_keys)) and set(curve_keys) == expected_edges,
        "raw_overlap_pixels_before_repair": manifest["cut"]["raw_overlap_pixels"],
        "raw_gap_pixels_before_repair": manifest["cut"]["raw_gap_pixels"],
        "islands_reassigned": len(islands),
        "largest_island_px": max((i["pixels"] for i in islands), default=0),
    }
    g1["pass"] = (
        g1["pieces"] == n and g1["piece_index_matches_files"] and not disconnected
        and g1["overlap_pixels"] == 0 and g1["piece_pixels_differing_from_image"] == 0
        and g1["piece_pixels_outside_image"] == 0 and g1["nonzero_values_outside_alpha"] == 0
        and g1["edges_unique_and_complete"]
        and (wear > 0 or g1["gap_pixels"] == 0)
    )
    if wear > 0:
        g1["worn_pixels_removed_fraction"] = round(g1["gap_pixels"] / (height * width), 4)

    g2 = {
        "true_pairs": len(pairs),
        "expected_2n_minus_r_minus_c": 2 * n - rows - cols,
        "diagonal_pairs": len(diagonal),
        "duplicates": len(pairs) - len(unordered),
        "matches_grid_adjacency": unordered == expected_pairs,
    }
    g2["pass"] = (g2["true_pairs"] == g2["expected_2n_minus_r_minus_c"] and not diagonal
                  and g2["duplicates"] == 0 and g2["matches_grid_adjacency"])
    return {"instance_id": root.name, "condition": manifest["condition"], "G1": g1, "G2": g2,
            "wear_totals": manifest["wear"]["totals"]}


def compare_trees(a: Path, b: Path) -> dict:
    files_a = {p.relative_to(a).as_posix(): p for p in a.rglob("*") if p.is_file()}
    files_b = {p.relative_to(b).as_posix(): p for p in b.rglob("*") if p.is_file()}
    differing = [k for k in sorted(files_a.keys() & files_b.keys())
                 if files_a[k].read_bytes() != files_b[k].read_bytes()]
    return {"files": len(files_a), "only_in_first": sorted(files_a.keys() - files_b.keys()),
            "only_in_second": sorted(files_b.keys() - files_a.keys()), "differing": differing}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check gates G1-G3 on generated instances.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--report", type=Path, default=Path("results/gates/step2_g1_g3.json"))
    parser.add_argument("--complexity", type=int, nargs="*", default=[0])
    args = parser.parse_args()
    config = load_config(args.config)
    index = json.loads((args.instances / "index.json").read_text(encoding="utf-8"))
    wanted = {Path(name).stem for name in config.source_images}

    instances = [check_instance(args.instances / iid) for iid, cond in index.items()
                 if cond["image_id"] in wanted and cond["complexity"] in args.complexity]

    # G3: regenerate every image into a fresh directory and compare bytes.
    with tempfile.TemporaryDirectory() as tmp:
        regenerated = Path(tmp)
        for name in config.source_images:
            generate_image(Path(config.source_dir) / name, regenerated, config.grids, args.complexity,
                           config.wear_levels_px, config.pitch_px)
        g3_trees = {iid: compare_trees(args.instances / iid, regenerated / iid)
                    for iid in sorted(p.name for p in regenerated.iterdir())}
    g3_failures = {k: v for k, v in g3_trees.items()
                   if v["differing"] or v["only_in_first"] or v["only_in_second"]}

    # Cuts must be identical across wear (and complexity) levels of the same image and grid.
    curves: dict[tuple, set[str]] = {}
    for iid, cond in index.items():
        if cond["image_id"] in wanted and cond["complexity"] in args.complexity:
            manifest = json.loads((args.instances / iid / "private" / "manifest.json").read_text(encoding="utf-8"))
            key = (cond["image_id"], cond["rows"], cond["cols"])
            curves.setdefault(key, set()).add(json.dumps(manifest["curves"], sort_keys=True))
    cuts_shared = all(len(v) == 1 for v in curves.values())

    report = {
        "config": str(args.config),
        "instances_checked": len(instances),
        "G1_pass": all(i["G1"]["pass"] for i in instances),
        "G2_pass": all(i["G2"]["pass"] for i in instances),
        "G3_pass": not g3_failures and cuts_shared,
        "G3": {"instances_regenerated": len(g3_trees),
               "files_compared": sum(v["files"] for v in g3_trees.values()),
               "failures": g3_failures, "cuts_identical_across_wear": cuts_shared,
               "scores": "not yet checkable; verified once methods exist (step 5+)"},
        "instances": instances,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    print(f"instances checked: {len(instances)}")
    for gate in ("G1", "G2", "G3"):
        print(f"{gate}: {'PASS' if report[gate + '_pass'] else 'FAIL'}")
    print(f"G3: {report['G3']['files_compared']} files compared across "
          f"{report['G3']['instances_regenerated']} regenerated instances; "
          f"cuts identical across wear: {cuts_shared}")
    header = f"{'grid':>6} {'img':>5} {'wear':>4} {'pieces':>6} {'overlap':>7} {'gap':>6} {'islands':>7} {'maxisl':>6} {'pairs':>5}/{'exp':<5} {'G1':>4} {'G2':>4}"
    print(header)
    for i in sorted(instances, key=lambda x: (x["condition"]["n"], x["condition"]["image_id"], x["condition"]["wear"])):
        c, g1, g2 = i["condition"], i["G1"], i["G2"]
        print(f"{c['rows']}x{c['cols']:<3} {c['image_id']:>5} {c['wear']:>4} {g1['pieces']:>6} "
              f"{g1['overlap_pixels']:>7} {g1['gap_pixels']:>6} {g1['islands_reassigned']:>7} "
              f"{g1['largest_island_px']:>6} {g2['true_pairs']:>5}/{g2['expected_2n_minus_r_minus_c']:<5} "
              f"{'ok' if g1['pass'] else 'FAIL':>4} {'ok' if g2['pass'] else 'FAIL':>4}")


if __name__ == "__main__":
    main()
