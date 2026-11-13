# Main results: initial summary

**Status:** initial results from the main run (2026-11-13). Quality: 20 DIV2K images. Runtime: 10 of them at 5 repetitions (D18). Peak memory is pending, because the memory pass has not been run yet, so the memory side of C5 is not reported here. Full tables: `reports/main_analysis/analysis.md` and its CSVs. Figures: `reports/main_analysis/*.png`.

**Design:** 12 conditions:
- 3 grids: 6 × 9, 12 × 18 and 20 × 30 pieces
- 2 complexity levels: 0% and 50% overlay
- 2 wear levels: 0 and 1 px

Each condition has 17 arms (5 methods × 3 reference levels, plus REF-ONLY at the exact and degraded levels). Every run completed: 2,040 quality runs and 10,200 timing runs, with no failures, all on one code commit. Comparisons use paired per-image differences: the median difference, a 95% bootstrap CI and a Wilcoxon signed-rank test, Holm-corrected across all 336 C1–C3 tests. AP is the main metric. Top-1 side accuracy is in `tests.csv`.

## Key findings

**1. Which evidence wins depends on the condition (C1).** No single kind of evidence wins everywhere.
- **Clean cuts with a textured image (wear 0, complexity 0%).** Geometry beats color by a wide margin: COLOR − GEO is −0.32 to −0.48 AP across grids, all significant. GRAD and GEO are statistically tied.
- **1 px of wear.** GEO collapses. Its median AP falls from 0.95, 0.85 and 0.75 to 0.23, 0.06 and 0.02 (6 × 9, 12 × 18, 20 × 30). Both visual methods then beat it: GRAD − GEO is +0.32 to +0.50, and COLOR − GEO is +0.10 to +0.21, all significant.
- **50% complexity at wear 0.** The visual methods collapse to AP 0.02–0.15, and GEO, which is unaffected, wins by 0.74–0.81.
- **Both stressors together.** Every method is near its floor. GEO is ahead by only 0.005–0.10.

**2. Hybrids help unless one component is uninformative (C2).**
- **HYB-GC** significantly beats its better single component in 9 of 12 conditions, by +0.04 to +0.41 AP. It is significantly worse than GEO in all three 50%-complexity, wear-0 conditions (−0.12 to −0.17). There, equal-weight rank fusion mixes in a useless color signal.
- **HYB-FILTER** significantly beats its better component in 6 of 12 conditions. It loses badly to GEO at 50% complexity and wear 0 (−0.56 to −0.66), because GRAD rescores the candidates GEO had already ranked well.

**3. A reference helps most where a method's own evidence fails, and can hurt (C3).**
- **The largest gains:**
  - GEO under wear: +0.39 to +0.62 AP at 0% complexity, and +0.21 to +0.34 at 50%.
  - COLOR and GRAD at 50% complexity: +0.37 to +0.52.
- **Little or no gain** where the method is already near the ceiling. One example is the hybrids at wear 0 and complexity 0%, where the exact reference adds at most +0.01 AP.
- **Losses:**
  - GEO+R is significantly worse than GEO at 50% complexity and wear 0 (−0.15 to −0.26).
  - HYB-GC+R is worse than HYB-GC in several conditions (down to −0.11).

  In both cases, a weak reference signal fused at equal weight dilutes a strong one.
- **Exact vs. degraded reference:** a degraded reference usually adds less than an exact one, and the gap is largest at 20 × 30.
- **The reference on its own (REF-ONLY):** with the exact reference, it reaches 0.93–1.00 AP at 0% complexity, but only 0.47–0.72 at 50%.

**4. Method rankings change when a reference is added (C4).** These are descriptive orderings of the five methods by median AP.
- **No reference vs. exact reference:** Kendall's τ ranges from −0.40 to 1.00. The ordering reverses at 20 × 30, 50% complexity, wear 1, and τ = 0 in three conditions.
- **Exact vs. degraded reference:** the rankings mostly agree (τ ≥ 0.6 in 10 of 12 conditions).

**5. Cost (C5, runtime only).**
- **GEO** is the fastest arm in every condition and is on the AP–runtime Pareto front in all 12. Median t_total is 0.01 s, 0.15 s and 1.3 s for the three grids.
- **The single visual methods and hybrids** are slower than GEO: 0.1–0.7 s at the two smaller grids, and 2.2–3.6 s at 20 × 30.
- **The reference arms** cost most, and their cost grows fastest with puzzle size. At 20 × 30, exact-reference arms take about 62–65 s, against 10–14 s for degraded ones. The degraded reference is half resolution, so locating pieces in it is cheaper.

## Caveats to state in the paper

- **GEO's sensitivity to wear** reflects this cut family. Piecemaker cuts differ from each other by only about 1 px, which is about the size of the wear (P19, P28).
- **AP and top-1 can disagree.** At 50% complexity, COLOR's AP is about 0.04, but its top-1 is 0.37–0.50. Pairs inside the flat overlay all score as near-perfect matches, which ruins the global ranking even when each side's own ranking still finds its partner. Report both metrics.
- **A few comparisons have a bootstrap CI that excludes zero but are not significant after Holm.** One example is GRAD − GEO at 6 × 9, wear 0 and complexity 0%. In these, 2–3 images go strongly the other way, which the rank-based Wilcoxon test counts and the median does not. The planned test decides significance.
- **Overlay strength varies by image.** 0091 and 0217 are already 50–80% uniform at 0%, so the overlay adds less to them (P26). See the table in `analysis.md`.
- **The reference scale** is about 5% too large at wear 1 (P25).
- **Runtime stability (G8, D19 rule).** All 2,040 arm groups pass. 2 of 240 reference-location groups fail: 6 × 9 degraded locations of 0.08–0.11 s, where the five timings fall into two clusters. The effect is at most about 0.03 s on two instances' +R runtimes, so the C5 conclusions are unaffected. They are reported as a failure, not rerun.
