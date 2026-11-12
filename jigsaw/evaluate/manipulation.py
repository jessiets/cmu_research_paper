"""Complexity-manipulation strength per instance (D15).

For every instance of a config, reports ``uniform_fraction`` of the image the
pieces were cut from (``reference/exact.png``), and for overlay instances the
gain over the matching 0% instance, both absolute and as the share of
previously non-uniform area the overlay made uniform:

    relative_gain = (uf_overlay - uf_0) / (1 - uf_0)

This lets the analysis show how strong the complexity manipulation was for
each image. It reads instance files only (evaluator side), never method code.
"""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from jigsaw.config import load_config
from jigsaw.cvsetup import cv2
from jigsaw.generate.instance import Condition
from jigsaw.generate.overlay import uniform_fraction
from jigsaw.generate.sources import image_id_for

COLUMNS = ["instance_id", "image_id", "rows", "cols", "complexity", "wear", "uniform_fraction",
           "uniform_fraction_at_0", "absolute_gain", "relative_gain"]


def instance_uniform_fraction(instance_dir: Path) -> float:
    bgr = cv2.imread(str(instance_dir / "reference" / "exact.png"))
    return uniform_fraction(cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB))


def main() -> None:
    parser = argparse.ArgumentParser(description="Report complexity-manipulation strength per instance.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--out", type=Path, help="default: results/<profile>_uniform_fraction.csv")
    args = parser.parse_args()
    config = load_config(args.config)
    out = args.out or Path(f"results/{config.profile}_uniform_fraction.csv")
    index = json.loads((args.instances / "index.json").read_text(encoding="utf-8"))

    rows = []
    for name in config.source_images:
        image_id = image_id_for(name)
        for r, c in config.grids:
            base_id = Condition(image_id, r, c, 0, 0).instance_id
            base = instance_uniform_fraction(args.instances / base_id) if base_id in index else None
            for level in config.complexity_levels:
                for wear in config.wear_levels_px:
                    iid = Condition(image_id, r, c, level, wear).instance_id
                    if iid not in index:
                        continue
                    uf = instance_uniform_fraction(args.instances / iid)
                    gain = None if base is None or level == 0 else uf - base
                    rel = None if gain is None or base >= 1 else gain / (1 - base)
                    rows.append({"instance_id": iid, "image_id": image_id, "rows": r, "cols": c,
                                 "complexity": level, "wear": wear, "uniform_fraction": round(uf, 6),
                                 "uniform_fraction_at_0": "" if base is None else round(base, 6),
                                 "absolute_gain": "" if gain is None else round(gain, 6),
                                 "relative_gain": "" if rel is None else round(rel, 6)})
    out.parent.mkdir(parents=True, exist_ok=True)
    with out.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    for row in rows:
        if row["complexity"] and row["wear"] == 0:
            print(f"{row['image_id']} {row['rows']}x{row['cols']:<3} uf {row['uniform_fraction_at_0']:.3f} -> "
                  f"{row['uniform_fraction']:.3f}  gain {row['absolute_gain']:+.3f}  relative {row['relative_gain']:.3f}")
    print(f"wrote {out} ({len(rows)} instances)")


if __name__ == "__main__":
    main()
