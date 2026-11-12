"""Gate G7: reference levels (spec B10).

Pass condition: exact and degraded references both run on every pilot
instance, and degraded localization falls below exact. A piece counts as
localized when its matched position in the reference is within pitch / 4 of
its true position. The comparison is made in reference coordinates and
converted back to image pixels, so a scale-estimate error alone does not
count as a localization error.

Also reported: the derived reference scale against the true scale, and
REF-ONLY quality at each level.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

from jigsaw.config import load_config
from jigsaw.evaluate.metrics import evaluate, load_truth
from jigsaw.features.pieces import load_public_pieces
from jigsaw.features.sides import extract_sides
from jigsaw.methods.base import PuzzleInput
from jigsaw.methods.registry import get_matcher
from jigsaw.run.runner import DEFAULT_CACHE, REFERENCE_FILES, cached_locations, plan
from jigsaw.cvsetup import cv2

LEVELS = ("exact", "degraded")


def localization(instance_dir: Path, level: str, cache_dir: Path) -> dict:
    path, meta = cached_locations(instance_dir, level, cache_dir)
    with np.load(path) as data:
        located = data["locations"]
    truth = json.loads((instance_dir / "private" / "truth.json").read_text(encoding="utf-8"))
    ref_width = cv2.imread(str(instance_dir / "reference" / REFERENCE_FILES[level])).shape[1]
    true_scale = ref_width / (truth["cols"] * truth["pitch"])
    est_scale = meta["scale"]
    errors = []
    for k, pid in enumerate(meta["piece_ids"]):
        p = truth["pieces"][pid]
        center = np.array(p["origin_xy"], float) + np.mean([p["corners_xy"][c] for c in ("TL", "TR", "BR", "BL")], axis=0)
        found_ref = located[k] * est_scale              # matched center, reference pixels
        errors.append(np.linalg.norm(found_ref - center * true_scale) / true_scale)
    errors = np.array(errors)
    tolerance = truth["pitch"] / 4

    pieces = load_public_pieces(instance_dir / "public")
    puzzle = PuzzleInput(instance_dir.name, pieces, extract_sides(pieces), None, located)
    matcher = get_matcher("REF-ONLY", reference=True)
    ref_only = evaluate(dict(matcher.score(puzzle, matcher.extract(puzzle)).relation_scores),
                        load_truth(instance_dir))
    return {"localized_share": float(np.mean(errors <= tolerance)),
            "median_error_px": float(np.median(errors)), "tolerance_px": tolerance,
            "estimated_scale": est_scale, "true_scale": true_scale,
            "scale_ratio": est_scale / true_scale, "t_reference": meta["t_reference"],
            "ref_only_ap": ref_only.ap, "ref_only_top1": ref_only.top1}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check gate G7 on generated instances.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    parser.add_argument("--report", type=Path, default=Path("results/gates/step9_g7.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    targets, _ = plan(config, args.instances, [0])

    results = {}
    for instance_dir, cond in targets:
        entry = {"condition": cond}
        for level in LEVELS:
            entry[level] = localization(instance_dir, level, args.cache)
        entry["degraded_below_exact"] = entry["degraded"]["localized_share"] < entry["exact"]["localized_share"]
        results[instance_dir.name] = entry
        e, d = entry["exact"], entry["degraded"]
        print(f"{cond['rows']}x{cond['cols']:<3} {cond['image_id']} w{cond['wear']}  "
              f"localized exact {e['localized_share']:.3f} degraded {d['localized_share']:.3f}  "
              f"scale ratio {e['scale_ratio']:.3f}/{d['scale_ratio']:.3f}  "
              f"REF-ONLY AP {e['ref_only_ap']:.3f}/{d['ref_only_ap']:.3f}  "
              f"t_ref {e['t_reference']:.1f}/{d['t_reference']:.1f}s", flush=True)

    def share(level):
        return float(np.mean([r[level]["localized_share"] for r in results.values()]))

    overall = {lvl: share(lvl) for lvl in LEVELS}
    report = {
        "G7_pass": overall["degraded"] < overall["exact"] and len(results) == len(targets),
        "criterion": "both levels run on every instance; mean localized share degraded < exact",
        "mean_localized_share": overall,
        "instances_where_degraded_below_exact": sum(r["degraded_below_exact"] for r in results.values()),
        "instances": results,
    }
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"G7: {'PASS' if report['G7_pass'] else 'FAIL'}  mean localized exact {overall['exact']:.3f}, "
          f"degraded {overall['degraded']:.3f}; degraded below exact in "
          f"{report['instances_where_degraded_below_exact']}/{len(results)} instances")


if __name__ == "__main__":
    main()
