"""Planned-analysis tests (spec A7; D16) on fabricated results with known answers."""

from __future__ import annotations

import csv
import subprocess
import sys
from pathlib import Path

import numpy as np
import pytest

from jigsaw.analysis.analyze import (bootstrap_ci, comparisons, holm, load_cells, orderings, pareto,
                                     wilcoxon_p)
from jigsaw.run.runner import COLUMNS

METHODS = ("GEO", "COLOR", "GRAD", "HYB-GC", "HYB-FILTER")


def test_holm_hand_example() -> None:
    # p sorted: 0.01, 0.02, 0.04 with m = 3 -> 0.03, 0.04, 0.04 (monotone step-down)
    assert holm([0.04, 0.01, 0.02]) == pytest.approx([0.04, 0.03, 0.04])
    assert holm([0.5, float("nan")])[0] == 0.5 and np.isnan(holm([0.5, float("nan")])[1])


def test_wilcoxon_and_bootstrap() -> None:
    diffs = np.full(20, 0.1) + np.linspace(-0.01, 0.01, 20)
    assert wilcoxon_p(diffs) < 1e-4
    assert wilcoxon_p(np.zeros(20)) == 1.0
    low, high = bootstrap_ci(diffs, seed=1)
    assert low <= np.median(diffs) <= high
    assert bootstrap_ci(diffs, seed=1) == (low, high)  # seeded


def test_pareto_front() -> None:
    points = {"a": (0.9, 10.0), "b": (0.8, 1.0), "c": (0.7, 5.0), "d": (0.9, 12.0)}
    assert pareto(points) == {"a", "b"}  # c is beaten by b; d by a


def fake_rows(n_images: int = 20, reps: int = 2) -> list[dict]:
    """GEO is the worst everywhere, COLOR beats it by ~0.2, references add ~0.1."""
    rng = np.random.default_rng(0)
    base = {"GEO": 0.4, "COLOR": 0.6, "GRAD": 0.55, "HYB-GC": 0.7, "HYB-FILTER": 0.65, "REF-ONLY": 0.8}
    rows = []
    for img in range(n_images):
        for method, ap in base.items():
            for ref in (("exact", "degraded") if method == "REF-ONLY" else ("none", "exact", "degraded")):
                value = ap + (0.1 if ref != "none" and method != "REF-ONLY" else 0.0) + rng.normal(0, 0.01)
                for rep in range(reps):
                    row = {k: "" for k in COLUMNS}
                    row.update(run_id=f"{img}{method}{ref}{rep}", image_id=f"{img:04d}", rows=6, cols=9,
                               complexity=0, wear=0, method=method, reference=ref, repetition=rep,
                               ap=value, top1=value, t_total=1.0 + 0.1 * rep, status="ok")
                    rows.append(row)
    return rows


def test_comparisons_find_known_effects() -> None:
    cells, warnings = load_cells(fake_rows(), [])
    assert not warnings
    conds = [("6x9", 0, 0)]
    tests = comparisons(cells, conds)
    c1 = next(t for t in tests if t["comparison"] == "COLOR - GEO" and t["metric"] == "ap")
    assert c1["median_diff"] == pytest.approx(0.2, abs=0.02) and c1["significant"] and c1["n_images"] == 20
    c2 = next(t for t in tests if t["family"] == "C2" and t["arm"] == "HYB-GC" and t["metric"] == "ap")
    assert c2["baseline_arm"] == "COLOR"  # the better median of GEO / COLOR
    c3 = [t for t in tests if t["family"] == "C3" and t["metric"] == "ap"]
    assert len(c3) == 10 and all(t["median_diff"] == pytest.approx(0.1, abs=0.02) for t in c3)
    # 2 (C1) + 2 (C2) + 10 (C3) comparisons x 2 metrics
    assert len(tests) == 28
    taus = orderings(cells, conds)
    assert all(t["kendall_tau"] == pytest.approx(1.0) for t in taus)  # ordering unchanged by the reference


def test_end_to_end_writes_tables_and_report(tmp_path: Path) -> None:
    timing = tmp_path / "timing.csv"
    with timing.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(fake_rows(n_images=6))
    out = tmp_path / "analysis"
    subprocess.run([sys.executable, "-m", "jigsaw.analysis.analyze", "--timing", str(timing), "--out", str(out),
                    "--label", "TEST - fabricated data"], check=True, capture_output=True)
    for name in ("descriptive.csv", "tests.csv", "c4_orderings.csv", "c5_tradeoffs.csv", "analysis.md",
                 "c1_ap.png", "c3_top1.png", "c5_pareto_time.png"):
        assert (out / name).exists(), name
    text = (out / "analysis.md").read_text(encoding="utf-8")
    assert "TEST - fabricated data" in text and "C4" in text


def test_quality_only_rows_add_images_without_runtime() -> None:
    """D18: untimed images supply AP/top-1 for C1-C4 but no runtime for C5."""
    timed = fake_rows(n_images=4)
    untimed = [dict(r, image_id=f"9{r['image_id'][1:]}", repetition=0, t_total="")
               for r in fake_rows(n_images=4, reps=1)]
    cells, warnings = load_cells(timed, [], untimed)
    assert not warnings
    images = {k[2] for k in cells}
    assert len(images) == 8
    timed_cells = [v for k, v in cells.items() if not k[2].startswith("9")]
    untimed_cells = [v for k, v in cells.items() if k[2].startswith("9")]
    assert all(v["reps"] == 2 and np.isfinite(v["t_total"]) for v in timed_cells)
    assert all(v["reps"] == 0 and np.isnan(v["t_total"]) for v in untimed_cells)
    tests = comparisons(cells, [("6x9", 0, 0)])
    assert all(t["n_images"] == 8 for t in tests)  # quality comparisons use every image


def test_median_shift_rule() -> None:
    from jigsaw.run.timing_gate import median_shift

    # One slow repetition: CV is high, but the median barely moves.
    t = [1.0, 1.01, 0.99, 1.0, 1.6]
    assert np.std(t, ddof=1) / np.mean(t) > 0.1
    assert median_shift(t) < 0.01
    # Two clusters: the median depends on which repetition is left out.
    assert median_shift([1.0, 1.0, 1.5, 2.0, 2.0]) == pytest.approx(0.25 / 1.5)
    assert np.isnan(median_shift([1.0, 2.0]))
