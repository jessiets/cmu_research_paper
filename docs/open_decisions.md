# Open Decisions and Proposed Defaults

**Carried over from:** the planning chat on November 6, 2026, in the claude.ai project.

**Status:** Q1 is resolved as Python 3.13 (D3). Q5 is resolved as option A for both hybrids (D9). All five proposed defaults are approved (D4, D5, D7, D10, D11). Q4 is resolved: the budget is 24 hours for the main run, met by the D18 design (runtime on 10 images, quality on all 20), with the G8 rule changed by D19. No questions remain open.

## Questions waiting on the user

### Q1. Python version (resolved)

The spec (B1) says Python 3.12. The project uses Python 3.13, recorded as D3 in `decision_log.md`.

- **Recommendation:** use 3.13. The code is the same either way. Recent NumPy releases may have dropped 3.12 support.
- **What matters more:** the exact library versions, because G3 requires byte-identical outputs. Pin them in a lockfile, and use the same environment for the timed pilot and the main run.
- **Paper impact:** none, beyond the software versions reported in Methods.
- **If 3.13 is chosen:** add a decision log entry that changes spec B1.

### Q4. Time budget for the main run (gate G9) (resolved: 24 hours, D18)

G9 asks whether the main run, projected from pilot timings, fits within the user's budget.

- **The pilot can run without this number.** G9 can't be checked until the user gives one.
- **Rough planning range:** a few to about 15 CPU-hours for the pilot, and roughly 7× that for the main run. These are estimates only. The pilot produces the real projection.
- **If the projection is over budget:** stop and ask. The options are fewer timing repetitions, dropping 20 × 30, or fewer images. Each of these is a B13 design change.

### Q5. How R is fused into the hybrid methods (resolved: option A for both, D9)

Spec B7 says each +R arm "rank-fuses R with that method's existing score channels." For the two hybrids, this can be read two ways.

**HYB-GC+R**

- **Option A (proposed):** GEO, COLOR, and R are fused with equal weights, one third each.
- **Option B:** R is fused with the already-fused HYB-GC rank, half and half. R would then carry more weight than in GEO+R or COLOR+R, which would muddy comparison C3.

**HYB-FILTER+R**

- **Option A (proposed):** R is fused only among the candidates the GEO filter kept. Filtered-out pairs stay at the worst score, so the arm remains filter-then-score.
- **Option B:** R is fused across all pairs, so it can rescue true neighbors the filter dropped. The arm would no longer be a filtering method, and the paper's description of it would change.

Either choice needs a decision log entry with its paper impact.

## Proposed defaults (go ahead unless the user objects)

All five defaults are now approved. The pilot summary should still list them.

1. **Reference location uses FFT-based masked squared-difference matching (approved; D10).** It is the same objective as masked `TM_SQDIFF`. Every reference arm uses it, as B7 permits. Direct masked `matchTemplate` at 20 × 30 is estimated to need trillions of operations per instance.
2. **Image selection (approved; D4):** sort the eligible DIV2K train HR filenames, then draw 23 using master seed `20261106`. The first 3 drawn are the pilot set, and the other 20 are the main set. Record the seed in the config and in each manifest.
3. **Disconnected regions (B2 step 5; approved; D5):** reassign each stray island to the neighboring piece it shares the longest border with. Count the reassignments in the manifest. Rejecting pieces would break G1's requirement of exactly `n` pieces.
4. **Top-1 side accuracy (approved; D7):** for each non-border side, rank candidates by that side's relation score, not by the best-of-four pair score.
5. **Complexity overlay seed and shape (approved; D11):** spec B10 says only that the overlay is a "seeded, connected solid-color region", so the seed and shape still need defining.
   - **Seed:** `overlay_seed = sha256(image_id, grid, complexity)`. Wear does not change the seed, so the wear 0 and wear 1 instances share the same overlay and stay paired.
   - **Shape:** grow a single region from a seeded start pixel by randomized region growing. Stop when it covers exactly `round(fraction × area)` pixels. This makes the region connected and gives an exact coverage fraction.
   - **Color:** the mean color of the cropped image, as B10 states.

## Environment notes

- The user runs everything locally. Timed work must stay on one machine (B1).
- The user downloads DIV2K into `data/sources/`, which is git-ignored.
- Piecemaker is vendored at commit `21f80208cc55caaac7f11d9a3ebbbce4aaa6d196`, from `src/piecemaker/paths/interlockingnubs.py`, with its LGPL-3.0 notice kept (B2).
