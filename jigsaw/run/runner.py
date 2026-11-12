"""Resumable experiment runner (spec B8, B9).

For each (instance, arm, repetition) it starts a fresh worker process that
sees only a temporary copy of the instance's ``public/`` folder (plus the
reference array for reference arms), then evaluates the returned relation
scores against ground truth in this process. One row is appended per finished
run, successful or not. Runs whose ``run_id`` already has an ``ok`` row are
skipped, so the runner can be stopped and restarted. Failed runs keep their
row with ``status`` and ``error``; a restart tries them again and appends a
new row.

Environment details (CPU, RAM, OS, dependency versions) go in a sidecar file
``<results>.meta.json`` next to every results CSV.

Measurement protocol (5 timed repetitions, randomized order, separate memory
runs) is build step 10; here every run is timed once with perf_counter and
process_time and memory fields are left empty.
"""

from __future__ import annotations

import argparse
import csv
import dataclasses
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import traceback
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from jigsaw.config import ExperimentConfig, load_config
from jigsaw.cvsetup import cv2
from jigsaw.evaluate.metrics import evaluate, load_truth
from jigsaw.generate.instance import Condition, software_versions
from jigsaw.generate.sources import image_id_for
from jigsaw.methods.registry import available
from jigsaw.seeds import seed_hex

COLUMNS = [
    "run_id", "git_commit", "config_hash", "instance_id", "image_id", "rows", "cols", "n",
    "complexity", "wear", "reference", "method", "repetition", "candidates_scored",
    "candidates_excluded", "ap", "top1", "f1_at_e", "accuracy_at_e", "relation_accuracy",
    "filter_recall", "extraction_failures", "t_load", "t_preprocess", "t_extract", "t_reference",
    "t_score", "t_total", "cpu_total", "cpu_utilization", "peak_rss_delta", "feature_bytes",
    "score_bytes", "status", "error",
]
REFERENCE_FILES = {"exact": "exact.png", "degraded": "degraded.png"}


@dataclass(frozen=True)
class Arm:
    method: str
    reference: str  # none, exact, degraded

    @property
    def label(self) -> str:
        if self.method == "REF-ONLY":
            return f"REF-ONLY ({self.reference})"
        return self.method if self.reference == "none" else f"{self.method}+R ({self.reference})"


def all_arms(config: ExperimentConfig) -> list[Arm]:
    """Spec A2: 5 methods x 3 reference levels, plus REF-ONLY at 2 levels = 17 arms."""
    arms = []
    for method in config.methods:
        levels = [r for r in config.reference_levels if r != "none"] if method == "REF-ONLY" \
            else list(config.reference_levels)
        arms += [Arm(method, ref) for ref in levels]
    return arms


def arm_is_built(arm: Arm) -> bool:
    """Reference arms arrive in build step 9; methods arrive in build order."""
    return arm.method in available() and arm.reference == "none"


def config_hash(config: ExperimentConfig) -> str:
    return seed_hex(json.dumps(dataclasses.asdict(config), sort_keys=True))[:16]


def git_commit() -> str:
    try:
        head = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True,
                              check=True).stdout.strip()
        dirty = subprocess.run(["git", "status", "--porcelain", "--untracked-files=no"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return "unknown"
    return head + ("-dirty" if dirty else "")


def run_id(instance_id: str, arm: Arm, repetition: int) -> str:
    return seed_hex("run", instance_id, arm.method, arm.reference, repetition)[:16]


def environment() -> dict:
    info = {"os": platform.platform(), "machine": platform.machine(),
            "processor": platform.processor(), "cpu_count": os.cpu_count(),
            "software": software_versions(),
            "threads": {k: os.environ.get(k) for k in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS",
                                                       "MKL_NUM_THREADS")},
            "opencv_threads": cv2.getNumThreads()}
    if sys.platform == "win32":
        import ctypes

        class MemoryStatus(ctypes.Structure):
            _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]
        status = MemoryStatus()
        status.dwLength = ctypes.sizeof(MemoryStatus)
        if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
            info["ram_bytes"] = int(status.ullTotalPhys)
    elif hasattr(os, "sysconf"):
        try:
            info["ram_bytes"] = os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")
        except (ValueError, OSError):
            pass
    return info


def completed_run_ids(results: Path) -> set[str]:
    if not results.exists():
        return set()
    with results.open(newline="", encoding="utf-8") as file:
        return {row["run_id"] for row in csv.DictReader(file) if row["status"] == "ok"}


def append_row(results: Path, row: dict) -> None:
    new = not results.exists()
    results.parent.mkdir(parents=True, exist_ok=True)
    with results.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in COLUMNS})
        file.flush()
        os.fsync(file.fileno())


def call_worker(instance_dir: Path, arm: Arm, workdir: Path) -> tuple[dict[str, np.ndarray], dict]:
    """Copy public data to ``workdir``, run the worker there, and return its outputs."""
    public = workdir / "public"
    shutil.copytree(instance_dir / "public", public)
    command = [sys.executable, "-m", "jigsaw.run.worker", "--public", str(public),
               "--instance-id", instance_dir.name, "--method", arm.method, "--out", str(workdir),
               "--forbid", str(instance_dir / "private"), "--forbid", str(instance_dir / "reference")]
    if arm.reference != "none":
        bgr = cv2.imread(str(instance_dir / "reference" / REFERENCE_FILES[arm.reference]), cv2.IMREAD_COLOR)
        np.save(workdir / "reference.npy", cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
        command += ["--reference", str(workdir / "reference.npy")]
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        lines = [line for line in done.stderr.strip().splitlines() if line.strip()]
        raise RuntimeError(lines[-1] if lines else f"worker exited with code {done.returncode}")
    with np.load(workdir / "scores.npz") as data:
        scores = {key: data[key] for key in ("right", "below")}
    return scores, json.loads((workdir / "measures.json").read_text(encoding="utf-8"))


def execute(instance_dir: Path, cond: dict, arm: Arm, repetition: int, base_row: dict) -> dict:
    row = dict(base_row, instance_id=instance_dir.name, image_id=cond["image_id"], rows=cond["rows"],
               cols=cond["cols"], n=cond["n"], complexity=cond["complexity"], wear=cond["wear"],
               reference=arm.reference, method=arm.method, repetition=repetition,
               run_id=run_id(instance_dir.name, arm, repetition))
    try:
        with tempfile.TemporaryDirectory(prefix="jigsaw_run_") as tmp:
            scores, measures = call_worker(instance_dir, arm, Path(tmp))
        truth = load_truth(instance_dir)
        if tuple(measures["piece_ids"]) != truth.piece_ids:
            raise RuntimeError("worker piece order differs from the evaluator's")
        metrics = evaluate(scores, truth)
        t_reference = 0.0
        t_total = measures["t_extract"] + measures["t_score"] + t_reference
        row.update(
            candidates_scored=measures["candidates_scored"],
            candidates_excluded=measures["candidates_excluded"],
            ap=metrics.ap, top1=metrics.top1, f1_at_e=metrics.f1_at_e,
            accuracy_at_e=metrics.accuracy_at_e, relation_accuracy=metrics.relation_accuracy,
            filter_recall=metrics.filter_recall, extraction_failures=measures["extraction_failures"],
            t_load=measures["t_load"], t_preprocess=measures["t_preprocess"],
            t_extract=measures["t_extract"], t_reference="", t_score=measures["t_score"],
            t_total=t_total, cpu_total=measures["cpu_extract_score"],
            cpu_utilization=measures["cpu_extract_score"] / t_total if t_total > 0 else "",
            feature_bytes=measures["feature_bytes"], score_bytes=measures["score_bytes"],
            status="ok", error="",
        )
    except Exception as exc:  # failed runs stay in the results file
        row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    return row


def plan(config: ExperimentConfig, instances: Path, complexity: list[int]) -> tuple[list[tuple[Path, dict]], list[dict]]:
    index = json.loads((instances / "index.json").read_text(encoding="utf-8"))
    found, missing = [], []
    for name in config.source_images:
        for rows, cols in config.grids:
            for level in complexity:
                for wear in config.wear_levels_px:
                    cond = Condition(image_id_for(name), rows, cols, level, wear)
                    if cond.instance_id in index and (instances / cond.instance_id).is_dir():
                        found.append((instances / cond.instance_id, index[cond.instance_id]))
                    else:
                        missing.append(cond.to_json())
    return found, missing


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run arms on generated instances (resumable).")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--methods", nargs="*", help="subset of methods (default: config)")
    parser.add_argument("--references", nargs="*", help="subset of reference levels (default: config)")
    parser.add_argument("--complexity", type=int, nargs="*", help="subset of complexity levels")
    parser.add_argument("--repetitions", type=int, default=1)
    parser.add_argument("--allow-main", action="store_true",
                        help="required for the main config; only with the user's approval (spec B13)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if config.profile == "main" and not args.allow_main:
        sys.exit("refusing to run the main config without --allow-main (needs the user's approval, spec B13)")
    arms = [a for a in all_arms(config)
            if (not args.methods or a.method in args.methods)
            and (not args.references or a.reference in args.references)]
    unbuilt = [a for a in arms if not arm_is_built(a)]
    if unbuilt:
        print(f"skipping {len(unbuilt)} arms not built yet: {', '.join(a.label for a in unbuilt)}")
    arms = [a for a in arms if arm_is_built(a)]
    levels = args.complexity if args.complexity is not None else list(config.complexity_levels)
    targets, missing = plan(config, args.instances, levels)
    if missing:
        print(f"warning: {len(missing)} instances not generated yet (e.g. {missing[0]}); skipped")

    meta = {"config": str(args.config), "config_hash": config_hash(config), "environment": environment()}
    args.results.parent.mkdir(parents=True, exist_ok=True)
    Path(str(args.results) + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")

    done = completed_run_ids(args.results)
    base = {"git_commit": git_commit(), "config_hash": meta["config_hash"], "peak_rss_delta": ""}
    total = len(targets) * len(arms) * args.repetitions
    counts = {"ok": 0, "failed": 0, "skipped": 0}
    step = 0
    for instance_dir, cond in targets:
        for arm in arms:
            for repetition in range(args.repetitions):
                step += 1
                if run_id(instance_dir.name, arm, repetition) in done:
                    counts["skipped"] += 1
                    continue
                row = execute(instance_dir, cond, arm, repetition, base)
                append_row(args.results, row)
                counts[row["status"]] += 1
                if row["status"] == "ok":
                    print(f"[{step}/{total}] {cond['rows']}x{cond['cols']} w{cond['wear']} "
                          f"{cond['image_id']} {arm.label}: AP {row['ap']:.3f} top1 {row['top1']:.3f}")
    print(f"done: {counts}")


if __name__ == "__main__":
    main()
