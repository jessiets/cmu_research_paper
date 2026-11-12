"""One-page pilot summary (spec A6, B10, B11 step 12).

Reads the gate reports, the pilot timing and memory results, and their run
logs, then writes ``reports/pilot_summary.md`` with:
- gate results G1-G10 with their evidence,
- the [pilot] values and whether they changed,
- measured pilot runtime and the projected main-run runtime (gate G9),
- peak memory, a pilot-only quality overview (not study results),
- paper-affecting changes and open items.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

from jigsaw.run.runner import reference_results_path, runlog_path

GATES = Path("results/gates")
PILOT_IMAGES, MAIN_IMAGES = 3, 20
PILOT_VALUES = [
    ("K (side resampling points)", "96", "spec B5"),
    ("Flat-side threshold", "0.05 x pitch", "spec B5"),
    ("HYB-FILTER candidates per side", "10", "spec B7"),
    ("Timing repetitions", "5", "spec B9"),
    ("Degraded reference", "blur 2 px, 0.5x, JPEG 40, gain 0.9, +15", "spec A5"),
    ("uniform_fraction block / std limit", "16 px / 4", "spec B10"),
]


def load(name: str) -> dict | None:
    path = GATES / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else None


def read_rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def verdict(flag) -> str:
    return "—" if flag is None else ("PASS" if flag else "**FAIL**")


def gate_lines(g8_pass, g9_text) -> list[str]:
    g13 = load("step11_g1_g3_all.json") or load("step2_g1_g3.json")
    g3s = load("step5_g3_scores.json")
    g4, g5, g6, g7, g10 = (load("step6_g4.json"), load("step3_g5.json"), load("step4_g6.json"),
                           load("step9_g7.json"), load("step11_g10.json"))
    lines = ["| Gate | Result | Evidence |", "|---|---|---|"]
    if g13:
        lines.append(f"| G1 instance integrity | {verdict(g13['G1_pass'])} | {g13['instances_checked']} instances: exactly n connected pieces, no overlaps or gaps at wear 0, each interior edge once |")
        lines.append(f"| G2 ground truth | {verdict(g13['G2_pass'])} | true pairs = 2n − r − c, no diagonal pairs |")
        scores = f"; {g3s['comparisons']} score sets identical" if g3s else ""
        lines.append(f"| G3 reproducibility | {verdict(g13['G3_pass'] and (g3s is None or g3s['G3_scores_pass']))} | {g13['G3']['files_compared']} files byte-identical on regeneration{scores} |")
    if g4:
        lines.append(f"| G4 leakage | {verdict(g4['G4_pass'])} | {len(g4['instances'])} instances × {len(g4.get('arms_checked', g4.get('methods_checked', [])))} arms: identical without private/ and reference/, and under re-permuted IDs; canary blocked |")
    if g5:
        lines.append(f"| G5 evaluator | {verdict(g5['G5_pass'])} | oracle 1.0, reversed oracle at base rate, random AP matches its expectation ({g5['instances_checked']} instances) |")
    if g6:
        shares = [r["corners_within_2px"] for r in g6["instances"].values() if r["condition"]["wear"] == 0]
        lines.append(f"| G6 side extraction | {verdict(g6['G6_pass'])} | wear 0: {min(shares):.3f}–{max(shares):.3f} of corners within 2 px; flat sides exact (D8: 2x contour) |")
    if g7:
        s = g7["mean_localized_share"]
        lines.append(f"| G7 reference | {verdict(g7['G7_pass'])} | localized share exact {s['exact']:.3f}, degraded {s['degraded']:.3f}; degraded below exact in {g7['instances_where_degraded_below_exact']}/{len(g7['instances'])} |")
    lines.append(f"| G8 measurement | {verdict(g8_pass)} | see the timing section (CV of t_total under 10%) |")
    lines.append(f"| G9 practicality | {g9_text} | projection below |")
    if g10:
        inc = [c["increase"] for c in g10["checks"]]
        result = verdict(g10["G10_pass"]) if g10["G10_pass"] else "PASS by user judgment (D15)"
        lines.append(f"| G10 complexity | {result} | uniform_fraction +{min(inc):.3f} to +{max(inc):.3f} at 50%; "
                     f"all mechanical checks pass; +{g10['min_increase']} absolute reading not met on every image (D15) |")
    return lines


def main() -> None:
    parser = argparse.ArgumentParser(description="Write reports/pilot_summary.md.")
    parser.add_argument("--timing", type=Path, default=Path("results/pilot_timing.csv"))
    parser.add_argument("--memory", type=Path, default=Path("results/pilot_memory.csv"))
    parser.add_argument("--budget-hours", type=float, help="main-run time budget (Q4); needed for G9")
    parser.add_argument("--out", type=Path, default=Path("reports/pilot_summary.md"))
    args = parser.parse_args()

    timing = [r for r in read_rows(args.timing) if r["status"] == "ok"]
    memory = [r for r in read_rows(args.memory) if r["status"] == "ok"]
    failed = [r for r in read_rows(args.timing) + read_rows(args.memory) if r["status"] != "ok"]
    g8 = load("step10_g8.json")

    walls: dict[str, float] = defaultdict(float)
    for path in (runlog_path(args.timing), runlog_path(args.memory)):
        for row in read_rows(path):
            walls[row["kind"]] += float(row["wall_seconds"])
    pilot_hours = sum(walls.values()) / 3600
    reps = max((int(r["repetition"]) for r in timing), default=4) + 1
    main_hours = pilot_hours * MAIN_IMAGES / PILOT_IMAGES
    # Timing cost scales with repetitions; memory runs (1 per arm) do not.
    memory_hours = sum(float(r["wall_seconds"]) for r in read_rows(runlog_path(args.memory))) / 3600
    timing_hours = pilot_hours - memory_hours

    def projected(r: int) -> float:
        return (timing_hours * r / reps + memory_hours) * MAIN_IMAGES / PILOT_IMAGES

    if args.budget_hours is None:
        g9_text = "waiting on Q4 budget"
    else:
        g9_text = verdict(main_hours <= args.budget_hours) + f" (budget {args.budget_hours:g} h)"

    out = ["# Pilot summary", "",
           f"Pilot set: {PILOT_IMAGES} images (0269, 0251, 0731), 12 instance types each, 17 arms, {reps} timed repetitions "
           "plus separate memory runs. **Pilot numbers are checks and tuning evidence only; they are not study results.**", "",
           "## Gates", ""] + gate_lines(g8["G8_pass"] if g8 else None, g9_text)

    out += ["", "## [pilot] values", "", "| Value | Setting | Source | Changed in pilot? |", "|---|---|---|---|"]
    out += [f"| {name} | {value} | {src} | No |" for name, value, src in PILOT_VALUES]

    out += ["", "## Runtime (G8, G9)", ""]
    if g8:
        for grid, s in g8["arms_by_grid"].items():
            out.append(f"- t_total {grid}: median {s['median_t']:.2f} s, CV median {s['median_cv']:.3f}, max {s['max_cv']:.3f}, "
                       f"share under 10% {s['share_under_limit']:.2f}")
        for grid, s in g8["locate_by_grid"].items():
            out.append(f"- t_reference {grid}: median {s['median_t']:.2f} s, CV max {s['max_cv']:.3f}")
    out.append(f"- Pilot wall time: {pilot_hours:.1f} h ({timing_hours:.1f} h timing, {memory_hours:.1f} h memory)")
    out.append(f"- **Projected main run: {main_hours:.1f} h** at {reps} repetitions "
               f"(3 reps: {projected(3):.1f} h; 2 reps: {projected(2):.1f} h). Fewer repetitions is a B13 change needing approval.")

    if memory:
        peak = defaultdict(list)
        for r in memory:
            peak[(f"{r['rows']}x{r['cols']}", r["method"], r["reference"])].append(int(r["peak_rss_delta"]))
        big = sorted(((g, m, ref, max(v)) for (g, m, ref), v in peak.items() if g == "20x30"), key=lambda x: -x[3])[:5]
        out += ["", "## Memory (20 × 30, largest peak deltas)", ""]
        out += [f"- {m} ({ref}): {v / 2**20:.0f} MiB" for _, m, ref, v in big]

    if timing:
        ap = defaultdict(list)
        for r in timing:
            if r["repetition"] == "0":
                ap[(r["method"], r["reference"], r["complexity"], r["wear"])].append(float(r["ap"]))
        out += ["", "## Quality overview (pilot only, median AP across images and grids; not results)", "",
                "| Arm | c0 w0 | c0 w1 | c50 w0 | c50 w1 |", "|---|---|---|---|---|"]
        arms = sorted({(m, ref) for m, ref, _, _ in ap})
        for m, ref in arms:
            cells = [f"{np.median(ap[(m, ref, c, w)]):.3f}" if ap.get((m, ref, c, w)) else "—"
                     for c, w in (("0", "0"), ("0", "1"), ("50", "0"), ("50", "1"))]
            label = m if ref == "none" else f"{m} ({ref})" if m == "REF-ONLY" else f"{m}+R ({ref})"
            out.append(f"| {label} | " + " | ".join(cells) + " |")

    out += ["", "## Paper-affecting changes", "",
            "Decisions D1–D16 in `docs/decision_log.md`; required paper edits P1–P27 in `docs/paper_updates.md`.", "",
            "## Open items", ""]
    if failed:
        out.append(f"- {len(failed)} failed runs in the results files (kept with their errors).")
    out.append("- Q4: main-run time budget (needed for G9). Decide whether to lower timing repetitions (B13 change).")
    g10 = load("step11_g10.json")
    if g10 and not g10["G10_pass"]:
        low = sorted({c["image_id"] for c in g10["checks"] if not c["pass"]})
        out.append(f"- G10: the +{g10['min_increase']} absolute reading of \"clearly higher\" fails for image(s) "
                   f"{', '.join(low)} (already uniform at 0%). The user judged G10 met on the relative measure (D15); "
                   "per-instance strength is in results/pilot_uniform_fraction.csv.")
    out.append("- Step 13: the main run starts only with the user's explicit approval.")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(out) + "\n", encoding="utf-8")
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
