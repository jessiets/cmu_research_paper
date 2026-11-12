# Pilot summary

Pilot set: 3 images (0269, 0251, 0731), 12 instance types each, 17 arms, 5 timed repetitions plus separate memory runs. **Pilot numbers are checks and tuning evidence only; they are not study results.**

## Gates

| Gate | Result | Evidence |
|---|---|---|
| G1 instance integrity | PASS | 36 instances: exactly n connected pieces, no overlaps or gaps at wear 0, each interior edge once |
| G2 ground truth | PASS | true pairs = 2n − r − c, no diagonal pairs |
| G3 reproducibility | PASS | 10620 files byte-identical on regeneration; 36 score sets identical |
| G4 leakage | PASS | 18 instances × 17 arms: identical without private/ and reference/, and under re-permuted IDs; canary blocked |
| G5 evaluator | PASS | oracle 1.0, reversed oracle at base rate, random AP matches its expectation (36 instances) |
| G6 side extraction | PASS | wear 0: 0.993–0.997 of corners within 2 px; flat sides exact (D8: 2x contour) |
| G7 reference | PASS | localized share exact 0.972, degraded 0.714; degraded below exact in 16/18 |
| G8 measurement | PASS | D19 rule: median t_total moves < 10% when any one repetition is left out; the spec's CV rule is reported in the timing section |
| G9 practicality | PASS (19.6 h projected, budget 24 h; D18) | projection below |
| G10 complexity | PASS by user judgment (D15) | uniform_fraction +0.165 to +0.426 at 50%; all mechanical checks pass; +0.25 absolute reading not met on every image (D15) |

## [pilot] values

| Value | Setting | Source | Changed in pilot? |
|---|---|---|---|
| K (side resampling points) | 96 | spec B5 | No |
| Flat-side threshold | 0.05 x pitch | spec B5 | No |
| HYB-FILTER candidates per side | 10 | spec B7 | No |
| Timing repetitions | 5 | spec B9 | No |
| Degraded reference | blur 2 px, 0.5x, JPEG 40, gain 0.9, +15 | spec A5 | No |
| uniform_fraction block / std limit | 16 px / 4 | spec B10 | No |

## Runtime (G8, G9)

- t_total 12x18: median 2.06 s, CV median 0.005, max 0.234, share under 10% 0.99; largest median shift 0.058
- t_total 20x30: median 13.27 s, CV median 0.005, max 0.155, share under 10% 0.99; largest median shift 0.050
- t_total 6x9: median 0.21 s, CV median 0.009, max 0.162, share under 10% 0.98; largest median shift 0.048
- t_reference 12x18: median 4.17 s, CV max 0.045; largest median shift 0.017
- t_reference 20x30: median 37.12 s, CV max 0.042; largest median shift 0.027
- t_reference 6x9: median 0.29 s, CV max 0.166; largest median shift 0.099
- The spec's CV rule fails: 10 arm groups and 5 location groups have CV ≥ 10%. In the pilot, each arm group had one slow repetition (CV under 7% without it); the location groups were all 6x9 locations of about 0.1 s, where jitter of a few hundredths of a second exceeds 10%. G8 is decided by the D19 median rule.
- Pilot wall time: 5.0 h (4.3 h timing, 0.8 h memory)
- Full design (all 20 images timed at 5 reps, plus memory): 33.6 h; 3 reps: 22.2 h; 2 reps: 16.5 h.
- **Projected main run under D18: 19.6 h**: timing at 5 reps on 10 images 14.3 h, one quality run on the other 10 2.9 h, memory on the 10 timed images 2.5 h.

## Memory (20 × 30, largest peak deltas)

- HYB-GC (exact): 119 MiB
- HYB-GC (none): 119 MiB
- HYB-GC (degraded): 118 MiB
- COLOR (degraded): 109 MiB
- COLOR (none): 109 MiB

## Quality overview (pilot only, median AP across images and grids; not results)

| Arm | c0 w0 | c0 w1 | c50 w0 | c50 w1 |
|---|---|---|---|---|
| COLOR+R (degraded) | 0.802 | 0.688 | 0.456 | 0.397 |
| COLOR+R (exact) | 0.983 | 0.926 | 0.564 | 0.501 |
| COLOR | 0.414 | 0.269 | 0.041 | 0.037 |
| GEO+R (degraded) | 0.819 | 0.546 | 0.531 | 0.312 |
| GEO+R (exact) | 0.998 | 0.688 | 0.642 | 0.402 |
| GEO | 0.841 | 0.063 | 0.841 | 0.063 |
| GRAD+R (degraded) | 0.811 | 0.759 | 0.458 | 0.425 |
| GRAD+R (exact) | 0.995 | 0.943 | 0.563 | 0.535 |
| GRAD | 0.867 | 0.467 | 0.042 | 0.042 |
| HYB-FILTER+R (degraded) | 0.904 | 0.608 | 0.642 | 0.390 |
| HYB-FILTER+R (exact) | 1.000 | 0.686 | 0.698 | 0.462 |
| HYB-FILTER | 0.982 | 0.595 | 0.222 | 0.105 |
| HYB-GC+R (degraded) | 0.869 | 0.717 | 0.558 | 0.415 |
| HYB-GC+R (exact) | 0.998 | 0.838 | 0.637 | 0.514 |
| HYB-GC | 0.996 | 0.693 | 0.684 | 0.434 |
| REF-ONLY (degraded) | 0.769 | 0.758 | 0.431 | 0.389 |
| REF-ONLY (exact) | 1.000 | 0.970 | 0.586 | 0.526 |

## Paper-affecting changes

Decisions D1–D19 in `docs/decision_log.md`; required paper edits P1–P30 in `docs/paper_updates.md`.

## Open items

- G10: the +0.25 absolute reading of "clearly higher" fails for image(s) 0251 (already uniform at 0%). The user judged G10 met on the relative measure (D15); per-instance strength is in results/pilot_uniform_fraction.csv.
- Step 13: the main run starts only with the user's explicit approval.
