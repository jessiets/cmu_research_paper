"""Gate G8: measurement stability (spec B10).

Pass condition: the coefficient of variation (CV) of ``t_total`` across the
timed repetitions stays under 10% for every (instance, arm), or the
repetition count is raised. The location step's ``t_reference`` CV is
reported the same way. Reads the results written by ``runner --mode timing``.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from jigsaw.run.measure import coefficient_of_variation
from jigsaw.run.runner import reference_results_path

CV_LIMIT = 0.10


def group_cv(path: Path, key_fields: tuple[str, ...], value: str) -> dict[tuple, dict]:
    groups: dict[tuple, list[float]] = defaultdict(list)
    meta: dict[tuple, dict] = {}
    with path.open(newline="", encoding="utf-8") as file:
        for row in csv.DictReader(file):
            if row["status"] != "ok" or row.get("mode", "timing") not in ("timing", ""):
                continue
            key = tuple(row[f] for f in key_fields)
            groups[key].append(float(row[value]))
            meta[key] = {"grid": f"{row['rows']}x{row['cols']}", "wear": row["wear"], "image_id": row["image_id"]}
    return {k: dict(meta[k], reps=len(v), median=float(np.median(v)), cv=coefficient_of_variation(v))
            for k, v in groups.items()}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check gate G8 on timing results.")
    parser.add_argument("--results", type=Path, required=True, help="CSV written by runner --mode timing")
    parser.add_argument("--report", type=Path, default=Path("results/gates/step10_g8.json"))
    args = parser.parse_args()

    arms = group_cv(args.results, ("instance_id", "method", "reference"), "t_total")
    ref_path = reference_results_path(args.results)
    locate = group_cv(ref_path, ("instance_id", "reference"), "t_reference") if ref_path.exists() else {}

    def summarize(groups: dict) -> dict:
        by_grid: dict[str, list] = defaultdict(list)
        for g in groups.values():
            by_grid[g["grid"]].append(g)
        return {grid: {"groups": len(v), "max_cv": float(np.nanmax([g["cv"] for g in v])),
                       "median_cv": float(np.nanmedian([g["cv"] for g in v])),
                       "share_under_limit": float(np.mean([g["cv"] < CV_LIMIT for g in v])),
                       "median_t": float(np.median([g["median"] for g in v]))}
                for grid, v in sorted(by_grid.items())}

    over = [dict(g, instance_id=k[0], method=k[1], reference=k[2]) for k, g in arms.items()
            if not g["cv"] < CV_LIMIT]
    over_ref = [dict(g, instance_id=k[0], reference=k[1]) for k, g in locate.items() if not g["cv"] < CV_LIMIT]
    report = {"G8_pass": not over and not over_ref and bool(arms),
              "cv_limit": CV_LIMIT, "arm_groups": len(arms), "locate_groups": len(locate),
              "arms_by_grid": summarize(arms), "locate_by_grid": summarize(locate) if locate else {},
              "over_limit": sorted(over, key=lambda g: -g["cv"])[:50], "locate_over_limit": over_ref}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    for label, summary in (("t_total", report["arms_by_grid"]), ("t_reference", report["locate_by_grid"])):
        for grid, s in summary.items():
            print(f"{label:11s} {grid:>6}: {s['groups']:>3} groups, median t {s['median_t']:.3f}s, "
                  f"CV median {s['median_cv']:.3f} max {s['max_cv']:.3f}, under 10%: {s['share_under_limit']:.2f}")
    print(f"G8: {'PASS' if report['G8_pass'] else 'FAIL'} ({len(over)} arm groups and {len(over_ref)} "
          f"location groups at or over {CV_LIMIT:.0%})")


if __name__ == "__main__":
    main()
