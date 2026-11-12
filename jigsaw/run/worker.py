"""One method run in a fresh process, seeing public data only (spec B4, B8).

The runner copies ``public/`` to a temporary folder and starts this worker
with that copy, the method name, and (for reference arms) a reference array
file. Before any method code runs, an audit hook is installed that refuses to
open or list any path under the ``--forbid`` folders (the instance's real
``private/`` and ``reference/``). The worker writes relation scores and
measurements to ``--out`` and never reads ground truth.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_FORBIDDEN: tuple[str, ...] = ()
_WATCHED_EVENTS = {"open", "os.listdir", "os.scandir", "os.mkdir", "os.remove", "shutil.copyfile",
                   "shutil.copytree", "os.rename"}


def _normalize(path) -> str | None:
    if isinstance(path, int):
        return None  # file descriptor
    try:
        text = os.fsdecode(os.fspath(path))
    except TypeError:
        return None
    return os.path.normcase(os.path.abspath(text))


def _audit(event: str, args: tuple) -> None:
    if event not in _WATCHED_EVENTS or not args:
        return
    for candidate in args[:2]:
        path = _normalize(candidate)
        if path is None:
            continue
        for forbidden in _FORBIDDEN:
            if path == forbidden or path.startswith(forbidden + os.sep):
                raise PermissionError(f"input control: method code may not access {candidate!r}")


def install_input_controls(forbidden: list[str]) -> None:
    global _FORBIDDEN
    _FORBIDDEN = tuple(os.path.normcase(os.path.abspath(p)) for p in forbidden)
    sys.addaudithook(_audit)


def run(public_dir: Path, instance_id: str, method: str, reference_path: Path | None) -> dict:
    import numpy as np

    from jigsaw.features.pieces import load_public_pieces
    from jigsaw.features.sides import extract_sides
    from jigsaw.methods.base import PuzzleInput
    from jigsaw.methods.registry import get_matcher

    matcher = get_matcher(method)
    t0 = time.perf_counter()
    pieces = load_public_pieces(public_dir)
    reference = np.load(reference_path) if reference_path is not None else None
    t1 = time.perf_counter()
    sides = extract_sides(pieces)
    t2 = time.perf_counter()
    if matcher.uses_reference and reference is None:
        raise ValueError(f"{method} needs a reference but the arm provides none")
    puzzle = PuzzleInput(instance_id, pieces, sides, reference if matcher.uses_reference else None)

    c0 = time.process_time()
    t3 = time.perf_counter()
    features = matcher.extract(puzzle)
    t4 = time.perf_counter()
    result = matcher.score(puzzle, features)
    t5 = time.perf_counter()
    c1 = time.process_time()

    scores = {key: np.asarray(result.relation_scores[key]) for key in ("right", "below")}
    return {
        "scores": scores,
        "measures": {
            "t_load": t1 - t0, "t_preprocess": t2 - t1, "t_extract": t4 - t3, "t_score": t5 - t4,
            "cpu_extract_score": c1 - c0,
            "candidates_scored": result.candidates_scored,
            "candidates_excluded": result.candidates_excluded,
            "extraction_failures": int(sides.failed.sum()),
            "feature_bytes": features.nbytes, "score_bytes": result.nbytes,
            "piece_ids": list(sides.piece_ids),
            "metadata": result.metadata,
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--method", required=True)
    parser.add_argument("--reference", type=Path)
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    install_input_controls(args.forbid)
    import numpy as np

    output = run(args.public, args.instance_id, args.method, args.reference)
    np.savez(args.out / "scores.npz", **output["scores"])
    (args.out / "measures.json").write_text(json.dumps(output["measures"]), encoding="utf-8")


if __name__ == "__main__":
    main()
