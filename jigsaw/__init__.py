"""Pairwise jigsaw matching pilot."""

import os as _os

# Single-threaded numerics (CLAUDE.md working conventions). Must be set before
# numpy, scipy, or OpenCV are first imported, so it lives in the package root.
for _name in ("OMP_NUM_THREADS", "OPENBLAS_NUM_THREADS", "MKL_NUM_THREADS"):
    _os.environ[_name] = "1"
