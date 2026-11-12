"""Gate G6: shared side extraction (spec B10).

Pass condition at wear 0, for every instance: at least 99% of corners fall
within 2 px of the true corners, and flat sides match the true border sides
exactly. Wear 1 is reported, not gated. Ground truth is read here only to
check the extractor; the extractor itself sees public pieces only.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from jigsaw.config import load_config
from jigsaw.features.pieces import load_public_pieces
from jigsaw.features.sides import CONTOUR_UPSAMPLE, SIDE_NAMES, extract_sides

CORNER_NAMES = ("TL", "TR", "BR", "BL")
CORNER_TOLERANCE_PX = 2.0
REQUIRED_SHARE = 0.99


def check_instance(root: Path, upsample: int) -> dict:
    sides = extract_sides(load_public_pieces(root / "public"), upsample=upsample)
    truth = json.loads((root / "private" / "truth.json").read_text(encoding="utf-8"))
    errors, flat_mismatch, true_flat, found_flat = [], [], 0, 0
    for k, pid in enumerate(sides.piece_ids):
        piece = truth["pieces"][pid]
        if not sides.failed[k]:
            true = np.array([piece["corners_xy"][name] for name in CORNER_NAMES], dtype=np.float64)
            errors.extend(np.linalg.norm(sides.corners[k] - true, axis=1).tolist())
        for s, name in enumerate(SIDE_NAMES):
            is_border = piece["border_sides"][name]
            true_flat += is_border
            found_flat += bool(sides.flat[k, s])
            if bool(sides.flat[k, s]) != is_border:
                flat_mismatch.append({"piece": pid, "side": name, "border": is_border,
                                      "deviation_px": round(float(sides.deviation[k, s]), 3)})
    errors = np.array(errors)
    within = float(np.mean(errors <= CORNER_TOLERANCE_PX)) if errors.size else 0.0
    flat_dev = sides.deviation[sides.flat]
    other_dev = sides.deviation[~sides.flat & ~sides.failed[:, None]]
    return {
        "pieces": len(sides.piece_ids),
        "extraction_failures": int(sides.failed.sum()),
        "failure_reasons": sides.errors,
        "derived_pitch_px": sides.pitch,
        "flat_threshold_px": sides.flat_threshold,
        "corners_within_2px": within,
        "corner_error_median_px": float(np.median(errors)),
        "corner_error_p99_px": float(np.quantile(errors, 0.99)),
        "corner_error_max_px": float(errors.max()),
        "corners_over_10px": int(np.sum(errors > 10)),
        "true_flat_sides": true_flat,
        "detected_flat_sides": found_flat,
        "flat_mismatches": flat_mismatch,
        "flat_deviation_max_px": float(flat_dev.max()) if flat_dev.size else None,
        "non_flat_deviation_min_px": float(other_dev.min()) if other_dev.size else None,
        "pass": (within >= REQUIRED_SHARE and not flat_mismatch and not sides.failed.any()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check gate G6 on generated instances.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--upsample", type=int, default=CONTOUR_UPSAMPLE)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    report_path = args.report or Path(f"results/gates/step4_g6_upsample{args.upsample}.json")
    config = load_config(args.config)
    wanted = {Path(name).stem for name in config.source_images}
    index = json.loads((args.instances / "index.json").read_text(encoding="utf-8"))

    results = {}
    print(f"contour upsample: {args.upsample}")
    for iid, cond in sorted(index.items(), key=lambda kv: (kv[1]["wear"], kv[1]["n"], kv[1]["image_id"])):
        if cond["image_id"] not in wanted:
            continue
        r = check_instance(args.instances / iid, args.upsample)
        r["condition"] = cond
        results[iid] = r
        verdict = ("PASS" if r["pass"] else "FAIL") if cond["wear"] == 0 else "report"
        print(f"w{cond['wear']} {cond['rows']}x{cond['cols']:<3} {cond['image_id']}  "
              f"corners<=2px {r['corners_within_2px']:.4f}  median {r['corner_error_median_px']:.2f}  "
              f"max {r['corner_error_max_px']:.1f}  >10px {r['corners_over_10px']:>3}  "
              f"flat {r['detected_flat_sides']}/{r['true_flat_sides']} mismatches {len(r['flat_mismatches'])}  "
              f"failures {r['extraction_failures']}  {verdict}")

    wear0 = [r for r in results.values() if r["condition"]["wear"] == 0]
    report = {"contour_upsample": args.upsample,
              "G6_pass": bool(wear0) and all(r["pass"] for r in wear0),
              "criterion": "wear 0, every instance: >= 99% corners within 2 px; flat sides == border sides; no failures",
              "instances": results}
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"G6: {'PASS' if report['G6_pass'] else 'FAIL'} (wear 0, {len(wear0)} instances)")


if __name__ == "__main__":
    main()
