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

from jigsaw.run.measure import peak_memory_bytes

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


def run(public_dir: Path, instance_id: str, method: str, with_reference: bool,
        locations_path: Path | None, measure_memory: bool = False) -> dict:
    """Score one arm. Reference arms receive cached piece locations, never the image."""
    import numpy as np

    from jigsaw.features.pieces import load_public_pieces
    from jigsaw.features.sides import extract_sides
    from jigsaw.methods.base import PuzzleInput
    from jigsaw.methods.registry import get_matcher

    matcher = get_matcher(method, reference=with_reference)
    t0 = time.perf_counter()
    pieces = load_public_pieces(public_dir)
    locations = None
    if matcher.uses_reference:
        if locations_path is None:
            raise ValueError(f"{matcher.name} needs cached reference locations")
        with np.load(locations_path) as cached:
            locations = cached["locations"]
    t1 = time.perf_counter()
    sides = extract_sides(pieces)
    t2 = time.perf_counter()
    puzzle = PuzzleInput(instance_id, pieces, sides, None, locations)
    baseline = peak_memory_bytes() if measure_memory else None  # after imports and loading

    c0 = time.process_time()
    t3 = time.perf_counter()
    features = matcher.extract(puzzle)
    t4 = time.perf_counter()
    result = matcher.score(puzzle, features)
    t5 = time.perf_counter()
    c1 = time.process_time()
    peak_delta = max(peak_memory_bytes() - baseline, 0) if measure_memory else None

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
            "peak_rss_delta": peak_delta,
        },
    }


def locate(public_dir: Path, reference_path: Path, measure_memory: bool = False) -> dict:
    """Locate every piece in the reference; times only the location step (t_reference)."""
    import numpy as np

    from jigsaw.features.pieces import load_public_pieces
    from jigsaw.features.reference import locate_pieces
    from jigsaw.features.sides import extract_sides

    pieces = load_public_pieces(public_dir)
    reference = np.load(reference_path)
    sides = extract_sides(pieces)
    baseline = peak_memory_bytes() if measure_memory else None
    c0 = time.process_time()
    t0 = time.perf_counter()
    found = locate_pieces(pieces, sides, reference)
    t1 = time.perf_counter()
    c1 = time.process_time()
    peak_delta = max(peak_memory_bytes() - baseline, 0) if measure_memory else None
    return {"arrays": {"locations": found["locations"], "match_xy": found["match_xy"]},
            "measures": {"t_reference": t1 - t0, "cpu_reference": c1 - c0, "scale": found["scale"],
                         "piece_ids": list(sides.piece_ids), "pitch": sides.pitch,
                         "peak_rss_delta": peak_delta}}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public", type=Path, required=True)
    parser.add_argument("--instance-id", required=True)
    parser.add_argument("--task", choices=("score", "locate"), default="score")
    parser.add_argument("--method")
    parser.add_argument("--with-reference", action="store_true")
    parser.add_argument("--reference", type=Path, help="reference array (.npy), locate task only")
    parser.add_argument("--locations", type=Path, help="cached locations (.npz), reference arms only")
    parser.add_argument("--forbid", action="append", default=[])
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--measure-memory", action="store_true",
                        help="memory run: record peak memory (timings from this run are not used)")
    args = parser.parse_args()

    install_input_controls(args.forbid)
    import numpy as np

    if args.task == "locate":
        output = locate(args.public, args.reference, args.measure_memory)
        np.savez(args.out / "locations.npz", **output["arrays"])
    else:
        output = run(args.public, args.instance_id, args.method, args.with_reference, args.locations,
                     args.measure_memory)
        np.savez(args.out / "scores.npz", **output["scores"])
    (args.out / "measures.json").write_text(json.dumps(output["measures"]), encoding="utf-8")


if __name__ == "__main__":
    main()
