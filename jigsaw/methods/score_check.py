"""G3, scores half: the same seed gives identical scores (spec B10).

Regenerates every pilot instance into a temporary folder, then scores the
original and the regenerated copy in two separate fresh processes and
compares SHA-256 hashes of the raw float64 score bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import tempfile
from pathlib import Path

from jigsaw.config import load_config
from jigsaw.generate.instance import generate_image
from jigsaw.methods.base import load_puzzle
from jigsaw.methods.registry import available, get_matcher
from jigsaw.relations import RELATION_KEYS


def score_hashes(instances: Path, instance_ids: list[str], methods: list[str]) -> dict:
    out: dict[str, dict[str, str]] = {}
    for iid in instance_ids:
        puzzle = load_puzzle(instances / iid / "public", iid)
        out[iid] = {}
        for name in methods:
            matcher = get_matcher(name)
            result = matcher.score(puzzle, matcher.extract(puzzle))
            digest = hashlib.sha256()
            for key in RELATION_KEYS:
                digest.update(result.relation_scores[key].tobytes())
            out[iid][name] = digest.hexdigest()
    return out


def _hash_in_subprocess(instances: Path, ids: list[str], methods: list[str]) -> dict:
    code = ("import json, sys; from pathlib import Path; "
            "from jigsaw.methods.score_check import score_hashes; "
            "a = json.loads(sys.argv[1]); "
            "print(json.dumps(score_hashes(Path(a['dir']), a['ids'], a['methods'])))")
    arg = json.dumps({"dir": str(instances), "ids": ids, "methods": methods})
    done = subprocess.run([sys.executable, "-c", code, arg], capture_output=True, text=True, check=True)
    return json.loads(done.stdout.strip().splitlines()[-1])


def main() -> None:
    parser = argparse.ArgumentParser(description="Check that regenerated instances give identical scores.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--complexity", type=int, nargs="*", default=[0])
    parser.add_argument("--report", type=Path, default=Path("results/gates/step5_g3_scores.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    wanted = {Path(name).stem for name in config.source_images}
    index = json.loads((args.instances / "index.json").read_text(encoding="utf-8"))
    ids = sorted(iid for iid, c in index.items()
                 if c["image_id"] in wanted and c["complexity"] in args.complexity)
    methods = list(available())

    first = _hash_in_subprocess(args.instances, ids, methods)
    with tempfile.TemporaryDirectory() as tmp:
        regenerated = Path(tmp)
        for name in config.source_images:
            generate_image(Path(config.source_dir) / name, regenerated, config.grids, args.complexity,
                           config.wear_levels_px, config.pitch_px)
        second = _hash_in_subprocess(regenerated, ids, methods)

    mismatches = [(iid, m) for iid in ids for m in methods if first[iid][m] != second[iid][m]]
    report = {"G3_scores_pass": not mismatches, "instances": len(ids), "methods": methods,
              "comparisons": len(ids) * len(methods), "mismatches": mismatches, "hashes": first}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"G3 scores: {'PASS' if not mismatches else 'FAIL'} - {report['comparisons']} score sets "
          f"({len(ids)} instances x {', '.join(methods)}) identical across regeneration and processes"
          if not mismatches else f"G3 scores: FAIL - mismatches: {mismatches}")


if __name__ == "__main__":
    main()
