# Paper Updates

Changes the written paper needs because of the experiment work. The experiment session adds items here, and the user passes them to the paper session. The experiment session never edits the paper itself.

**Rules**

- Add one row per required paper change, newest last.
- A change that comes from a decision gives its decision log ID in the Source column. The full reason is in `docs/decision_log.md`.
- Only the paper session or the user changes Status, from `Pending` to `Done`.

| ID | Date added | Paper section | Change needed | Source | Status |
|---|---|---|---|---|---|
| P1 | 2026-11-11 | 2.2 | Say that texture evidence was not tested (TEX and HYB-GX are out of scope). | D1 | Pending |
| P2 | 2026-11-11 | 4.2, 4.3 | Name the levels used: grids 6 × 9, 12 × 18, 20 × 30; complexity 0% and 50%; wear 0 and 1 px; 3 pilot and 20 main images. | D1 | Pending |
| P3 | 2026-11-11 | 4.3 | Remove `tracemalloc` from the memory measurement description. | D1 | Pending |
| P4 | 2026-11-11 | 4.4 | Name the planned comparisons C1–C5 and the Holm correction. Remove interaction models and the decision tree. | D1 | Pending |
| P5 | 2026-11-11 | 4.5 | Note the dropped levels (25% complexity, 2 px wear) and dropped methods (TEX, HYB-GX). | D1 | Pending |
| P6 | 2026-11-11 | 1.4 | Change "framework" wording to conditional guidance. | D1 | Pending |
| P7 | 2026-11-11 | 4.3 | Explain that reference locations are computed once per instance and reference level, and that this cost (`t_reference`) is added to each reference arm's runtime. | D2 | Pending |
| P8 | 2026-11-11 | Methods | Report Python 3.13 and the pinned package versions from the lockfile. | D3 | Pending |
| P9 | 2026-11-11 | Methods | Report the image selection procedure: eligible DIV2K train HR filenames sorted, then 23 drawn with master seed `20261106`; the first 3 are the pilot set and the other 20 the main set. | D4 | Pending |
| P10 | 2026-11-11 | Methods | Describe the stray-island rule (each disconnected island joins the neighboring piece it shares the longest border with) and say reassignment counts are in the instance manifests. | D5 | Pending |
| P11 | 2026-11-11 | Methods, References | **Citation needed.** Cite DIV2K, as its license requires. Required citation (check the wording on the DIV2K site, https://data.vision.ee.ethz.ch/cvl/DIV2K/, before final submission): E. Agustsson and R. Timofte, "NTIRE 2017 Challenge on Single Image Super-Resolution: Dataset and Study," *Proc. IEEE Conf. Computer Vision and Pattern Recognition (CVPR) Workshops*, July 2017. Also state that the dataset is used for academic research only. | DIV2K license; spec A4 | Pending |
| P12 | 2026-11-11 | Methods, Figures | Do not print a DIV2K source image in the paper unless permission is obtained or a different image is used. Image copyright stays with the original owners. | Spec A4 | Pending |
| P13 | 2026-11-11 | Methods, References | **Citation needed.** Cite Piecemaker as software and say it is the source of the piece-cut curve code. Reference entry: J. Hickenlooper, *Piecemaker: Create jigsaw puzzle pieces from an image*, version 0.8.1, commit `21f80208cc55caaac7f11d9a3ebbbce4aaa6d196` (March 13, 2026), GNU LGPL v3.0 or later. https://github.com/jkenlooper/piecemaker. Only `src/piecemaker/paths/interlockingnubs.py` is reused (vendored with its license). Also say ground truth comes from the generator's own cut topology, not from Piecemaker's `adjacent.py`. The project gives no preferred citation, so this is a standard software citation built from its `pyproject.toml`. | Spec B2; Piecemaker `pyproject.toml` | Pending |
| P14 | 2026-11-11 | Methods | Describe the GRAD adaptation: per-side gradient mean and covariance along curved sides, Gallagher's dummy gradients added so the covariance can be inverted, both directions summed. The original measure assumes straight edges. | Spec B7 | Pending |
| P15 | 2026-11-11 | Results | Do not report the smoke-test numbers in the spec appendix. They are design checks, not results. | Spec appendix | Pending |
| P16 | 2026-11-11 | Methods (dataset) | Explain why DIV2K's high-resolution (HR) train images are used instead of its low-resolution (LR) sets. (1) Piece pitch is fixed at 64 px for every grid, so puzzle size is not confounded with piece resolution. The largest grid, 20 × 30, therefore needs a 1,280 × 1,920 px image. DIV2K's LR sets are 2×, 3×, and 4× bicubic downscales of the HR images (the 2× set is about 1,020 × 700 px), so none would cover that size. (2) Using LR images would mean a smaller pitch, which leaves fewer edge pixels for the color and gradient measures, or dropping the 20 × 30 grid, which is where scaling to many candidates (0.64% true pairs) is tested. (3) Bicubic downscaling smooths edges, which would weaken color and gradient evidence through preprocessing rather than through the methods. | Spec A3, A4 | Pending |
| P17 | 2026-11-11 | 4.2 (wear description) | Describe wear as material removal only: each piece is eroded by about 1 px along its boundary, made irregular by Gaussian-smoothed noise (σ = pitch/10), and the largest connected part is kept. Wear never adds pixels, so neighbors never share image content. At wear 1, about 10% of each piece's pixels are removed. | D6 | Pending |
