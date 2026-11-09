# Experiment Design Plan and Specification

**Scope:** Phase 1 jigsaw experiments (RQ1 and RQ2)
**Version:** 1.1, November 6, 2026 (scope reduced; see Decision Log D1 and D2)
**Audience:** the `Jigsaw – Coding` session
**Related files:** the handoff owns research decisions, this spec owns implementation, and `Decision Log.md` records every later change.

Values marked **[pilot]** are starting values that the pilot may change. Everything else is fixed unless a decision log entry changes it.

**v1.1 scope rule:** keep only what a research question or an existing paper claim needs. Out of scope for v1.1: TEX, HYB-GX, the 25% complexity level, 2 px wear, `tracemalloc`, interaction models, and a decision tree. Do not add them back without a decision log entry.

---

# Part A: Design Plan

## A1. What the experiment tests

**RQ1:** Which evidence works best, at what cost, under which puzzle conditions?
**RQ2:** Does a reference image change which strategy is preferable?

Each run gives one result for one method on one puzzle instance. All methods see identical pieces, so comparisons are paired.

## A2. Experimental factors

| Factor | Levels | Why |
|---|---|---|
| Evidence method | GEO, COLOR, GRAD, HYB-GC, HYB-FILTER | Answers RQ1; covers both visual measures the paper discusses and both hybrid forms |
| Reference | None, exact, degraded | Answers RQ2; degraded keeps the reference from being trivially decisive |
| Puzzle size | 6 × 9, 12 × 18, 20 × 30 | Three points are needed to show a scaling trend |
| Visual complexity | 0% and 50% solid-color overlay | Shows visual evidence dropping while geometry does not |
| Boundary wear | 0 and 1 px | Shows whether clean cuts flatter geometry |

The source image is the repeated unit. Every image appears in every condition, using the same cuts wherever the grid is the same.

**Arms:** 5 methods × 3 reference levels, plus REF-ONLY at 2 reference levels, gives 17 arms.
**Instances:** 3 sizes × 2 complexity levels × 2 wear levels gives 12 instances per image, or 240 instances across the 20 main images.

## A3. Puzzle sizes

Piece pitch stays fixed at 64 px, so puzzle size is not mixed up with piece resolution.

| Grid | Pieces (n) | Image size (px) | True pairs | Candidate pairs | Unique side comparisons | True pairs (%) | Dense pair scores at 64 bits (MB) |
|---|---:|---|---:|---:|---:|---:|---:|
| 6 × 9 | 54 | 384 × 576 | 93 | 1,431 | 5,724 | 6.50 | 0.01 |
| 12 × 18 | 216 | 768 × 1,152 | 402 | 23,220 | 92,880 | 1.73 | 0.19 |
| 20 × 30 | 600 | 1,280 × 1,920 | 1,150 | 179,700 | 718,800 | 0.64 | 1.44 |

## A4. Images

- **Source:** [DIV2K](https://data.vision.ee.ethz.ch/cvl/DIV2K/) train HR images, chosen for their 2K resolution. The set is limited to academic research, and image copyright stays with the original owners. Do not put the images in a public repository. Get permission or use different images before printing a source image in the paper.
- **Eligibility:** both image dimensions must cover 1,280 × 1,920 after an optional 90° rotation of the source. Check this during the pilot. If too few qualify, record the change and adjust the grid or pitch.
- **Selection:** sort eligible filenames, then take a seeded random sample. Do not choose images by eye.
- **Crop:** center crop to the grid's image size.
- **Pilot set:** 3 images, never reused in the main experiment. All tuning happens here.
- **Main set:** 20 images, enough for usable paired confidence intervals. Change it only through a decision log entry.

## A5. Reference-image design

The reference is one shared evidence channel, R. This avoids the two main threats to RQ2:

1. Giving each family its own use of the reference would make differences reflect the reference code, not the evidence.
2. A geometric method can use the reference only by reading piece pixels. This spec allows that in one place only, and labels GEO+R as a reference-assisted hybrid.

R locates each piece in the reference, then rewards pairs whose locations differ by one piece pitch in the expected direction.

| Reference level | Definition |
|---|---|
| None | The method receives no reference image or data derived from it. |
| Exact | The cropped image the pieces were cut from, after the complexity overlay. |
| Degraded | Gaussian blur (σ = 2 px), 0.5× downscale, JPEG quality 40, then gain 0.9 and offset +15. This approximates box art. **[pilot]** |

## A6. Pilot plan

Run the 3 pilot images across all 12 instance types and all 17 arms, with 5 timing repetitions. Section B10 defines the pass conditions. The pilot ends with a one-page summary and decision log entries that fix every **[pilot]** value.

## A7. Analysis plan

Five comparisons are fixed in advance. Each uses paired per-image differences in AP and top-1 within each condition, with the median difference and a 95% bootstrap confidence interval that resamples images.

| # | Comparison | Answers |
|---|---|---|
| C1 | COLOR vs. GEO, and GRAD vs. GEO | RQ1: visual against geometric evidence |
| C2 | HYB-GC and HYB-FILTER vs. the better of their single components | RQ1: whether combining helps |
| C3 | Each method with the reference vs. without it, at each reference level | RQ2: what the reference adds |
| C4 | Whether the method ordering changes across reference levels, measured by Kendall's τ between orderings | RQ2: whether suitability changes |
| C5 | Quality against `t_total` and peak memory, showing the Pareto front per condition | RQ1: trade-offs |

- Apply the Holm correction across all C1–C3 tests.
- Report C4 and C5 descriptively.
- Summarize each arm by condition with the median and interquartile range.
- Report results by condition. Do not fit interaction models.
- Give conditional strategy guidance. Do not build a decision tree.

---

# Part B: Implementation Specification

## B1. Environment

- Python 3.12, NumPy, SciPy, OpenCV, scikit-image, and scikit-learn, with exact versions pinned in a lockfile.
- The code goes in the user's GitHub repository, `jessiets/cmu_research_paper`, so it survives the session. The user makes all commits and pushes.
- Run all timed work on one machine, and record CPU, RAM, OS, and dependency versions in every results file.
- Set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, `MKL_NUM_THREADS`, and OpenCV threads to 1.

```text
jigsaw-matching/
├── configs/         pilot.yaml, main.yaml
├── data/            sources/ and instances/ (git-ignored)
├── jigsaw/
│   ├── generate/    curves.py, cut.py, wear.py, instance.py, third_party/
│   ├── features/    sides.py, geometric.py, color.py, gradient.py, reference.py
│   ├── methods/     base.py, registry.py, fusion.py
│   ├── evaluate/    metrics.py
│   └── run/         runner.py, measure.py
├── tests/
├── results/         raw CSV and JSON outputs
└── reports/         pilot_summary.md
```

## B2. Generator

Use a small custom generator built on Piecemaker's `interlockingnubs.py` curve code.

- **Source:** [Piecemaker](https://github.com/jkenlooper/piecemaker), commit `21f80208cc55caaac7f11d9a3ebbbce4aaa6d196`. Keep its LGPL-3.0 license notice with the vendored file.
- **Do not use** Piecemaker's `adjacent.py` for ground truth. It estimates neighbors from bounding boxes and mask overlap, and it can fall back to nearest pieces.
- **Do not use** CV-Jigsaw-Reconstruction. Its tabs all share one profile, its random shuffle is unseeded, its grid is square only, and it has no license file.

Steps:

1. Seed Python's `random` with `cut_seed = hash(image_id, grid)`. Here and elsewhere, `hash` means SHA-256 of the joined values, not Python's built-in `hash`, which changes between runs. Complexity and wear do not change the seed, so cuts stay the same across those levels.
2. Generate one curve per interior edge, and force each endpoint onto its grid corner.
3. Build each piece as a closed polygon from its four edges. Do not flood-fill rendered lines, because the first smoke test merged pieces that way.
4. Rasterize polygons to a label map. Assign every pixel to exactly one piece.
5. Fix or reject any piece with disconnected regions. The smoke test found these on varied cuts, and the cause has not been diagnosed.
6. Apply wear, then export the pieces.

## B3. Boundary wear

Apply wear independently per piece at generation time, so all methods see the same pieces and true neighbors stop fitting perfectly.

For wear level `a > 0`, compute this in a padded crop around the piece:

```text
sd    = signed distance to the piece boundary (positive inside)
f     = Gaussian-smoothed noise, sigma = pitch / 10, scaled to unit standard deviation
mask' = (sd - 1 + a * f) > 0
```

The −1 term removes about one pixel of material, and the noise makes the loss irregular. Keep only the largest connected component. Level 0 leaves the mask unchanged. Seed noise from `wear_seed = hash(image_id, grid, wear, piece_grid_index)`.

## B4. Instance format

```text
instances/<instance_id>/
├── public/
│   ├── pieces/p0000.png ...      # RGBA, tight crop with 2 px padding
│   └── piece_index.json          # piece IDs only
├── reference/
│   ├── exact.png
│   └── degraded.png
└── private/
    ├── truth.json                # grid position per piece, true pairs and their relations
    └── manifest.json             # source image, crop, seeds, grid, wear, overlay, curves, hashes
```

**Leakage rules:**

- Piece IDs come from a seeded permutation, so ID order reveals nothing.
- Filenames and PNG metadata contain no coordinates.
- Pixels outside the piece mask are zeroed, with alpha 0.
- Methods receive only `public/`, plus a reference array when the arm calls for one. They receive no paths to `private/`.
- Methods do not receive the grid dimensions. They derive piece pitch from side lengths, and reference scale as `sqrt(reference area / total piece area)`.

**Ground truth:** derive pairs only from grid positions. Pixel contact is not used, because pieces also touch diagonally at corners.

## B5. Shared preprocessing

All methods use one side extractor, so errors there do not separate the families.

1. Take the largest external contour from the alpha mask.
2. Find corners as the contour extrema of `x + y` and `x − y`.
3. Split the contour into sides T, R, B, and L, all ordered clockwise.
4. Resample each side to `K = 96` points by arc length. **[pilot]**
5. Mark a side flat if its largest deviation from its corner-to-corner chord is below 0.05 × pitch. **[pilot]** A flat side has no neighbor, so all its candidate relations are excluded.

The flat rule is required. Without it, flat border sides match each other almost perfectly, which pushed geometric average precision down to about 0.31 in the smoke test even though top-1 was 1.0 on 8 × 8.

Any extraction failure is logged per piece. The failed piece stays in the run and its sides are scored worst, so a method cannot gain from excluding hard pieces.

## B6. Pair and side rules

An unordered pair {A, B} has four relations under known orientation:

| Relation | A's side | B's side |
|---|---|---|
| B is right of A | R | L |
| B is left of A | L | R |
| B is below A | B | T |
| B is above A | T | B |

- A relation compares A's side with B's opposing side, with B's points reversed.
- **Pair score:** the best score across the four relations. Higher means more compatible.
- Excluded relations and filtered pairs get the worst possible score.
- Store the winning relation, so direction can be scored separately.

## B7. Methods

| ID | Evidence | Definition |
|---|---|---|
| GEO | Shape | Mean L1 distance between side profiles after subtracting the chord midpoint. |
| COLOR | Color | Mean squared CIELAB difference between facing boundary samples, following the form in Cho et al. (2010). |
| GRAD | Gradient | Gallagher's (2012) Mahalanobis gradient compatibility, adapted to curved sides by sampling layers along the inward normal. |
| HYB-GC | Shape + color | Rank fusion of GEO and COLOR. |
| HYB-FILTER | Shape, then gradient | Keep GEO's top 10 candidates per side, then score those with GRAD. Log how many true neighbors the filter removes. **[pilot]** |
| REF-ONLY | Reference | Location agreement alone. Defined only where a reference exists. |

**Boundary samples:** sample one pixel inward along the normal for COLOR. GRAD uses inward depths 1 and 2. All sampling uses pieces after wear.

**GRAD adaptation:** for each side, `G = p(d1) − p(d2)` gives a mean and covariance across the side. Add Gallagher's dummy gradients so the covariance can be inverted. Sum both directions, as in the original. Record this adaptation in the paper, because the original measure assumes straight edges.

**Rank fusion:** for each relation matrix, sum each candidate's row rank and column rank. Add those ranks across evidence channels with equal weights. Do not tune weights.

**Reference channel:**

1. Resize each piece and its mask by the derived reference scale.
2. Run masked `cv2.matchTemplate` with `TM_SQDIFF` over the reference.
3. Take the best position and convert it to piece coordinates.
4. Score a relation as the negative distance between the observed displacement and the expected one-pitch displacement.
5. Each +R arm rank-fuses R with that method's existing score channels.

**Reference caching:** compute piece locations once per instance and reference level, save them, and reuse them in every +R arm and REF-ONLY. Time this location step once per instance as `t_reference`, under the same timing rules. Report each +R arm's runtime as its own `t_total` plus `t_reference`, so the cost of using the reference is counted in full. Use FFT-based matching only if every reference arm uses it.

**Determinism and ties:** nothing else may be random. Ties are expected on solid regions. Average precision treats tied scores as one threshold, and top-1 counts a tie as `1 / tied candidates`.

## B8. Method interface

```python
@dataclass(frozen=True)
class PuzzleInput:
    instance_id: str
    pieces: Mapping[str, PieceImage]     # public data only
    sides: SideSet                       # output of shared preprocessing
    reference: np.ndarray | None         # None in the reference-free arm

@dataclass
class ScoreResult:
    relation_scores: Mapping[str, np.ndarray]  # higher is better; float64
    candidates_scored: int
    candidates_excluded: int
    metadata: dict

class Matcher(Protocol):
    name: str
    uses_reference: bool
    def extract(self, puzzle: PuzzleInput) -> Features: ...
    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult: ...
```

The runner, not the matcher, converts relation scores to pair scores. Evaluation lives in a separate module and is the only code that may read `private/`.

## B9. Metrics

### Matching quality

| Metric | Role | Definition |
|---|---|---|
| Average precision (AP) | Primary | Pair ranking against true unordered pairs, across all candidates. |
| Top-1 side accuracy | Primary | Share of non-border sides whose true partner ranks first. |
| Precision, recall, F1 | Secondary | Calculated on the top `E` ranked pairs, where `E` is the true pair count. The evaluator uses `E`; methods never see it. These three values are equal by construction, so report one value. |
| Accuracy | Secondary | At the same cut-off, shown next to the all-negative baseline. |
| Relation accuracy | Secondary | Among true pairs in the top `E`, the share with the correct direction. |
| Baselines | Context | Random ranking AP, which equals the base rate, and all-negative accuracy. |

### Runtime

Record wall-clock time with `time.perf_counter` and CPU time with `time.process_time`, for each phase:

| Phase | Includes |
|---|---|
| `load` | Reading files. Reported, but excluded from method runtime. |
| `preprocess` | The shared side extractor. Reported as shared cost. |
| `extract` | Method features. For +R arms, this excludes reference location, which is reported as `t_reference`. |
| `reference` | Locating pieces in the reference, measured once per instance and reference level. |
| `score` | Relation scores and fusion. |
| `total` | `extract` + `score`, plus `t_reference` for +R arms and REF-ONLY. The main runtime measure. |

Use 5 timing repetitions **[pilot]**, each in a fresh process, in randomized order. Report the median.

### Memory

Run memory in separate processes from timing, because profiling adds overhead.

- **Peak process memory:** peak RSS from `resource.getrusage`, minus a baseline taken after imports and loading. Convert units by platform.
- **Direct sizes:** `nbytes` of feature arrays and score arrays.
- Record the storage type (dense or filtered) and candidates scored in every run.

### Results schema

Each row in `results/*.csv` records: `run_id, git_commit, config_hash, instance_id, image_id, rows, cols, n, complexity, wear, reference, method, repetition, candidates_scored, candidates_excluded, ap, top1, f1_at_e, accuracy_at_e, relation_accuracy, filter_recall, extraction_failures, t_load, t_preprocess, t_extract, t_reference, t_score, t_total, cpu_total, cpu_utilization, peak_rss_delta, feature_bytes, score_bytes, status`.

Failed runs stay in the file, with `status` and the error.

## B10. Pilot pass conditions

| Gate | Check | Pass condition |
|---|---|---|
| G1 | Instance integrity | Exactly `n` connected pieces, with no overlaps or gaps at wear 0. Interior edges are present once each. |
| G2 | Ground truth | True pairs equal `2n − r − c`, with no diagonal pairs. |
| G3 | Reproducibility | The same seed produces byte-identical instances and identical scores. |
| G4 | Leakage | Reference-free methods run with `private/` and `reference/` removed. Results do not change when piece IDs are re-permuted, apart from tie-breaks. |
| G5 | Evaluator | Known-answer tests pass: an oracle scores 1.0, a reversed oracle scores near 0, and random AP matches the base rate. |
| G6 | Side extraction | At wear 0, at least 99% of corners fall within 2 px of the true corners, and flat-side counts match exactly. Report results for wear 1, and diagnose why 16 × 16 GEO top-1 was below 1.0 in the smoke test. |
| G7 | Reference | Exact and degraded inputs both run. Degraded localization falls below exact, or the degradation is strengthened. |
| G8 | Measurement | Coefficient of variation for `t_total` stays under 10%, or the repetition count is raised. |
| G9 | Practicality | The largest condition fits the time budget you set for the main run. |
| G10 | Complexity | The 50% overlay is reproducible, and its `uniform_fraction` is clearly higher than at 0%. |

**`uniform_fraction`:** the share of pixels in non-overlapping 16 × 16 luma blocks with a standard deviation below 4. **[pilot]**

**Overlay:** a seeded, connected solid-color region covering the target fraction of the cropped image. The color is that image's mean color.

The one-page pilot summary must include gate results, any **[pilot]** value changes, the estimated main-run runtime, and any paper-affecting changes.

## B11. Build order

1. Set up the repository, config system, and lockfile.
2. Build the generator, ground truth, and instance export. Pass G1–G3.
3. Build the evaluator with known-answer tests. Pass G5.
4. Build shared side extraction. Pass G6.
5. Add GEO and COLOR.
6. Add the runner, input controls, and leakage tests. Pass G4.
7. Add GRAD.
8. Add HYB-GC and HYB-FILTER.
9. Add reference levels, R, and location caching. Pass G7.
10. Add runtime and memory measurement. Pass G8.
11. Add complexity overlays. Pass G10.
12. Run the pilot, check G9, and write the one-page summary.
13. Stop for your approval before the main run.

## B12. Candidate repositories

| Repository | License | Decision | Reason |
|---|---|---|---|
| Piecemaker | LGPL-3.0 | **Use curve code only** | Per-edge varied cuts with seeding. The full tool could not be run here because `potrace` and `pixsaw` would not install. |
| CV-Jigsaw-Reconstruction | No license file | Reject | One tab shape, so almost no geometric signal. |
| Zolver | MIT | Reference only | Its `diff_match_edges` and `real_edge_compute` are readable, but they sit inside a solver with rotation and real-photo extraction. |
| PuzzleSolver | No license file | Reference only | C++ edge-shape solver built for scanned puzzles. |
| jigsaw-solver | No license file | Reference only | A single Colab notebook for real-photo input. |
| RL Puzzle Solver | CC0 | Reject | Its line-based compatibility and relaxation solver do not fit this pairwise comparison. |

All baselines are written fresh on one code path, which removes system-level differences between third-party solvers. Do not reuse code from repositories with no license.

## B13. Stop and ask

Stop and ask before you:

- Change a research question, factor, or method family.
- Drop a pilot gate or lower its pass condition.
- Use main-set images for tuning.
- Start the main run.
- Introduce learned methods or GPU execution.

Record every approved change in `Decision Log.md`.

---

# Appendix: Smoke-Test Evidence

I ran these quick checks to choose the design. **They are not study results and must not appear in the paper.** They used one cut seed, two standard images upscaled to 1,024 × 1,024, and throwaway code.

| Check | Result | Design consequence |
|---|---|---|
| Identical tab shapes vs. varied cuts, 16 × 16, GEO top-1 | 0.012 vs. 0.858 | Varied cuts are required |
| Flat-side rule, 8 × 8, GEO AP | About 0.31 without it, 0.999 with it | The rule is required |
| Flat-side detection | 32 of 32 and 64 of 64 correct on clean pieces | The simple rule is viable, but wear is untested |
| Wear 0, 1, 2 px, 16 × 16, GEO top-1 | 0.858, 0.108, 0.038 | Clean cuts flatter geometry |
| Wear 0, 1, 2 px, 16 × 16, COLOR top-1 | Astronaut 0.950, 0.850, 0.683; Coffee 0.996, 0.800, 0.658 | Visual evidence degrades more slowly here |
| 50% solid overlay, 16 × 16, COLOR AP | Astronaut 0.244 to 0.036 | The overlay creates the intended stress |
| 50% solid overlay, GEO AP | Unchanged | Geometry does not read pixels |
| Rank fusion, 16 × 16, clean, AP | 0.998–0.999, vs. GEO 0.807 and COLOR 0.244–0.695 | Hybrids merit a full test |
| Reference alone, 16 × 16, varied images, AP | Exact 0.987–1.0; degraded 0.879–0.883 | Exact references are close to trivial |
| Reference alone, 16 × 16, 50% solid, AP | Exact 0.557; degraded 0.372 | The reference is not universally sufficient |
