# Handoff: add the experiment's design and results to the paper

**Your task:** update `docs/paper_submission.md` with a short account of how the experiment was run and what it found. Keep it brief. The user will expand it later. Edit the paper file in place. The user handles all git commits; never run git commands that change history.

This session is the **paper session**. The experiment is finished, and its code, data and results are frozen. Do not change anything under `jigsaw/`, `configs/`, `results/` or `reports/`, and do not rerun anything.

## Read first, in this order

1. **`docs/paper_submission.md`:** the current paper. Sections 4.2–4.5 are still written in the future tense ("will"), Section 5 is a placeholder, and Section 6 is empty.
2. **`reports/main_results_summary.md`:** the main findings and caveats. This is the primary source for Section 5.
3. **`docs/paper_updates.md`:** rows P1–P34, every change the experiment requires in the paper, including citations. Work from the **Pending** rows.
4. **`reports/main_analysis/analysis.md`:** full result tables. Take exact numbers from here; `tests.csv` and `descriptive.csv` have the rest.
5. **`docs/decision_log.md`:** D1–D19, the reasons behind each design choice, if you need detail for Methods.
6. **`docs/handoff.txt` and `docs/spec.md`:** background on the scope and design, only if needed. In `handoff.txt`, the dated blocks at the top override the numbered sections below them.

## What to write (short)

### Methods (Sections 4.2–4.5)

Change "will" to past tense where the step was done, and describe only what was actually done. Aim for about 300–500 words of changes in total.

- **Data (4.2).** Cover:
  - The images: 23 DIV2K training images at high resolution, selected by seeded random draw: 3 for the pilot and 20 for the main study (P9, P16).
  - The generator: the piece-cut curves from Piecemaker (P13).
  - The ground truth, which comes from the generator.
  - Add the DIV2K and Piecemaker citations to the References (P11, P13).
  - Do not print any DIV2K image (P12).
- **Conditions (4.3).** Cover:
  - The 12 conditions: grids of 6 × 9, 12 × 18 and 20 × 30 pieces, complexity of 0% or 50% (a flat overlay region), and wear of 0 or 1 px (P2, P17).
  - The methods: GEO (shape), COLOR, GRAD (gradients), HYB-GC (rank fusion of GEO and COLOR) and HYB-FILTER (GEO shortlist, then GRAD). Each runs without a reference, with an exact reference image (+R) and with a degraded one, plus REF-ONLY (P21, P24, P23).
  - The input controls (P22).
  - Measurement: runtime is the median of 5 repetitions on 10 of the 20 images, and quality uses all 20 (P29, P30). Remove `tracemalloc` (P3). Peak memory is the Windows peak working set (P23).
- **Analysis (4.4).** The metrics are AP (main) and top-1 side accuracy (P18). Comparisons C1–C5 use the Wilcoxon signed-rank test with Holm correction and bootstrap CIs (P4, P27).
- **Threats (4.5).** Add brief versions of P19 and P28 (low cut variety), P25 (reference scale) and P26 (overlay strength varies). Keep the existing text.
- **Figure 1's caption** says details "will be specified after the pilot". Update it.
- **Other short consistency fixes:**
  - P1: texture was not tested (Section 2.2).
  - P6: change "framework" wording to conditional guidance (Section 1.4).

  Skip any other Pending row that needs a long rewrite, and list it for the user.

### Results (Section 5)

Replace the placeholder. Aim for about 400–600 words plus the figures and one table, organized by comparison:

- **C1, visual vs. geometric evidence.** Which evidence wins depends on the condition:
  - Geometry wins on clean cuts and under 50% complexity.
  - Visual evidence wins under 1 px of wear.
- **C2, hybrids.** Hybrids usually beat their better component, but lose when one component carries no information.
- **C3, the reference.** It helps most where a method's own evidence fails, and can hurt.
- **C4, rankings.** Method rankings change when a reference is added.
- **C5, runtime.** GEO is the cheapest arm and on the Pareto front everywhere. Exact-reference arms take about 60 s per 20 × 30 puzzle.
- **Say plainly** that peak-memory results are pending (the memory pass has not run yet) and that these are initial results.
- **Mention briefly** that AP and top-1 diverge at 50% complexity (P32).

### Discussion (Section 6)

Write a single short paragraph in 6.1 that answers RQ1 and RQ2 at the level of conditional guidance: which evidence to use under which conditions. Leave 6.2–6.4 empty for now.

## Figures and table to add

All figures are in `reports/main_analysis/`. Insert each one as a Markdown image link with a caption, and keep the file paths, because the user will place the images in Word.

| Paper figure | File | Shows | Caption should say |
|---|---|---|---|
| Figure 2 | `c1_ap.png` | C1: COLOR − GEO and GRAD − GEO, AP difference per condition | Median paired difference with 95% bootstrap CI over 20 images; filled = significant after Holm. |
| Figure 3 | `c2_ap.png` | C2: each hybrid minus its better component | Same encoding. The baseline is the component with the higher median in that condition. |
| Figure 4 | `c3_ap.png` | C3: each method +R minus the method, exact and degraded reference | Same encoding. Orange = exact reference, green = degraded reference. |
| Figure 5 | `c5_pareto_time.png` | C5: median AP against median runtime (log scale), one panel per condition | Median AP over 20 images; runtime over the 10 timed images; labeled points are on the Pareto front. |

- **The C5 figure** has some overlapping labels in its busiest panels. Leave it as it is; the user knows.
- **The top-1 figures** (`*_top1.png`) are not needed for now.
- **Table 1** (one table only): median AP of the five reference-free methods plus REF-ONLY (exact) in each of the 12 conditions, copied exactly from the "Median AP by arm and condition" table in `reports/main_analysis/analysis.md`. Put conditions as rows and arms as columns so it fits the page.

## Rules

- **Report results honestly.** Where a result contradicts what the paper expected, say so and update the claim. Do not soften results or hide them.
- **Use only numbers** from `reports/main_results_summary.md` or `reports/main_analysis/`. Never use the spec appendix's smoke-test numbers or any pilot number as a result (P15).
- **Do not change** the research questions or expand the scope.
- **Do not** add statistics or analyses that the reports don't contain.
- **When finished:**
  - Set the Status to `Done` for each `docs/paper_updates.md` row you applied.
  - List the rows you left Pending, with a one-line reason each.
  - Summarize your edits to the paper by section.
