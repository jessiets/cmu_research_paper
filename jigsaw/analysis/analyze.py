"""Planned analysis, comparisons C1-C5 (spec A7; D16).

Inputs: a timing results CSV (quality metrics and timed repetitions), the
matching memory results CSV, and optionally the per-instance overlay-strength
CSV (D15). Output: ``<out>/`` with CSV tables, figures, and ``analysis.md``.

- Descriptive: every arm in every condition (grid x complexity x wear):
  median and IQR of AP, top-1, t_total (median over repetitions), and peak memory.
- C1-C3: paired per-image differences in AP and top-1 within each condition.
  Median difference, 95% percentile bootstrap CI (10,000 resamples of
  images), two-sided Wilcoxon signed-rank p-value, and Holm correction
  across all C1-C3 tests (D16).
    C1  COLOR - GEO, GRAD - GEO                       (no reference)
    C2  HYB-GC - better of (GEO, COLOR)               (better = higher median
        HYB-FILTER - better of (GEO, GRAD)             in that condition, D16)
    C3  M+R - M, for each method M and level exact, degraded
- C4: Kendall's tau between method orderings (by median AP and top-1) across
  reference levels, per condition. Descriptive.
- C5: median quality against median t_total and peak memory; Pareto front
  per condition. Descriptive.
Results are reported by condition; no interaction models (spec A7).

Pilot output is labeled "PILOT - not study results" throughout.
"""

from __future__ import annotations

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path

import numpy as np
from scipy.stats import kendalltau, wilcoxon

from jigsaw.seeds import seed_int

METHODS = ("GEO", "COLOR", "GRAD", "HYB-GC", "HYB-FILTER")
LEVELS = ("exact", "degraded")
METRICS = ("ap", "top1")
BOOTSTRAP = 10_000
ALPHA = 0.05


# ---- loading ----------------------------------------------------------------------

def arm_label(method: str, reference: str) -> str:
    if method == "REF-ONLY":
        return f"REF-ONLY ({reference})"
    return method if reference == "none" else f"{method}+R ({reference})"


def read_csv(path: Path | None) -> list[dict]:
    if path is None or not path.exists():
        return []
    with path.open(newline="", encoding="utf-8") as file:
        return list(csv.DictReader(file))


def condition_of(row: dict) -> tuple[str, int, int]:
    return (f"{row['rows']}x{row['cols']}", int(row["complexity"]), int(row["wear"]))


def condition_name(cond: tuple[str, int, int]) -> str:
    return f"{cond[0]} c{cond[1]} w{cond[2]}"


def grid_order(cond: tuple[str, int, int]) -> tuple:
    rows, cols = map(int, cond[0].split("x"))
    return (rows * cols, cond[1], cond[2])


def load_cells(timing: list[dict], memory: list[dict]) -> tuple[dict, list[str]]:
    """cells[(cond, arm, image)] = {"ap", "top1", "t_total", "peak"}; plus warnings."""
    warnings: list[str] = []
    quality: dict[tuple, dict] = {}
    times: dict[tuple, list[float]] = defaultdict(list)
    for row in timing:
        if row["status"] != "ok":
            continue
        key = (condition_of(row), arm_label(row["method"], row["reference"]), row["image_id"])
        metrics = {m: float(row[m]) for m in METRICS}
        if key in quality and quality[key] != metrics:
            warnings.append(f"quality differs across repetitions for {key}")
        quality.setdefault(key, metrics)
        times[key].append(float(row["t_total"]))
    peaks = {(condition_of(r), arm_label(r["method"], r["reference"]), r["image_id"]): float(r["peak_rss_delta"])
             for r in memory if r["status"] == "ok" and r["peak_rss_delta"] != ""}
    cells = {}
    for key, metrics in quality.items():
        cells[key] = dict(metrics, t_total=float(np.median(times[key])), reps=len(times[key]),
                          peak=peaks.get(key, float("nan")))
    failed = [r for r in timing + memory if r["status"] != "ok"]
    if failed:
        warnings.append(f"{len(failed)} failed runs excluded (kept in the results files)")
    return cells, warnings


# ---- statistics -------------------------------------------------------------------

def bootstrap_ci(diffs: np.ndarray, seed: int) -> tuple[float, float]:
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, diffs.size, size=(BOOTSTRAP, diffs.size))
    medians = np.median(diffs[idx], axis=1)
    return float(np.quantile(medians, 0.025)), float(np.quantile(medians, 0.975))


def wilcoxon_p(diffs: np.ndarray) -> float:
    if diffs.size == 0 or np.all(diffs == 0):
        return 1.0
    try:
        return float(wilcoxon(diffs, alternative="two-sided", zero_method="wilcox").pvalue)
    except ValueError:
        return float("nan")


def holm(pvalues: list[float]) -> list[float]:
    """Holm step-down adjusted p-values; NaN p-values stay NaN and are not counted."""
    finite = [(p, i) for i, p in enumerate(pvalues) if math.isfinite(p)]
    m = len(finite)
    adjusted = [float("nan")] * len(pvalues)
    running = 0.0
    for rank, (p, i) in enumerate(sorted(finite)):
        running = max(running, min(1.0, (m - rank) * p))
        adjusted[i] = running
    return adjusted


def paired(cells: dict, cond, arm_a: str, arm_b: str, metric: str) -> tuple[np.ndarray, list[str]]:
    images = sorted({k[2] for k in cells if k[0] == cond})
    both = [img for img in images if (cond, arm_a, img) in cells and (cond, arm_b, img) in cells]
    diffs = np.array([cells[(cond, arm_a, i)][metric] - cells[(cond, arm_b, i)][metric] for i in both])
    return diffs, both


def median_of(cells: dict, cond, arm: str, field: str) -> float:
    values = [v[field] for k, v in cells.items() if k[0] == cond and k[1] == arm and math.isfinite(v[field])]
    return float(np.median(values)) if values else float("nan")


def comparisons(cells: dict, conditions: list) -> list[dict]:
    tests = []

    def add(family, a, b, cond, metric, baseline=""):
        diffs, images = paired(cells, cond, a, b, metric)
        if diffs.size == 0:
            return
        seed = seed_int("bootstrap", family, a, b, condition_name(cond), metric)
        low, high = bootstrap_ci(diffs, seed)
        tests.append({"family": family, "comparison": f"{a} - {b}", "arm": a, "baseline_arm": b,
                      "baseline_rule": baseline, "grid": cond[0], "complexity": cond[1], "wear": cond[2],
                      "metric": metric, "n_images": diffs.size, "median_diff": float(np.median(diffs)),
                      "ci_low": low, "ci_high": high, "p_wilcoxon": wilcoxon_p(diffs)})

    for cond in conditions:
        for metric in METRICS:
            add("C1", "COLOR", "GEO", cond, metric)
            add("C1", "GRAD", "GEO", cond, metric)
            for hybrid, parts in (("HYB-GC", ("GEO", "COLOR")), ("HYB-FILTER", ("GEO", "GRAD"))):
                medians = {p: median_of(cells, cond, p, metric) for p in parts}
                better = max(parts, key=lambda p: (medians[p], -parts.index(p)))  # ties -> first listed
                add("C2", hybrid, better, cond, metric, f"better median {metric} of {' / '.join(parts)}")
            for method in METHODS:
                for level in LEVELS:
                    add("C3", arm_label(method, level), method, cond, metric)
    adjusted = holm([t["p_wilcoxon"] for t in tests])
    for t, p in zip(tests, adjusted):
        t["p_holm"] = p
        t["significant"] = bool(math.isfinite(p) and p < ALPHA)
    return tests


def orderings(cells: dict, conditions: list) -> list[dict]:
    rows = []
    for cond in conditions:
        for metric in METRICS:
            vectors = {}
            for level in ("none",) + LEVELS:
                vectors[level] = [median_of(cells, cond, arm_label(m, level), metric) for m in METHODS]
            for a, b in (("none", "exact"), ("none", "degraded"), ("exact", "degraded")):
                x, y = np.array(vectors[a]), np.array(vectors[b])
                ok = np.isfinite(x) & np.isfinite(y)
                tau = kendalltau(x[ok], y[ok]).statistic if ok.sum() >= 2 else float("nan")
                rows.append({"grid": cond[0], "complexity": cond[1], "wear": cond[2], "metric": metric,
                             "levels": f"{a} vs {b}", "kendall_tau": float(tau),
                             f"order_{a}": " > ".join(_order(vectors[a])),
                             f"order_{b}": " > ".join(_order(vectors[b]))})
    return rows


def _order(values: list[float]) -> list[str]:
    return [m for _, m in sorted(zip(values, METHODS), key=lambda t: (-t[0] if math.isfinite(t[0]) else math.inf, t[1]))]


def pareto(points: dict[str, tuple[float, ...]], higher_first: bool = True) -> set[str]:
    """Arms not dominated: no other arm is at least as good on every axis and strictly better on one.
    Axis 0 is quality (higher is better); the rest are costs (lower is better)."""
    front = set()
    for arm, p in points.items():
        if not all(math.isfinite(v) for v in p):
            continue
        dominated = False
        for other, q in points.items():
            if other == arm or not all(math.isfinite(v) for v in q):
                continue
            no_worse = q[0] >= p[0] and all(qi <= pi for qi, pi in zip(q[1:], p[1:]))
            better = q[0] > p[0] or any(qi < pi for qi, pi in zip(q[1:], p[1:]))
            if no_worse and better:
                dominated = True
                break
        if not dominated:
            front.add(arm)
    return front


def tradeoffs(cells: dict, conditions: list, arms: list[str]) -> list[dict]:
    rows = []
    for cond in conditions:
        med = {a: (median_of(cells, cond, a, "ap"), median_of(cells, cond, a, "t_total"),
                   median_of(cells, cond, a, "peak")) for a in arms}
        front_time = pareto({a: (v[0], v[1]) for a, v in med.items()})
        front_mem = pareto({a: (v[0], v[2]) for a, v in med.items()})
        front_all = pareto(med)
        for a, (ap, t, peak) in med.items():
            rows.append({"grid": cond[0], "complexity": cond[1], "wear": cond[2], "arm": a,
                         "median_ap": ap, "median_t_total": t, "median_peak_bytes": peak,
                         "front_ap_time": a in front_time, "front_ap_memory": a in front_mem,
                         "front_ap_time_memory": a in front_all})
    return rows


def descriptive(cells: dict, conditions: list, arms: list[str]) -> list[dict]:
    rows = []
    for cond in conditions:
        for arm in arms:
            vals = [v for k, v in cells.items() if k[0] == cond and k[1] == arm]
            if not vals:
                continue
            row = {"grid": cond[0], "complexity": cond[1], "wear": cond[2], "arm": arm, "n_images": len(vals)}
            for field in ("ap", "top1", "t_total", "peak"):
                x = np.array([v[field] for v in vals if math.isfinite(v[field])])
                q = np.quantile(x, [0.25, 0.5, 0.75]) if x.size else [float("nan")] * 3
                row.update({f"{field}_median": float(q[1]), f"{field}_q25": float(q[0]), f"{field}_q75": float(q[2])})
            rows.append(row)
    return rows


# ---- output -----------------------------------------------------------------------

def write_csv(path: Path, rows: list[dict]) -> None:
    if not rows:
        return
    fields = list(dict.fromkeys(k for r in rows for k in r))
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def fmt(x: float, digits: int = 3) -> str:
    return "—" if not math.isfinite(x) else f"{x:.{digits}f}"


def report(out: Path, label: str, n_images: int, conditions, arms, desc, tests, taus, trade, uniform,
           warnings, figures) -> None:
    lines = [f"# Analysis{' — ' + label if label else ''}", ""]
    if label:
        lines += [f"> **{label}.** Generated by `jigsaw.analysis.analyze`; numbers below come from the pilot "
                  "images, which are used for checks and tuning only.", ""]
    lines += [f"Images: {n_images}. Conditions: {len(conditions)} (grid × complexity × wear). Arms: {len(arms)}. "
              f"Tests C1–C3: {len(tests)} (Wilcoxon signed-rank, Holm-corrected; 95% bootstrap CI of the median "
              f"difference over {BOOTSTRAP:,} image resamples).", ""]
    for w in warnings:
        lines.append(f"- Note: {w}")
    if warnings:
        lines.append("")

    lines += ["## Median AP by arm and condition", "", "Full medians and IQRs for AP, top-1, t_total and peak "
              "memory: `descriptive.csv`.", ""]
    header = "| Arm | " + " | ".join(condition_name(c) for c in conditions) + " |"
    lines += [header, "|---|" + "---|" * len(conditions)]
    by = {(r["arm"], (r["grid"], r["complexity"], r["wear"])): r for r in desc}
    for arm in arms:
        lines.append(f"| {arm} | " + " | ".join(fmt(by[(arm, c)]["ap_median"]) if (arm, c) in by else "—"
                                              for c in conditions) + " |")

    for family, title in (("C1", "C1 — visual vs. geometric evidence"), ("C2", "C2 — hybrids vs. their better component"),
                          ("C3", "C3 — what the reference adds")):
        rows = [t for t in tests if t["family"] == family and t["metric"] == "ap"]
        sig = sum(t["significant"] for t in tests if t["family"] == family)
        lines += ["", f"## {title}", "",
                  f"AP shown; top-1 in `tests.csv`. Significant after Holm (p < {ALPHA}): {sig} of "
                  f"{sum(1 for t in tests if t['family'] == family)} tests in this family.", "",
                  "| Comparison | Condition | n | Median diff | 95% CI | p (Holm) |", "|---|---|---|---|---|---|"]
        for t in rows:
            cond = (t["grid"], t["complexity"], t["wear"])
            star = " *" if t["significant"] else ""
            lines.append(f"| {t['comparison']} | {condition_name(cond)} | {t['n_images']} | {t['median_diff']:+.3f}{star} "
                         f"| [{t['ci_low']:+.3f}, {t['ci_high']:+.3f}] | {fmt(t['p_holm'], 4)} |")

    lines += ["", "## C4 — does the method ordering change with the reference?", "",
              "Kendall's τ between the orderings of the five methods by median AP (1 = same order). Top-1 in `c4_orderings.csv`.", "",
              "| Condition | none vs exact | none vs degraded | exact vs degraded |", "|---|---|---|---|"]
    tau = {((r["grid"], r["complexity"], r["wear"]), r["levels"]): r["kendall_tau"] for r in taus if r["metric"] == "ap"}
    for c in conditions:
        lines.append(f"| {condition_name(c)} | " + " | ".join(fmt(tau.get((c, lv), float('nan')), 2)
                     for lv in ("none vs exact", "none vs degraded", "exact vs degraded")) + " |")

    lines += ["", "## C5 — quality against cost (Pareto fronts)", "",
              "Arms not beaten on both median AP and median t_total; full table with memory fronts in `c5_tradeoffs.csv`.", ""]
    for c in conditions:
        front = sorted(r["arm"] for r in trade if (r["grid"], r["complexity"], r["wear"]) == c and r["front_ap_time"])
        lines.append(f"- {condition_name(c)}: {', '.join(front) or '—'}")

    if uniform:
        lines += ["", "## Complexity manipulation strength (D15)", "",
                  "| Image | Grid | uniform_fraction 0% → 50% | Relative gain |", "|---|---|---|---|"]
        for r in uniform:
            if r["complexity"] != "0" and r["wear"] == "0":
                lines.append(f"| {r['image_id']} | {r['rows']}x{r['cols']} | {float(r['uniform_fraction_at_0']):.3f} → "
                             f"{float(r['uniform_fraction']):.3f} | {float(r['relative_gain']):.3f} |")

    if figures:
        lines += ["", "## Figures", ""] + [f"- `{f}`" for f in figures]
    (out / "analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the planned analysis (C1-C5).")
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--memory", type=Path)
    parser.add_argument("--uniform", type=Path, help="per-instance uniform_fraction CSV (D15)")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--label", default="", help='e.g. "PILOT - not study results"')
    parser.add_argument("--no-figures", action="store_true")
    args = parser.parse_args()

    timing, memory = read_csv(args.timing), read_csv(args.memory)
    cells, warnings = load_cells(timing, memory)
    if not cells:
        raise SystemExit("no successful runs found")
    conditions = sorted({k[0] for k in cells}, key=grid_order)
    arm_order = [arm_label(m, "none") for m in METHODS] + [arm_label(m, lv) for lv in LEVELS for m in METHODS] \
        + [arm_label("REF-ONLY", lv) for lv in LEVELS]
    arms = [a for a in arm_order if any(k[1] == a for k in cells)]
    n_images = len({k[2] for k in cells})

    desc = descriptive(cells, conditions, arms)
    tests = comparisons(cells, conditions)
    taus = orderings(cells, conditions)
    trade = tradeoffs(cells, conditions, arms)
    uniform = read_csv(args.uniform)

    args.out.mkdir(parents=True, exist_ok=True)
    write_csv(args.out / "descriptive.csv", desc)
    write_csv(args.out / "tests.csv", tests)
    write_csv(args.out / "c4_orderings.csv", taus)
    write_csv(args.out / "c5_tradeoffs.csv", trade)
    figures = []
    if not args.no_figures:
        from jigsaw.analysis.figures import draw_all

        figures = draw_all(args.out, tests, trade, conditions, args.label)
    report(args.out, args.label, n_images, conditions, arms, desc, tests, taus, trade, uniform, warnings, figures)
    print(f"wrote {args.out / 'analysis.md'}: {len(conditions)} conditions, {len(arms)} arms, {len(tests)} tests, "
          f"{sum(t['significant'] for t in tests)} significant after Holm")


if __name__ == "__main__":
    main()
