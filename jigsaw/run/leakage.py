"""Gate G4: leakage and input controls (spec B4, B10).

For every pilot instance and every built reference-free method:
1. Stripped: the instance is copied with ``private/`` and ``reference/``
   removed; scores must be byte-identical to the normal run.
2. Re-permuted: piece IDs are re-drawn with a new seeded permutation (files
   renamed, index rewritten); scores mapped back to the original IDs must be
   identical, and so must every metric. Our tie rules are order-free, so
   "apart from tie-breaks" needs no allowance; any difference is reported.
Plus, once per gate run:
3. Canary: a worker with the input controls installed tries to open the real
   ``private/truth.json``; the read must be refused.
4. Static checks on ``public/``: only piece PNGs and ``piece_index.json``, no
   PNG text chunks, an index holding only IDs, and piece-ID order unrelated
   to grid position.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np

from jigsaw.config import load_config
from jigsaw.evaluate.metrics import evaluate, load_truth, truth_from_dict
from jigsaw.run.runner import Arm, all_arms, arm_is_built, call_worker, plan
from jigsaw.seeds import seed_int

METRIC_FIELDS = ("ap", "top1", "f1_at_e", "accuracy_at_e", "relation_accuracy", "filter_recall")


def stripped_copy(instance_dir: Path, dest: Path) -> Path:
    target = dest / instance_dir.name
    shutil.copytree(instance_dir / "public", target / "public")
    return target


def permuted_copy(instance_dir: Path, dest: Path) -> tuple[Path, dict[str, str]]:
    """Copy public data with piece IDs re-drawn; returns the copy and old -> new ID map."""
    index = json.loads((instance_dir / "public" / "piece_index.json").read_text(encoding="utf-8"))
    old = sorted(index["pieces"])
    perm = np.random.default_rng(seed_int("g4", instance_dir.name)).permutation(len(old))
    mapping = {pid: f"p{perm[k]:04d}" for k, pid in enumerate(old)}
    target = dest / instance_dir.name
    (target / "public" / "pieces").mkdir(parents=True)
    for pid, new in mapping.items():
        shutil.copyfile(instance_dir / "public" / "pieces" / f"{pid}.png",
                        target / "public" / "pieces" / f"{new}.png")
    (target / "public" / "piece_index.json").write_text(
        json.dumps({"instance_id": index["instance_id"], "pieces": sorted(mapping.values())}, indent=2),
        encoding="utf-8")
    return target, mapping


def run_in(instance_dir: Path, arm: Arm) -> tuple[dict[str, np.ndarray], dict]:
    with tempfile.TemporaryDirectory(prefix="jigsaw_g4_") as tmp:
        return call_worker(instance_dir, arm, Path(tmp))


def check(instance_dir: Path, arm: Arm) -> dict:
    normal, _ = run_in(instance_dir, arm)
    truth = load_truth(instance_dir)
    base_metrics = evaluate(normal, truth)
    with tempfile.TemporaryDirectory(prefix="jigsaw_g4_copy_") as tmp:
        stripped, _ = run_in(stripped_copy(instance_dir, Path(tmp) / "stripped"), arm)
        permuted_dir, mapping = permuted_copy(instance_dir, Path(tmp) / "permuted")
        permuted, _ = run_in(permuted_dir, arm)

    stripped_equal = all(np.array_equal(normal[k], stripped[k]) for k in ("right", "below"))

    new_sorted = sorted(mapping.values())
    position = np.array([new_sorted.index(mapping[pid]) for pid in truth.piece_ids])
    back = {k: permuted[k][np.ix_(position, position)] for k in ("right", "below")}
    def finite_diff(a: np.ndarray, b: np.ndarray) -> float:
        both = np.isfinite(a) & np.isfinite(b)
        return float(np.max(np.abs(a[both] - b[both]))) if both.any() else 0.0

    max_diff = max(finite_diff(normal[k], back[k]) for k in ("right", "below"))
    same_exclusions = all(np.array_equal(np.isfinite(normal[k]), np.isfinite(back[k]))
                          for k in ("right", "below"))
    permuted_equal = all(np.array_equal(normal[k], back[k]) for k in ("right", "below"))

    raw_truth = json.loads((instance_dir / "private" / "truth.json").read_text(encoding="utf-8"))
    renamed = dict(raw_truth)
    renamed["pieces"] = {mapping[pid]: v for pid, v in raw_truth["pieces"].items()}
    renamed["true_pairs"] = [dict(p, a=mapping[p["a"]], b=mapping[p["b"]]) for p in raw_truth["true_pairs"]]
    permuted_metrics = evaluate(permuted, truth_from_dict(renamed, tuple(new_sorted)))
    metric_diffs = {f: abs(getattr(base_metrics, f) - getattr(permuted_metrics, f)) for f in METRIC_FIELDS}

    return {
        "stripped_scores_identical": stripped_equal,
        "permuted_scores_identical": permuted_equal,
        "permuted_same_exclusions": same_exclusions,
        "permuted_max_abs_score_diff": max_diff,
        "permuted_metric_abs_diffs": metric_diffs,
        "pass": stripped_equal and permuted_equal and max(metric_diffs.values()) == 0.0,
    }


def canary(instance_dir: Path) -> dict:
    """A worker process with input controls must be refused when it opens ground truth."""
    target = instance_dir / "private" / "truth.json"
    code = ("import sys; from jigsaw.run.worker import install_input_controls; "
            "install_input_controls([sys.argv[1], sys.argv[2]]); "
            "\ntry:\n    open(sys.argv[3]).read(); print('LEAKED')\n"
            "except PermissionError:\n    print('BLOCKED')\n"
            "try:\n    import os; os.listdir(sys.argv[1]); print('LEAKED')\n"
            "except PermissionError:\n    print('BLOCKED')")
    done = subprocess.run([sys.executable, "-c", code, str(instance_dir / "private"),
                           str(instance_dir / "reference"), str(target)],
                          capture_output=True, text=True)
    lines = done.stdout.split()
    return {"open_truth": lines[0] if lines else done.stderr[-200:],
            "list_private": lines[1] if len(lines) > 1 else "",
            "pass": lines == ["BLOCKED", "BLOCKED"]}


def static_checks(instance_dir: Path) -> dict:
    public = instance_dir / "public"
    files = sorted(p.relative_to(public).as_posix() for p in public.rglob("*") if p.is_file())
    unexpected = [f for f in files if f != "piece_index.json" and not
                  (f.startswith("pieces/p") and f.endswith(".png") and len(f) == len("pieces/p0000.png"))]
    text_chunks = [f for f in files if f.endswith(".png") and any(
        tag in (public / f).read_bytes() for tag in (b"tEXt", b"iTXt", b"zTXt", b"eXIf"))]
    index = json.loads((public / "piece_index.json").read_text(encoding="utf-8"))
    truth = json.loads((instance_dir / "private" / "truth.json").read_text(encoding="utf-8"))
    ids = sorted(truth["pieces"])
    id_rank = np.arange(len(ids))
    grid_rank = np.argsort(np.argsort([truth["pieces"][p]["grid_index"] for p in ids]))
    spearman = float(np.corrcoef(id_rank, grid_rank)[0, 1])
    return {"unexpected_public_files": unexpected, "png_text_chunks": text_chunks,
            "index_keys": sorted(index), "id_grid_spearman": spearman,
            "pass": not unexpected and not text_chunks and sorted(index) == ["instance_id", "pieces"]
            and abs(spearman) < 0.35}


def main() -> None:
    parser = argparse.ArgumentParser(description="Check gate G4 on generated instances.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--report", type=Path, default=Path("results/gates/step6_g4.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    arms = [a for a in all_arms(config) if a.reference == "none" and arm_is_built(a)]
    targets, _ = plan(config, args.instances, [0])

    results = {}
    for instance_dir, cond in targets:
        entry = {"condition": cond, "static": static_checks(instance_dir), "arms": {}}
        for arm in arms:
            entry["arms"][arm.method] = check(instance_dir, arm)
        results[instance_dir.name] = entry
        arm_text = "  ".join(f"{m}: {'ok' if r['pass'] else 'FAIL'} (perm max diff {r['permuted_max_abs_score_diff']:.1e})"
                             for m, r in entry["arms"].items())
        print(f"{cond['rows']}x{cond['cols']:<3} {cond['image_id']} w{cond['wear']}  static "
              f"{'ok' if entry['static']['pass'] else 'FAIL'} (id/grid rho {entry['static']['id_grid_spearman']:+.2f})  {arm_text}")

    canary_result = canary(targets[0][0])
    print(f"canary: open truth.json -> {canary_result['open_truth']}, list private/ -> {canary_result['list_private']}")
    passed = canary_result["pass"] and all(
        e["static"]["pass"] and all(r["pass"] for r in e["arms"].values()) for e in results.values())
    report = {"G4_pass": passed, "methods_checked": [a.method for a in arms],
              "note": "reference-free arms only; reference arms are checked again in build step 9",
              "canary": canary_result, "instances": results}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"G4: {'PASS' if passed else 'FAIL'} ({len(results)} instances x {len(arms)} methods)")


if __name__ == "__main__":
    main()
