"""Runner, input controls, and leakage tests (gate G4) on a synthetic instance."""

from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

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
    from jigsaw.config import load_config

    arms = all_arms(load_config(ROOT / "configs" / "pilot.yaml"))
    assert len(arms) == 17
    assert Arm("REF-ONLY", "none") not in arms
    assert Arm("GEO", "degraded") in arms


def test_runner_appends_rows_and_resumes(workspace: dict) -> None:
    results = workspace["base"] / "results.csv"
    args = ["--config", str(workspace["config"]), "--instances", str(workspace["instances"]),
            "--results", str(results), "--complexity", "0"]
    runner.main(args)
    with results.open(newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    assert len(rows) == 4  # 2 instances (wear 0, 1) x 2 built methods (GEO, COLOR)
    assert {r["status"] for r in rows} == {"ok"}
    assert {r["method"] for r in rows} == {"GEO", "COLOR"}
    assert set(rows[0]) == set(runner.COLUMNS)
    assert float(rows[0]["ap"]) > 0 and rows[0]["git_commit"]
    meta = json.loads(Path(str(results) + ".meta.json").read_text(encoding="utf-8"))
    assert "environment" in meta and meta["environment"]["cpu_count"]

    runner.main(args)  # resume: nothing new
    with results.open(newline="", encoding="utf-8") as f:
        assert len(list(csv.DictReader(f))) == 4
    assert len(completed_run_ids(results)) == 4


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


@pytest.mark.parametrize("method", ["GEO", "COLOR"])
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
