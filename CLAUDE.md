# CLAUDE.md: Jigsaw Matching Pilot (Phase 1)

## Your role

Implement and run the Phase 1 pilot described in `docs/spec.md`. You write and test the code. The user runs the experiments and handles all git commits and pushes.

## Source documents (read before starting work)

| File | Owns | Rule |
|---|---|---|
| `docs/handoff.txt` | Research scope and decisions | Source of truth for scope |
| `docs/spec.md` | How the experiment is implemented (v1.1) | Follow it exactly |
| `docs/decision_log.md` | Changes made after the spec | Newer than the spec; wins over it |
| `docs/open_decisions.md` | Questions still open and proposed defaults | Check before building the affected parts |

If these documents conflict, flag the conflict and ask. Do not guess.

The documents were copied from a claude.ai project and renamed, so their cross-references use the old names: `Experiment Spec.md` is `docs/spec.md`, `Decision Log.md` is `docs/decision_log.md`, and `jigsaw_experiment_handoff.txt` is `docs/handoff.txt`. The paper and `Alignment Audit.md` are not in this repo. They belong to the paper session.

In the handoff, the dated blocks at the top ("Decisions approved November 3" and "Scope reduction approved November 6") replace any conflicting text in the numbered sections below them. Examples are the "decision tree" wording, the "accuracy as primary metric" wording, and the "completed image or generator metadata" wording.

## Boundaries

- Do not edit the paper, and do not expand the research scope.
- Follow the spec. If something is unclear or unworkable, stop and ask before changing the design.
- Always stop and ask before you do anything in spec section B13:
  - change a research question, factor, or method family
  - drop a pilot gate or lower its pass condition
  - use main-set images for tuning
  - start the main run
  - introduce learned methods or GPU execution
- Record every approved change in `docs/decision_log.md`. Fill in every column: ID, date, what changed, why, evidence, approved by, and paper impact. Add only changes the user has approved.
- Do not run `git commit`, `git push`, or any other command that changes git history. The user does this.
- The smoke-test numbers in the spec appendix are not results. Never present them as results.

## Data rules

- DIV2K images go under `data/sources/`. Generated instances go under `data/instances/`.
- `data/` must be listed in `.gitignore`. Never commit images. The DIV2K license limits use to academic research.
- Only the evaluator may read `private/`. Methods receive `public/`, plus a reference array when the arm calls for one (spec B4).

## Build order (spec B11)

1. Repository, config system, and lockfile
2. Generator, ground truth, and instance export: pass G1–G3
3. Evaluator with known-answer tests: pass G5
4. Shared side extraction: pass G6
5. GEO and COLOR
6. Runner, input controls, and leakage tests: pass G4
7. GRAD
8. HYB-GC and HYB-FILTER
9. Reference levels, R, and location caching: pass G7. The +R versions of the two hybrids wait on Q5 in `docs/open_decisions.md`.
10. Runtime and memory measurement: pass G8
11. Complexity overlays: pass G10
12. Pilot run, the G9 check, and `reports/pilot_summary.md`
13. **Stop for the user's approval before the main run.**

At each gate, report pass or fail with the evidence before moving to the next step.

## Working conventions

- Pin exact dependency versions in a lockfile. Pinned versions are required for G3, which demands byte-identical instances and scores.
- Set `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, and `MKL_NUM_THREADS` to 1, and call `cv2.setNumThreads(1)`.
- Seeds use SHA-256 of the joined values, never Python's built-in `hash()`.
- The runner must be resumable. It appends one row per completed run and skips runs that are already done.
- Failed runs stay in the results file, with their `status` and error.
- Keep timing runs and memory runs in separate processes (spec B9).
- Before the user starts a timed run, remind them to close heavy programs and keep the machine plugged in.
