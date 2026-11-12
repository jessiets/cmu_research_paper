"""Gate G5: evaluator known-answer tests on the real pilot instances (spec B10).

Pass conditions:
- Oracle: AP, top-1, F1@E, accuracy@E, and relation accuracy are all exactly 1.
- Reversed oracle: top-1 is 0 and AP is at most the base rate (true pairs ranked last).
- All-tied scores (a random ranking in expectation): AP equals the base rate.
- Random scores: mean AP over many draws is within 3 standard errors of the exact
  expected AP of a random ranking, which sits slightly above the base rate for
  finite N; top-1 is within 3 standard errors of 1 / (n - 1).
- AP agrees with scikit-learn's ``average_precision_score`` on random draws.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
from sklearn.metrics import average_precision_score

from jigsaw.config import load_config
from jigsaw.evaluate import known_answers as ka
from jigsaw.evaluate.metrics import Truth, evaluate, load_truth
from jigsaw.run.pairs import to_pair_scores

RANDOM_DRAWS = 200
SKLEARN_DRAWS = 5
TOLERANCE = 1e-12


def expected_random_ap(candidates: int, positives: int) -> float:
    """Exact E[AP] for a uniformly random ranking of N items with E positives.

    E[AP] = (1/N) * sum_{r=1..N} [ 1/r + ((E-1)/(N-1)) * (r-1)/r ]
    """
    r = np.arange(1, candidates + 1, dtype=np.float64)
    return float(np.mean(1.0 / r + (positives - 1) / (candidates - 1) * (r - 1) / r))


def labels_for(truth: Truth, pairs) -> np.ndarray:
    n = truth.n
    flat = pairs.i * n + pairs.j
    labels = np.zeros(pairs.size, dtype=bool)
    labels[np.searchsorted(flat, [i * n + j for i, j, _ in truth.pairs])] = True
    return labels


def check_truth(truth: Truth) -> dict:
    o = evaluate(ka.oracle(truth), truth)
    rev = evaluate(ka.reversed_oracle(truth), truth)
    tied = evaluate(ka.all_tied(truth), truth)
    aps, top1s, sk_diff = [], [], 0.0
    for seed in range(RANDOM_DRAWS):
        scores = ka.random_scores(truth, seed)
        pairs = to_pair_scores(scores)
        m = evaluate(scores, truth, pairs)
        aps.append(m.ap)
        top1s.append(m.top1)
        if seed < SKLEARN_DRAWS:
            sk = average_precision_score(labels_for(truth, pairs), pairs.score)
            sk_diff = max(sk_diff, abs(sk - m.ap))
    expected_ap = expected_random_ap(o.candidates, o.true_pairs)
    ap_mean, ap_se = float(np.mean(aps)), float(np.std(aps, ddof=1) / np.sqrt(RANDOM_DRAWS))
    t1_mean, t1_se = float(np.mean(top1s)), float(np.std(top1s, ddof=1) / np.sqrt(RANDOM_DRAWS))
    chance_top1 = 1.0 / (truth.n - 1)

    checks = {
        "oracle_all_one": all(v == 1.0 for v in (o.ap, o.top1, o.f1_at_e, o.accuracy_at_e,
                                                 o.relation_accuracy)),
        "reversed_top1_zero": rev.top1 == 0.0,
        "reversed_ap_at_most_base_rate": rev.ap <= rev.base_rate + TOLERANCE,
        "tied_ap_equals_base_rate": abs(tied.ap - tied.base_rate) <= TOLERANCE,
        "random_ap_matches_expected": abs(ap_mean - expected_ap) <= 3 * ap_se,
        "random_top1_matches_chance": abs(t1_mean - chance_top1) <= 3 * t1_se,
        "ap_matches_sklearn": sk_diff <= TOLERANCE,
    }
    return {
        "n": truth.n, "candidates": o.candidates, "true_pairs": o.true_pairs,
        "base_rate": o.base_rate,
        "oracle": o.to_dict(),
        "reversed": {"ap": rev.ap, "top1": rev.top1, "f1_at_e": rev.f1_at_e},
        "tied_ap": tied.ap,
        "random": {"draws": RANDOM_DRAWS, "ap_mean": ap_mean, "ap_se": ap_se,
                   "expected_ap": expected_ap, "top1_mean": t1_mean, "top1_se": t1_se,
                   "chance_top1": chance_top1},
        "sklearn_max_abs_diff": sk_diff,
        "checks": checks,
        "pass": all(checks.values()),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Check gate G5 on generated instances.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--report", type=Path, default=Path("results/gates/step3_g5.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    wanted = {Path(name).stem for name in config.source_images}
    index = json.loads((args.instances / "index.json").read_text(encoding="utf-8"))

    results = {}
    for iid, cond in sorted(index.items(), key=lambda kv: (kv[1]["n"], kv[1]["image_id"], kv[1]["wear"])):
        if cond["image_id"] not in wanted:
            continue
        result = check_truth(load_truth(args.instances / iid))
        result["condition"] = cond
        results[iid] = result
        r = result["random"]
        print(f"{cond['rows']}x{cond['cols']:<3} {cond['image_id']} w{cond['wear']}  "
              f"oracle AP/top1 {result['oracle']['ap']:.3f}/{result['oracle']['top1']:.3f}  "
              f"reversed AP {result['reversed']['ap']:.5f} (base {result['base_rate']:.5f}) top1 {result['reversed']['top1']:.3f}  "
              f"random AP {r['ap_mean']:.5f}+-{r['ap_se']:.5f} (expected {r['expected_ap']:.5f})  "
              f"{'PASS' if result['pass'] else 'FAIL'}")

    report = {"G5_pass": all(r["pass"] for r in results.values()),
              "instances_checked": len(results), "random_draws": RANDOM_DRAWS, "instances": results}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"G5: {'PASS' if report['G5_pass'] else 'FAIL'} on {len(results)} instances")


if __name__ == "__main__":
    main()
