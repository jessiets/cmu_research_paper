"""GRAD: gradient evidence, Gallagher's (2012) Mahalanobis gradient compatibility (spec B7).

Adapted to curved sides by sampling layers along the inward normal:

- For each side, p(d) is the RGB (0-255, D14) sample d px inward at each of
  the K side points. The side's own gradient is G = p(1) - p(2), which points
  outward across the side. Its mean mu and covariance S over the K points,
  with Gallagher's nine dummy gradients appended, describe how color changes
  as the side is approached. The dummies keep S invertible.
- For the relation "B faces A across this side", the gradient across the cut
  is C_k = pB(1)_k - pA(1)_k (B's points reversed so k faces k).
- D(A -> B) = mean_k (C_k - mu_A)^T S_A^-1 (C_k - mu_A). The reverse direction
  uses B's statistics and -C_k. The relation score is -(D(A->B) + D(B->A)).

Sums over the K points are replaced by means, which only rescales scores by
the constant K.
"""

from __future__ import annotations

import numpy as np

from jigsaw.features.boundary import side_samples
from jigsaw.methods.base import B, Features, L, PuzzleInput, R, ScoreResult, T, finish

DEPTHS_PX = (1.0, 2.0)
CHUNK_ROWS = 32
# Gallagher (2012): dummy gradients appended before estimating mean and covariance.
DUMMY_GRADIENTS = np.array([[0, 0, 0], [1, 1, 1], [-1, -1, -1], [0, 0, 1], [0, 1, 0],
                            [1, 0, 0], [-1, 0, 0], [0, -1, 0], [0, 0, -1]], dtype=np.float64)


def gradient_stats(inner: np.ndarray, outer: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """(n, K, 3) samples at depths 1 and 2 -> mean (n, 3) and inverse covariance (n, 3, 3)."""
    gradients = inner - outer
    n = gradients.shape[0]
    stacked = np.concatenate([gradients, np.broadcast_to(DUMMY_GRADIENTS, (n, 9, 3))], axis=1)
    mean = stacked.mean(axis=1)
    centered = stacked - mean[:, None, :]
    cov = np.einsum("nkp,nkq->npq", centered, centered) / (stacked.shape[1] - 1)
    return mean, np.linalg.inv(cov)


def _quadratic_terms(x: np.ndarray, y: np.ndarray, inv: np.ndarray, rows: slice) -> np.ndarray:
    """out[a, b] = mean_k (x_bk - y_ak)^T M_a (x_bk - y_ak) for a in ``rows``, all b.

    Expanded as x^T M x - 2 x^T M y + y^T M y so no (rows, n, K, 3) einsum is
    needed. Every sum runs over a fixed axis of elementwise products, so each
    entry is independent of row and column order (gate G4).
    """
    m = inv[rows]                                                       # (c, 3, 3)
    ya = y[rows]                                                        # (c, K, 3)
    second = np.einsum("nkp,nkq->npq", x, x, optimize=False) / x.shape[1]  # (n, 3, 3)
    term_xx = (m.reshape(-1, 1, 9) * second.reshape(1, -1, 9)).sum(axis=-1)            # (c, n)
    v = np.einsum("cpq,ckq->ckp", m, ya, optimize=False)                # M_a y_ak, (c, K, 3)
    term_xy = (v.reshape(v.shape[0], 1, -1) * x.reshape(1, x.shape[0], -1)).sum(axis=-1) / x.shape[1]
    term_yy = (v * ya).sum(axis=-1).mean(axis=-1)                       # (c,)
    return term_xx - 2.0 * term_xy + term_yy[:, None]


def mgc(a_inner: np.ndarray, a_stats, b_inner: np.ndarray, b_stats) -> np.ndarray:
    """-(D(A->B) + D(B->A)) for all (a, b), where A's side faces B's (already reversed) side."""
    n = a_inner.shape[0]
    mean_a, inv_a = a_stats
    mean_b, inv_b = b_stats
    # A -> B: x = pB(1), y = pA(1) + mu_A, A's statistics (row piece).
    y_a = a_inner + mean_a[:, None, :]
    # B -> A: x = pA(1), y = pB(1) + mu_B, B's statistics; computed with B as the row, then transposed.
    y_b = b_inner + mean_b[:, None, :]
    forward = np.empty((n, b_inner.shape[0]))
    backward_t = np.empty((b_inner.shape[0], n))
    for start in range(0, n, CHUNK_ROWS):
        rows = slice(start, min(start + CHUNK_ROWS, n))
        forward[rows] = _quadratic_terms(b_inner, y_a, inv_a, rows)
    for start in range(0, b_inner.shape[0], CHUNK_ROWS):
        rows = slice(start, min(start + CHUNK_ROWS, b_inner.shape[0]))
        backward_t[rows] = _quadratic_terms(a_inner, y_b, inv_b, rows)
    return -(forward + backward_t.T)


PAIR_CHUNK = 8192


def mgc_pairs(a_idx: np.ndarray, b_idx: np.ndarray, a_inner: np.ndarray, a_stats,
              b_inner: np.ndarray, b_stats) -> np.ndarray:
    """``mgc`` for an explicit list of (a, b) pairs only (used by HYB-FILTER)."""
    out = np.empty(a_idx.size)
    mean_a, inv_a = a_stats
    mean_b, inv_b = b_stats
    for start in range(0, a_idx.size, PAIR_CHUNK):
        ai, bi = a_idx[start:start + PAIR_CHUNK], b_idx[start:start + PAIR_CHUNK]
        across = b_inner[bi] - a_inner[ai]                                   # (m, K, 3)
        fd = across - mean_a[ai][:, None, :]
        forward = (np.einsum("mkp,mpq->mkq", fd, inv_a[ai], optimize=False) * fd).sum(-1).mean(-1)
        bd = -across - mean_b[bi][:, None, :]
        backward = (np.einsum("mkp,mpq->mkq", bd, inv_b[bi], optimize=False) * bd).sum(-1).mean(-1)
        out[start:start + PAIR_CHUNK] = -(forward + backward)
    return out


class GradMatcher:
    name = "GRAD"
    uses_reference = False

    def extract(self, puzzle: PuzzleInput) -> Features:
        sides = puzzle.sides
        n, k = len(sides.piece_ids), sides.k
        layers = np.zeros((len(DEPTHS_PX), n, 4, k, 3))
        for index, pid in enumerate(sides.piece_ids):
            if sides.failed[index]:
                continue
            piece = puzzle.pieces[pid]
            rgb = piece.rgb.astype(np.float64)
            for d, depth in enumerate(DEPTHS_PX):
                layers[d, index] = side_samples(piece, sides.points[index], depth, values=rgb)
        inner, outer = layers
        arrays = {}
        for name, s, reverse in (("right", R, False), ("left_rev", L, True),
                                 ("bottom", B, False), ("top_rev", T, True)):
            i = inner[:, s, ::-1] if reverse else inner[:, s]
            o = outer[:, s, ::-1] if reverse else outer[:, s]
            mean, inv_cov = gradient_stats(i, o)
            arrays[f"{name}_inner"] = np.ascontiguousarray(i)
            arrays[f"{name}_mean"] = mean
            arrays[f"{name}_inv_cov"] = inv_cov
        return Features(arrays)

    def score(self, puzzle: PuzzleInput, features: Features) -> ScoreResult:
        f = features.arrays

        def stats(name):
            return f[f"{name}_mean"], f[f"{name}_inv_cov"]

        scores = {
            "right": mgc(f["right_inner"], stats("right"), f["left_rev_inner"], stats("left_rev")),
            "below": mgc(f["bottom_inner"], stats("bottom"), f["top_rev_inner"], stats("top_rev")),
        }
        return finish(scores, puzzle.sides.usable)
