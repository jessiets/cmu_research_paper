# Jigsaw Matching Experiment

Controlled experiment for the paper *From Jigsaw Puzzles to General Fragment Matching*. It compares geometric, visual and hybrid pairwise-matching strategies for jigsaw pieces, with and without a reference image. Each strategy is measured on match quality, runtime and peak memory.

- **Puzzles:** generated from DIV2K images. 3 grid sizes (6 × 9, 12 × 18 and 20 × 30 pieces), 2 levels of visual complexity (0% and 50% flat overlay) and 2 levels of edge wear (0 and 1 px). The generator records the true neighbors.
- **Methods:**
  - Five strategies: GEO (piece shape), COLOR, GRAD (color gradients), HYB-GC (rank fusion of GEO and COLOR) and HYB-FILTER (GEO shortlist rescored by GRAD).
  - Each strategy runs three ways: with no reference, with an exact reference image (+R) and with a degraded one.
  - REF-ONLY runs with each reference level.
- **Analysis:** planned comparisons C1–C5. Paired Wilcoxon tests with Holm correction and bootstrap CIs, plus Pareto fronts for cost.

Results: [reports/main_results_summary.md](reports/main_results_summary.md). Design: [docs/spec.md](docs/spec.md). Changes after the spec: [docs/decision_log.md](docs/decision_log.md).

## Layout

| Path | Contents |
|---|---|
| `jigsaw/generate/` | Puzzle generator, overlays, wear, gates G1–G3 and G10 |
| `jigsaw/features/`, `jigsaw/methods/` | Shared side extraction and the matching methods |
| `jigsaw/evaluate/` | Evaluator: the only code that reads the ground truth |
| `jigsaw/run/` | Resumable runner, isolated workers, timing and memory measurement |
| `jigsaw/analysis/` | Statistics and figures |
| `configs/` | `pilot.yaml` (3 images) and `main.yaml` (20 images) |
| `results/`, `reports/` | Raw results CSVs, gate reports and analysis output |

## Reproduce

Requirements:
- Python 3.13 and [uv](https://docs.astral.sh/uv/). The dependencies are pinned in `uv.lock`.
- Windows. Peak memory is read from the Windows peak working set.

The commands below use PowerShell.

1. **Install:**
   ```
   uv sync --extra dev
   .venv\Scripts\python -m pytest -q
   ```
2. **Get the data.** Download the DIV2K train HR set from https://data.vision.ee.ethz.ch/cvl/DIV2K/ and put the 800 PNGs in `data/sources/` (`data/sources/0001.png` …). DIV2K is for academic research only. `data/` is git-ignored, so never commit images.
3. **Generate the puzzles** (~25 min for the main set):
   ```
   .venv\Scripts\python -m jigsaw.generate.instance --config configs/main.yaml
   .venv\Scripts\python -m jigsaw.evaluate.manipulation --config configs/main.yaml
   ```
   The image selection is seeded and already fixed in the configs. To redraw it, run `python -m jigsaw.generate.sources`.
4. **Run the experiment** (~19 h in total). Before the timing pass, close other programs and keep the machine plugged in. If a pass is interrupted, rerun the same command and it resumes.
   ```
   $untimed = "0407 0016 0473 0288 0354 0737 0587 0217 0633 0459".Split()
   $timed   = "0510 0186 0479 0223 0506 0173 0730 0178 0091 0525".Split()
   .venv\Scripts\python -m jigsaw.run.runner --config configs/main.yaml --results results/main_quality.csv --mode quality --allow-main --images $untimed
   .venv\Scripts\python -m jigsaw.run.runner --config configs/main.yaml --results results/main_timing.csv  --mode timing  --allow-main --images $timed
   .venv\Scripts\python -m jigsaw.run.runner --config configs/main.yaml --results results/main_memory.csv  --mode memory  --allow-main --images $timed
   ```
   Quality is measured on all 20 images. Runtime (5 repetitions) and memory are measured on the first 10 (decision D18).
5. **Check and analyze:**
   ```
   .venv\Scripts\python -m jigsaw.run.timing_gate --results results/main_timing.csv --report results/gates/main_g8.json
   .venv\Scripts\python -m jigsaw.analysis.analyze --timing results/main_timing.csv --quality results/main_quality.csv --memory results/main_memory.csv --uniform results/main_uniform_fraction.csv --out reports/main_analysis --label "Main run"
   ```

Quality scores are deterministic and should match exactly. Runtime and memory depend on the machine.

For the pilot, use `configs/pilot.yaml` with the runner's timing and memory modes, then run `python -m jigsaw.run.pilot_summary`.

## Credits

- **Images:** DIV2K. E. Agustsson and R. Timofte, "NTIRE 2017 Challenge on Single Image Super-Resolution: Dataset and Study," CVPR Workshops, 2017.
- **Piece-cut curves:** vendored from [Piecemaker](https://github.com/jkenlooper/piecemaker) v0.8.1 by Jake Hickenlooper (LGPL-3.0-or-later). See `jigsaw/generate/third_party/piecemaker/`.
