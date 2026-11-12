"""Runner, input controls, and leakage tests (gate G4) on a synthetic instance."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from jigsaw.config import load_config
from jigsaw.generate.instance import generate_image, update_index
from jigsaw.run import runner
from jigsaw.run.leakage import canary, check, static_checks
from jigsaw.run.runner import Arm, all_arms, completed_run_ids
from tests.test_generate import synthetic_source

ROOT = Path(__file__).parents[1]


@pytest.fixture(scope="module")
def workspace(tmp_path_factory: pytest.TempPathFactory) -> dict:
    base = tmp_path_factory.mktemp("runner")
    sources = base / "sources"
    sources.mkdir()
    synthetic_source(sources / "9999.png")
    instances = base / "instances"
    entries = generate_image(sources / "9999.png", instances, [(3, 4)], [0], [0, 1], 64)
    update_index(instances, entries)
    text = (ROOT / "configs" / "pilot.yaml").read_text(encoding="utf-8")
    text = text.replace("source_dir: data/sources", f"source_dir: {sources.as_posix()}")
    text = text.replace("  - 0269.png\n  - 0251.png\n  - 0731.png\n",
                        "  - 9999.png\n  - 9998.png\n  - 9997.png\n")
    text = text.replace("  - [6, 9]\n  - [12, 18]\n  - [20, 30]\n", "  - [3, 4]\n")
    config = base / "pilot.yaml"
    config.write_text(text, encoding="utf-8")
    return {"base": base, "instances": instances, "config": config, "entries": entries}


def test_seventeen_arms() -> None:
    arms = all_arms(load_config(ROOT / "configs" / "pilot.yaml"))
    assert len(arms) == 17
    assert Arm("REF-ONLY", "none") not in arms
    assert Arm("GEO", "degraded") in arms


def test_runner_appends_rows_and_resumes(workspace: dict) -> None:
    results = workspace["base"] / "results.csv"
    args = ["--config", str(workspace["config"]), "--instances", str(workspace["instances"]),
            "--results", str(results), "--complexity", "0", "--cache", str(workspace["base"] / "cache")]
    runner.main(args)
    with results.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    arms = [a for a in all_arms(load_config(workspace["config"])) if runner.arm_is_built(a)]
    built = len(arms)
    assert built == 17
    assert len(rows) == 2 * built  # 2 instances (wear 0, 1) x 17 arms
    assert {r["status"] for r in rows} == {"ok"}, [r["error"] for r in rows if r["error"]]
    ref_rows = [r for r in rows if r["reference"] != "none"]
    assert all(float(r["t_reference"]) > 0 for r in ref_rows)
    assert all(float(r["t_total"]) >= float(r["t_reference"]) for r in ref_rows)
    assert len(list((workspace["base"] / "cache").glob("*.npz"))) == 4  # 2 instances x 2 levels, reused
    assert set(rows[0]) == set(runner.COLUMNS)
    assert float(rows[0]["ap"]) > 0 and rows[0]["git_commit"]
    meta = json.loads(Path(str(results) + ".meta.json").read_text(encoding="utf-8"))
    assert "environment" in meta and meta["environment"]["cpu_count"]

    runner.main(args)  # resume: nothing new
    with results.open(newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 2 * built
    assert len(completed_run_ids(results)) == 2 * built


def test_failed_run_keeps_its_row(workspace: dict, tmp_path: Path) -> None:
    broken = tmp_path / workspace["entries"][0]["instance_id"]
    shutil.copytree(workspace["instances"] / broken.name, broken)
    (broken / "public" / "pieces" / sorted((broken / "public" / "pieces").iterdir())[0].name).write_bytes(b"x")
    cond = workspace["entries"][0]
    row = runner.execute(broken, cond, Arm("GEO", "none"), 0, {"git_commit": "t", "config_hash": "t"})
    assert row["status"] == "failed" and row["error"]
    results = tmp_path / "r.csv"
    runner.append_row(results, row)
    with results.open(newline="", encoding="utf-8") as f:
        saved = list(csv.DictReader(f))
    assert saved[0]["status"] == "failed" and not completed_run_ids(results)


def test_main_config_needs_explicit_approval() -> None:
    with pytest.raises(SystemExit, match="allow-main"):
        runner.main(["--config", str(ROOT / "configs" / "main.yaml"), "--results", "unused.csv"])


@pytest.mark.parametrize("method", ["GEO", "COLOR", "GRAD", "HYB-GC", "HYB-FILTER"])
def test_g4_stripped_and_permuted_runs_match(workspace: dict, method: str) -> None:
    instance = workspace["instances"] / workspace["entries"][0]["instance_id"]
    result = check(instance, Arm(method, "none"))
    assert result["pass"], result


def test_g4_canary_blocks_private_access(workspace: dict) -> None:
    instance = workspace["instances"] / workspace["entries"][0]["instance_id"]
    assert canary(instance)["pass"]


def test_g4_static_checks(workspace: dict) -> None:
    instance = workspace["instances"] / workspace["entries"][0]["instance_id"]
    result = static_checks(instance)
    assert not result["unexpected_public_files"] and not result["png_text_chunks"]


def test_worker_blocks_reference_reads_for_reference_free_arm(workspace: dict, tmp_path: Path) -> None:
    instance = workspace["instances"] / workspace["entries"][0]["instance_id"]
    code = ("import sys; from jigsaw.run.worker import install_input_controls; "
            "install_input_controls([sys.argv[1]]); "
            "from jigsaw.cvsetup import cv2; import numpy as np; open(sys.argv[2], 'rb')")
    done = subprocess.run([sys.executable, "-c", code, str(instance / "reference"),
                           str(instance / "reference" / "exact.png")], capture_output=True, text=True)
    assert done.returncode != 0 and "input control" in done.stderr


def test_timing_and_memory_modes(workspace: dict) -> None:
    from jigsaw.run.timing_gate import group_cv

    common = ["--config", str(workspace["config"]), "--instances", str(workspace["instances"]),
              "--complexity", "0", "--cache", str(workspace["base"] / "cache2"),
              "--methods", "GEO", "REF-ONLY", "--references", "none", "exact"]
    timing = workspace["base"] / "timing.csv"
    runner.main(common + ["--results", str(timing), "--mode", "timing", "--repetitions", "2"])
    with timing.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    # 2 instances x (GEO none, GEO+R exact, REF-ONLY exact) x 2 repetitions
    assert len(rows) == 12 and {r["status"] for r in rows} == {"ok"}
    ref_rows = runner.reference_results_path(timing)
    with ref_rows.open(newline="", encoding="utf-8") as f:
        locate_rows = list(csv.DictReader(f))
    assert len(locate_rows) == 4  # 2 instances x exact x 2 repetitions
    medians = runner.median_reference_times(ref_rows)
    for r in rows:
        if r["reference"] == "exact":
            assert float(r["t_reference"]) == pytest.approx(medians[(r["instance_id"], "exact")])
    assert all(g["reps"] == 2 for g in group_cv(timing, ("instance_id", "method", "reference"), "t_total").values())

    memory = workspace["base"] / "memory.csv"
    runner.main(common + ["--results", str(memory), "--mode", "memory"])
    with memory.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 6 and all(int(r["peak_rss_delta"]) >= 0 for r in rows)
    assert all(r["peak_rss_delta"] != "" for r in rows)


def test_peak_memory_reads_the_os() -> None:
    # In a fresh process: the test process itself may already have peaked higher.
    code = ("from jigsaw.run.measure import peak_memory_bytes; before = peak_memory_bytes(); "
            "block = bytearray(256 * 1024 * 1024); block[::4096] = bytes(len(block[::4096])); "
            "block[::4096] = b'x' * len(block[::4096]); print(peak_memory_bytes() - before)")
    done = subprocess.run([sys.executable, "-c", code], capture_output=True, text=True, check=True)
    assert int(done.stdout.strip()) >= 128 * 1024 * 1024
