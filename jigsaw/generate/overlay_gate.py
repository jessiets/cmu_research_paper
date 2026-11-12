"""Gate G10: complexity overlay (spec B10; D11).

Pass condition: the 50% overlay is reproducible and its uniform_fraction is
clearly higher than at 0%. Checked for every pilot image and grid:
- Reproducible: regenerating the overlay instances gives byte-identical files,
  and the wear 0 and wear 1 instances share the same overlay record.
- Correct: the regrown region is one 4-connected component with exactly the
  target pixel count, and the exact reference holds the overlay color on it.
- "Clearly higher" is taken as at least MIN_INCREASE above the 0% instance
  (half the overlay's share of the image); every difference is reported.
"""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

import numpy as np
from scipy import ndimage

from jigsaw.config import load_config
from jigsaw.cvsetup import cv2
from jigsaw.generate.gates import compare_trees
from jigsaw.generate.instance import Condition, generate_image
from jigsaw.generate.overlay import grow_region, uniform_fraction
from jigsaw.generate.sources import image_id_for

MIN_INCREASE = 0.25
FOUR = ndimage.generate_binary_structure(2, 1)


def exact_image(instance_dir: Path) -> np.ndarray:
    return cv2.cvtColor(cv2.imread(str(instance_dir / "reference" / "exact.png")), cv2.COLOR_BGR2RGB)


def main() -> None:
    parser = argparse.ArgumentParser(description="Check gate G10 on generated instances.")
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--instances", type=Path, default=Path("data/instances"))
    parser.add_argument("--report", type=Path, default=Path("results/gates/step11_g10.json"))
    args = parser.parse_args()
    config = load_config(args.config)
    levels = [c for c in config.complexity_levels if c > 0]

    with tempfile.TemporaryDirectory() as tmp:
        regenerated = Path(tmp)
        for name in config.source_images:
            generate_image(Path(config.source_dir) / name, regenerated, config.grids, levels,
                           config.wear_levels_px, config.pitch_px)
        rows_out = []
        for name in config.source_images:
            image_id = image_id_for(name)
            for rows, cols in config.grids:
                base = args.instances / Condition(image_id, rows, cols, 0, 0).instance_id
                uf0 = uniform_fraction(exact_image(base))
                for level in levels:
                    ids = [Condition(image_id, rows, cols, level, w).instance_id for w in config.wear_levels_px]
                    trees = [compare_trees(args.instances / i, regenerated / i) for i in ids]
                    identical = all(t["files"] and not (t["differing"] or t["only_in_first"] or t["only_in_second"])
                                    for t in trees)
                    overlays = [json.loads((args.instances / i / "private" / "manifest.json")
                                           .read_text(encoding="utf-8"))["overlay"] for i in ids]
                    shared = all(o == overlays[0] for o in overlays)
                    ov = overlays[0]
                    image = exact_image(args.instances / ids[0])
                    mask, _ = grow_region(image.shape[0], image.shape[1], ov["target_pixels"], ov["seed"])
                    components = ndimage.label(mask, structure=FOUR)[1]
                    colored = bool(np.all(image[mask] == np.array(ov["color_rgb"], dtype=np.uint8)))
                    uf = uniform_fraction(image)
                    entry = {"image_id": image_id, "grid": f"{rows}x{cols}", "complexity": level,
                             "uniform_fraction_0": uf0, "uniform_fraction": uf, "increase": uf - uf0,
                             "coverage": int(mask.sum()) / mask.size, "pixels": int(mask.sum()),
                             "target_pixels": ov["target_pixels"], "components": int(components),
                             "overlay_color_on_mask": colored, "byte_identical_on_regeneration": identical,
                             "shared_across_wear": shared}
                    entry["pass"] = (identical and shared and components == 1 and colored
                                     and int(mask.sum()) == ov["target_pixels"] and uf - uf0 >= MIN_INCREASE)
                    rows_out.append(entry)
                    print(f"{image_id} {rows}x{cols:<3} uniform_fraction {uf0:.3f} -> {uf:.3f} "
                          f"(+{uf - uf0:.3f})  coverage {entry['coverage']:.4f}  components {components}  "
                          f"identical {identical}  shared {shared}  {'PASS' if entry['pass'] else 'FAIL'}")

    report = {"G10_pass": all(r["pass"] for r in rows_out), "min_increase": MIN_INCREASE,
              "note": "'clearly higher' operationalized as an increase of at least 0.25 (half the overlay share)",
              "checks": rows_out}
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print(f"G10: {'PASS' if report['G10_pass'] else 'FAIL'} ({len(rows_out)} image-grid overlays)")


if __name__ == "__main__":
    main()
