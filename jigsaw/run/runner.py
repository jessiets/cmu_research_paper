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
import hashlib
import dataclasses
import json
import os
import platform
import random
import shutil
import subprocess
import sys
import tempfile
import time
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
from jigsaw.seeds import seed_hex, seed_int

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
    """Methods arrive in build order (spec B11); REF-ONLY exists only with a reference."""
    if arm.method == "REF-ONLY":
        return arm.reference != "none"
    return arm.method in available()


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


DEFAULT_CACHE = Path("data/cache/reference")


def _worker_command(instance_dir: Path, public: Path, workdir: Path) -> list[str]:
    return [sys.executable, "-m", "jigsaw.run.worker", "--public", str(public),
            "--instance-id", instance_dir.name, "--out", str(workdir),
            "--forbid", str(instance_dir / "private"), "--forbid", str(instance_dir / "reference")]


def _run_worker(command: list[str]) -> None:
    done = subprocess.run(command, capture_output=True, text=True)
    if done.returncode != 0:
        lines = [line for line in done.stderr.strip().splitlines() if line.strip()]
        raise RuntimeError(lines[-1] if lines else f"worker exited with code {done.returncode}")


def cache_key(instance_dir: Path, level: str) -> str:
    """Changes whenever the reference file or the location code changes."""
    code = (Path(__file__).parents[1] / "features" / "reference.py").read_bytes()
    ref = (instance_dir / "reference" / REFERENCE_FILES[level]).read_bytes()
    return seed_hex(hashlib.sha256(code).hexdigest(), hashlib.sha256(ref).hexdigest())[:16]


def locate_in_worker(instance_dir: Path, level: str, workdir: Path,
                     measure_memory: bool = False) -> tuple[dict[str, np.ndarray], dict]:
    """Run the timed location step in a fresh worker that sees public data plus the reference array."""
    public = workdir / "public"
    shutil.copytree(instance_dir / "public", public)
    bgr = cv2.imread(str(instance_dir / "reference" / REFERENCE_FILES[level]), cv2.IMREAD_COLOR)
    np.save(workdir / "reference.npy", cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))
    _run_worker(_worker_command(instance_dir, public, workdir)
                + ["--task", "locate", "--reference", str(workdir / "reference.npy")]
                + (["--measure-memory"] if measure_memory else []))
    with np.load(workdir / "locations.npz") as data:
        arrays = {k: data[k] for k in data.files}
    return arrays, json.loads((workdir / "measures.json").read_text(encoding="utf-8"))


def cached_locations(instance_dir: Path, level: str, cache_dir: Path = DEFAULT_CACHE) -> tuple[Path, dict]:
    """Locations for (instance, level): computed once, then reused by every reference arm (D2)."""
    key = cache_key(instance_dir, level)
    path = cache_dir / f"{instance_dir.name}_{level}.npz"
    meta_path = path.with_suffix(".json")
    if path.exists() and meta_path.exists():
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        if meta.get("cache_key") == key:
            return path, meta
    cache_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="jigsaw_locate_") as tmp:
        arrays, measures = locate_in_worker(instance_dir, level, Path(tmp))
    np.savez(path, **arrays)
    meta = dict(measures, cache_key=key, level=level, instance_id=instance_dir.name)
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return path, meta


def call_worker(instance_dir: Path, arm: Arm, workdir: Path, locations: Path | None = None,
                measure_memory: bool = False) -> tuple[dict[str, np.ndarray], dict]:
    """Copy public data to ``workdir``, run the scoring worker there, and return its outputs."""
    public = workdir / "public"
    shutil.copytree(instance_dir / "public", public)
    command = _worker_command(instance_dir, public, workdir) + ["--method", arm.method]
    if arm.reference != "none":
        if locations is None:
            raise ValueError("reference arms need cached locations")
        command += ["--with-reference", "--locations", str(locations)]
    if measure_memory:
        command.append("--measure-memory")
    _run_worker(command)
    with np.load(workdir / "scores.npz") as data:
        scores = {key: data[key] for key in ("right", "below")}
    return scores, json.loads((workdir / "measures.json").read_text(encoding="utf-8"))


def execute(instance_dir: Path, cond: dict, arm: Arm, repetition: int, base_row: dict,
            cache_dir: Path = DEFAULT_CACHE, mode: str = "quality",
            t_reference_override: float | None = None) -> dict:
    """One arm run. ``mode``: quality (single run), timing (one timed repetition;
    t_reference is the median of the timed location runs), or memory (peak
    memory recorded; its timings are not used)."""
    row = dict(base_row, instance_id=instance_dir.name, image_id=cond["image_id"], rows=cond["rows"],
               cols=cond["cols"], n=cond["n"], complexity=cond["complexity"], wear=cond["wear"],
               reference=arm.reference, method=arm.method, repetition=repetition,
               run_id=run_id(instance_dir.name, arm, repetition))
    try:
        locations, t_reference = None, 0.0
        if arm.reference != "none":
            locations, ref_meta = cached_locations(instance_dir, arm.reference, cache_dir)
            t_reference = ref_meta["t_reference"] if t_reference_override is None else t_reference_override
        with tempfile.TemporaryDirectory(prefix="jigsaw_run_") as tmp:
            scores, measures = call_worker(instance_dir, arm, Path(tmp), locations, mode == "memory")
        truth = load_truth(instance_dir)
        if tuple(measures["piece_ids"]) != truth.piece_ids:
            raise RuntimeError("worker piece order differs from the evaluator's")
        metrics = evaluate(scores, truth)
        t_total = measures["t_extract"] + measures["t_score"] + t_reference
        row.update(
            candidates_scored=measures["candidates_scored"],
            candidates_excluded=measures["candidates_excluded"],
            ap=metrics.ap, top1=metrics.top1, f1_at_e=metrics.f1_at_e,
            accuracy_at_e=metrics.accuracy_at_e, relation_accuracy=metrics.relation_accuracy,
            filter_recall=metrics.filter_recall, extraction_failures=measures["extraction_failures"],
            t_load=measures["t_load"], t_preprocess=measures["t_preprocess"],
            t_extract=measures["t_extract"],
            t_reference=t_reference if arm.reference != "none" else "", t_score=measures["t_score"],
            t_total=t_total, cpu_total=measures["cpu_extract_score"],
            cpu_utilization=measures["cpu_extract_score"] / t_total if t_total > 0 else "",
            feature_bytes=measures["feature_bytes"], score_bytes=measures["score_bytes"],
            peak_rss_delta=measures["peak_rss_delta"] if mode == "memory" else "",
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


REFERENCE_COLUMNS = [
    "run_id", "git_commit", "config_hash", "instance_id", "image_id", "rows", "cols", "n", "complexity",
    "wear", "reference", "repetition", "mode", "t_reference", "cpu_reference", "peak_rss_delta",
    "status", "error",
]


def reference_results_path(results: Path) -> Path:
    return results.with_name(results.stem + "_reference" + results.suffix)


def locate_run_id(instance_id: str, level: str, repetition: int, mode: str) -> str:
    return seed_hex("locate", instance_id, level, repetition, mode)[:16]


def locate_run(instance_dir: Path, cond: dict, level: str, repetition: int, mode: str, base: dict) -> dict:
    """One timed (or memory) run of the location step, in a fresh worker."""
    row = dict(base, instance_id=instance_dir.name, image_id=cond["image_id"], rows=cond["rows"],
               cols=cond["cols"], n=cond["n"], complexity=cond["complexity"], wear=cond["wear"],
               reference=level, repetition=repetition, mode=mode,
               run_id=locate_run_id(instance_dir.name, level, repetition, mode))
    try:
        with tempfile.TemporaryDirectory(prefix="jigsaw_locate_") as tmp:
            _, measures = locate_in_worker(instance_dir, level, Path(tmp), mode == "memory")
        row.update(t_reference=measures["t_reference"], cpu_reference=measures["cpu_reference"],
                   peak_rss_delta=measures["peak_rss_delta"] if mode == "memory" else "",
                   status="ok", error="")
    except Exception as exc:
        row.update(status="failed", error=f"{type(exc).__name__}: {exc}")
        traceback.print_exc()
    return row


def append_reference_row(path: Path, row: dict) -> None:
    new = not path.exists()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=REFERENCE_COLUMNS)
        if new:
            writer.writeheader()
        writer.writerow({k: row.get(k, "") for k in REFERENCE_COLUMNS})
        file.flush()
        os.fsync(file.fileno())


def runlog_path(results: Path) -> Path:
    return results.with_name(results.stem + "_runlog.csv")


def log_wall(results: Path, kind: str, run: str, grid: str, wall: float, status: str) -> None:
    """Full wall-clock seconds per run, process start-up included (used for the G9 projection)."""
    path = runlog_path(results)
    new = not path.exists()
    with path.open("a", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        if new:
            writer.writerow(["kind", "run_id", "grid", "wall_seconds", "status"])
        writer.writerow([kind, run, grid, f"{wall:.4f}", status])


def median_reference_times(path: Path) -> dict[tuple[str, str], float]:
    """(instance_id, level) -> median t_reference over the ok timing runs."""
    times: dict[tuple[str, str], list[float]] = {}
    if path.exists():
        with path.open(newline="", encoding="utf-8") as file:
            for row in csv.DictReader(file):
                if row["status"] == "ok" and row["mode"] == "timing":
                    times.setdefault((row["instance_id"], row["reference"]), []).append(float(row["t_reference"]))
    return {key: float(np.median(v)) for key, v in times.items()}


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run arms on generated instances (resumable).")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--mode", choices=("quality", "timing", "memory"), default="quality",
                        help="quality: one run per arm; timing: timed repetitions in fresh processes, "
                             "randomized order (spec B9); memory: separate peak-memory runs")
    parser.add_argument("--methods", nargs="*", help="subset of methods (default: config)")
    parser.add_argument("--references", nargs="*", help="subset of reference levels (default: config)")
    parser.add_argument("--complexity", type=int, nargs="*", help="subset of complexity levels")
    parser.add_argument("--images", nargs="*", help="subset of the config's image IDs")
    parser.add_argument("--grids", nargs="*", help="subset of grids, e.g. 6x9 20x30")
    parser.add_argument("--repetitions", type=int,
                        help="default: the config's timing_repetitions in timing mode, else 1")
    parser.add_argument("--cache", type=Path, default=DEFAULT_CACHE, help="reference-location cache")
    parser.add_argument("--allow-main", action="store_true",
                        help="required for the main config; only with the user's approval (spec B13)")
    args = parser.parse_args(argv)

    config = load_config(args.config)
    if config.profile == "main" and not args.allow_main:
        sys.exit("refusing to run the main config without --allow-main (needs the user's approval, spec B13)")
    repetitions = args.repetitions or (config.timing_repetitions if args.mode == "timing" else 1)
    arms = [a for a in all_arms(config)
            if (not args.methods or a.method in args.methods)
            and (not args.references or a.reference in args.references)]
    unbuilt = [a for a in arms if not arm_is_built(a)]
    if unbuilt:
        print(f"skipping {len(unbuilt)} arms not built yet: {', '.join(a.label for a in unbuilt)}")
    arms = [a for a in arms if arm_is_built(a)]
    levels = args.complexity if args.complexity is not None else list(config.complexity_levels)
    targets, missing = plan(config, args.instances, levels)
    if args.images:
        known = {t[1]["image_id"] for t in targets}
        unknown = sorted(set(args.images) - known)
        if unknown:
            raise SystemExit(f"--images not found among this config's generated instances: {', '.join(unknown)}")
        targets = [t for t in targets if t[1]["image_id"] in args.images]
    if args.grids:
        targets = [t for t in targets if f"{t[1]['rows']}x{t[1]['cols']}" in args.grids]
    if missing:
        print(f"warning: {len(missing)} instances not generated yet (e.g. {missing[0]}); skipped")

    meta = {"config": str(args.config), "config_hash": config_hash(config), "mode": args.mode,
            "repetitions": repetitions, "environment": environment()}
    args.results.parent.mkdir(parents=True, exist_ok=True)
    Path(str(args.results) + ".meta.json").write_text(json.dumps(meta, indent=2) + "\n", encoding="utf-8")
    base = {"git_commit": git_commit(), "config_hash": meta["config_hash"], "peak_rss_delta": ""}
    order = random.Random(seed_int(config.master_seed, "run-order", args.mode))

    # Reference location runs first: timing and memory modes measure that step on its own (spec B7, B9).
    ref_path = reference_results_path(args.results)
    ref_levels = sorted({a.reference for a in arms if a.reference != "none"})
    if args.mode in ("timing", "memory") and ref_levels:
        done = completed_run_ids(ref_path)
        tasks = [(d, c, lvl, r) for d, c in targets for lvl in ref_levels for r in range(repetitions)]
        order.shuffle(tasks)
        for step, (instance_dir, cond, level, rep) in enumerate(tasks, 1):
            if locate_run_id(instance_dir.name, level, rep, args.mode) in done:
                continue
            started = time.perf_counter()
            row = locate_run(instance_dir, cond, level, rep, args.mode, base)
            append_reference_row(ref_path, row)
            log_wall(args.results, "locate", row["run_id"], f"{cond['rows']}x{cond['cols']}",
                     time.perf_counter() - started, row["status"])
            print(f"[locate {step}/{len(tasks)}] {cond['rows']}x{cond['cols']} w{cond['wear']} "
                  f"{cond['image_id']} {level} rep {rep}: {row['status']}", flush=True)
    medians = median_reference_times(ref_path) if args.mode == "timing" else {}

    done = completed_run_ids(args.results)
    tasks = [(d, c, a, r) for d, c in targets for a in arms for r in range(repetitions)]
    if args.mode == "timing":
        order.shuffle(tasks)  # randomized order (spec B9)
    counts = {"ok": 0, "failed": 0, "skipped": 0}
    for step, (instance_dir, cond, arm, repetition) in enumerate(tasks, 1):
        if run_id(instance_dir.name, arm, repetition) in done:
            counts["skipped"] += 1
            continue
        override = None
        if args.mode == "timing" and arm.reference != "none":
            override = medians.get((instance_dir.name, arm.reference))
            if override is None:
                row = dict(base, run_id=run_id(instance_dir.name, arm, repetition),
                           instance_id=instance_dir.name, image_id=cond["image_id"], rows=cond["rows"],
                           cols=cond["cols"], n=cond["n"], complexity=cond["complexity"], wear=cond["wear"],
                           method=arm.method, reference=arm.reference, repetition=repetition,
                           status="failed", error="no successful timed location runs for this instance and level")
                append_row(args.results, row)
                counts["failed"] += 1
                continue
        started = time.perf_counter()
        row = execute(instance_dir, cond, arm, repetition, base, args.cache, args.mode, override)
        append_row(args.results, row)
        log_wall(args.results, "arm", row["run_id"], f"{cond['rows']}x{cond['cols']}",
                 time.perf_counter() - started, row["status"])
        counts[row["status"]] += 1
        if row["status"] == "ok":
            print(f"[{step}/{len(tasks)}] {cond['rows']}x{cond['cols']} w{cond['wear']} {cond['image_id']} "
                  f"{arm.label} rep {repetition}: AP {row['ap']:.3f} top1 {row['top1']:.3f} "
                  f"t_total {row['t_total']:.2f}s", flush=True)
    print(f"done: {counts}")


if __name__ == "__main__":
    main()
