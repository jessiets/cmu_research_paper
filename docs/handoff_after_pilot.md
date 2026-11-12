# Handoff: after the pilot run finishes

This is for the session that picks up once the user has run the pilot (build step 12). Read `CLAUDE.md` first, then `docs/spec.md`, `docs/decision_log.md` (D1–D16) and `docs/open_decisions.md`. The rules there still apply. In particular, the user does all git commits, and everything in spec B13 needs the user's approval first.

## Where things stand (2026-11-11)

- **Steps 1–11 are built.** 97 tests pass (`.venv\Scripts\python -m pytest`).
- **Gates passed:** G1–G3 (36 pilot instances, 180 score sets), G4 (18 instances × 17 arms), G5 (36 instances), G6 (with D8), G7, and G10 by user judgment (D15). Evidence is in `results/gates/`.
- **Gates still open:**
  - G8: coefficient of variation of `t_total` below 10%, or more repetitions.
  - G9: the largest condition fits the main-run time budget. This needs Q4.
- **Pilot data:** 3 images (0269, 0251, 0731), 36 instances in `data/instances/`, and reference-location caches in `data/cache/reference/`. The per-instance overlay strength is in `results/pilot_uniform_fraction.csv`.
- **Config:** `configs/pilot.yaml` uses `timing_repetitions: 5`. The user said they will decide after the pilot whether to lower the repetitions for the main run.

## Waiting on the user

1. **D17 approval.** The evaluator sums fractional tie credits with `math.fsum`. That makes metrics independent of piece-ID order down to the last bit, so G4 passes under exact equality without a tolerance. G4 and G5 were re-run on the fixed code. D17 is **not** in the decision log yet. Add it with every column filled only once the user approves. Proposed text:
   - **What changed:** the evaluator sums fractional credits with `math.fsum`.
   - **Why:** G4 found differences of about 1e-16 in 19 of 306 checks, caused by summation order, not leakage.
   - **Evidence:** `results/gates/step6_g4.json` and `step3_g5.json`, both re-run.
   - **Paper impact:** none.
2. **Q4: the main-run time budget,** in hours. G9 needs it.
3. **The repetition decision for the main run.** If the repetitions go down, G8 must still pass at the new count. Lowering the count without that check would loosen a gate, which is a B13 item.

## What the user runs (PowerShell, repo root)

```
.venv\Scripts\python -m jigsaw.run.runner --config configs/pilot.yaml --results results/pilot_timing.csv --mode timing
.venv\Scripts\python -m jigsaw.run.runner --config configs/pilot.yaml --results results/pilot_memory.csv --mode memory
```

Both runs can be resumed: if one stops, rerun the same command. Each run also writes a runlog sidecar with wall times. Expect 3–6 hours in total.

## What the next session does, in order

1. **Check that the runs are complete.**
   - Both CSVs should exist, with every planned run present.
   - Count the rows whose `status` is not `ok`, and read their errors. Failed rows stay in the file. Never delete them.
   - If runs are missing, ask the user to rerun the same command; the runner skips completed runs.
   - Confirm that the `commit` column is one clean commit. If it isn't, flag it.
2. **G8 (timing stability).**
   ```
   .venv\Scripts\python -m jigsaw.run.timing_gate --results results/pilot_timing.csv
   ```
   - The report goes to `results/gates/step10_g8.json`.
   - Report pass or fail per arm and condition, with the coefficients of variation.
   - If G8 fails, the spec's remedy is more repetitions. Do not loosen the 10% bar. Present the options and let the user decide.
3. **Pilot summary and G9.**
   ```
   .venv\Scripts\python -m jigsaw.run.pilot_summary --budget-hours <Q4>
   ```
   - This writes `reports/pilot_summary.md`.
   - Without `--budget-hours`, G9 is shown as pending. Ask the user for Q4.
   - Give the main-run time projection at 5 repetitions, and at any lower count the user is considering.
4. **Pilot analysis.** It must carry the pilot label.
   ```
   .venv\Scripts\python -m jigsaw.analysis.analyze --timing results/pilot_timing.csv --memory results/pilot_memory.csv --uniform results/pilot_uniform_fraction.csv --out reports/pilot_analysis --label "PILOT - not study results"
   ```
   - Look at every figure in `reports/pilot_analysis/` for label collisions and clipping.
   - With 3 images, nothing is expected to be significant. That shows the pipeline works. It is not a finding.
5. **Report to the user.**
   - Gate status: G8, G9, and whether every gate G1–G10 has now passed.
   - Failed runs, if any.
   - The main-run time estimate.
   - Anything surprising.
   - Pilot numbers are diagnostics only. Never present them as study results, and never use them to tune methods. Write any paper-relevant observation into `docs/paper_updates.md` as a new row (next ID: **P28**), labeled pilot or diagnostic.
6. **Commit messages.** Give the user messages for the pilot results and reports. Use their style: a lowercase "added …" subject, followed by `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
7. **Step 13: STOP.** Do not start the main run. Even with every gate passed, the main run needs the user's explicit approval (B13). When approved, the user runs the commands below. Note that main instances must be generated first; check `jigsaw.generate.instance --help` and generate at complexity 0 and 50.
   ```
   .venv\Scripts\python -m jigsaw.evaluate.manipulation --config configs/main.yaml
   .venv\Scripts\python -m jigsaw.run.runner --config configs/main.yaml --results results/main_timing.csv --mode timing --allow-main
   .venv\Scripts\python -m jigsaw.run.runner --config configs/main.yaml --results results/main_memory.csv --mode memory --allow-main
   ```
   Before any timed run, remind the user to close heavy programs and keep the machine plugged in.

## Useful facts

- The runner modes are `quality`, `timing` and `memory`. Timing and memory always run in separate processes (B9).
- In timing mode, the reference-location timing runs first, and its median `t_reference` is added to each reference arm's `t_total` (D2).
- Filter flags: `--methods`, `--references`, `--complexity`, `--images`, `--grids` and `--repetitions`.
- There are 17 arms:
  - 5 methods with no reference
  - 5 methods with R, at the exact and degraded levels (10 arms)
  - REF-ONLY at the exact and degraded levels (2 arms)
- Known caveats already recorded for the paper:
  - P25: at wear 1, the reference scale comes out about 5% too large.
  - P26: the overlay strength varies by image.
  - P19: GEO is limited by the low variety of cut shapes.
- The user's standing rule is to report results honestly. If the results contradict the thesis, report what was found and log a paper update. Never adjust the experiment to fit the thesis.
