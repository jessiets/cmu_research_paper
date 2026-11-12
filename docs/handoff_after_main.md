# Handoff: after the main run finishes

This is for the session that picks up once the user has run the main quality and timing passes (build step 13). Read `CLAUDE.md` first, then `docs/decision_log.md` (D1–D19), `docs/paper_updates.md` (P1–P30) and `reports/pilot_summary.md`. `docs/handoff_after_pilot.md` is history and is fully done.

## Where things stand (2026-11-12)

- **The pilot is done,** and every gate G1–G10 has passed or been settled:
  - G8 passes under the D19 median rule.
  - G9 passes: 19.6 h projected against the 24 h budget.
  - G10 was judged met by the user (D15).
- **The main run was approved by the user.** Its design (D18):
  - **Timed images:** 0510, 0186, 0479, 0223, 0506, 0173, 0730, 0178, 0091, 0525. They get timing mode at 5 repetitions, then a memory run later.
  - **Untimed images:** 0407, 0016, 0473, 0288, 0354, 0737, 0587, 0217, 0633, 0459. They get one quality-mode run per arm.
  - C1–C4 use all 20 images. C5 uses AP over 20 images, with runtime and memory over the 10 timed ones.
- **Main instances:** 240 generated, and G1–G3 pass (`results/gates/main_g1_g3.json`). The per-image overlay strength is in `results/main_uniform_fraction.csv`.
- **Deadline:** the user has 24 hours from 2026-11-12 morning for initial results, then another 24 hours for final results.
- **The memory pass** (about 2.5 h) runs in the second window.

## Results files

- `results/main_quality.csv` holds the 10 untimed images. Expect 10 × 12 × 17 = 2,040 rows.
- `results/main_timing.csv` holds the 10 timed images. Expect 10 × 12 × 17 × 5 = 10,200 rows.
- `results/main_timing_reference.csv` holds the timing of the reference-location step.
- `results/main_memory.csv` will hold the memory pass, once the user runs it.

## What the next session does, in order

1. **Check that the runs are complete.**
   - Check the row counts above.
   - Check that every row records one clean `git_commit` and the same config hash.
   - Count rows whose `status` is not `ok`, and read their errors. Never delete failed rows.
   - If runs are missing, ask the user to rerun the same command; the runner skips completed runs.
2. **G8 on the main timing data** (D19 rule):
   ```
   .venv\Scripts\python -m jigsaw.run.timing_gate --results results/main_timing.csv --report results/gates/main_g8.json
   ```
   Report the median-shift result and the CV result. If any group fails, report it. Don't hide it, and don't rerun selectively without the user's approval.
3. **Analysis** (initial results):
   ```
   .venv\Scripts\python -m jigsaw.analysis.analyze --timing results/main_timing.csv --quality results/main_quality.csv --uniform results/main_uniform_fraction.csv --out reports/main_analysis --label "Main run - initial results"
   ```
   - After the memory pass, rerun with `--memory results/main_memory.csv` added, writing to `reports/main_analysis` with the label "Main run - final results".
   - Look at every figure for clipping and overlapping labels. In the busy C5 panels, labels were already known to overlap in the pilot. That's cosmetic: fix only the layout, never the data.
4. **Report the results honestly.** Cover C1–C5 with effect sizes, CIs and Holm-corrected p-values, plus the per-image overlay strength (P26). Where the results contradict the paper's thesis, say so plainly and add a paper-update row. Never adjust the experiment to fit the thesis. The next paper-update ID is **P31**.
5. **Commit messages** for the results and reports. Use the user's style: a lowercase "added …" subject, followed by `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`. The user runs git; never commit yourself.

## Rules that still apply

- Everything in spec B13 needs the user's approval: research questions, gates, tuning, learned methods and GPU use.
- No tuning on main-set results. The methods and settings are frozen.
- The smoke-test numbers in the spec appendix and the pilot numbers are not results.
- Before any timed run, remind the user to close heavy programs and keep the machine plugged in.
