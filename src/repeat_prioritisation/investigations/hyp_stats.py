"""Estimators for the hypothesis tests (`repeat-hypotheses`): a stratified difference of increases with a cluster bootstrap, Moran's I,
Mann-Kendall. numpy and scipy only; every random draw takes a seed, so a rerun on the same data gives the same numbers."""
from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats

MIN_BASE = 10          # a stratum enters the pooled estimate only with at least this many baseline detections in both groups


def _logratio(a, c, b, d):
    """log of the increase ratio (a/c) / (b/d), with 0.5 added to each count so that an empty cell does not break the log."""
    return np.log((a + 0.5) / (c + 0.5)) - np.log((b + 0.5) / (d + 0.5))


def _weight(a, c, b, d):
    return 1.0 / (1.0 / (a + 0.5) + 1.0 / (c + 0.5) + 1.0 / (b + 0.5) + 1.0 / (d + 0.5))


def did_estimate(rows: pd.DataFrame, n_boot: int = 1000, seed: int = 1, min_base: int = MIN_BASE) -> dict:
    """Ratio of increases, group 1 against group 0, pooled over strata.

    ``rows``: one row per (cluster, stratum) with ``a`` and ``c`` (group 1: detections in the test year, and in the baseline years added up),
    ``b`` and ``d`` (the same for group 0). Within a stratum the ratio is (a/c) / (b/d): how much more group 1 rose in the test year than
    group 0 did, relative to each group's own baseline (exposure cancels). Strata are pooled by the inverse of the Poisson variance of the
    log ratio. The interval is the 2.5th and 97.5th percentile of a bootstrap that resamples clusters (spatial blocks, or KHG).
    Returns the ratio, its interval, and the counts behind it."""
    if rows.empty:
        return {"ratio": None, "lo": None, "hi": None, "n_clusters": 0, "n_strata": 0, "a": 0, "b": 0, "c": 0, "d": 0}
    cl = pd.factorize(rows["cluster"])[0]
    st = pd.factorize(rows["stratum"])[0]
    a, c, b, d = (rows[k].to_numpy(float) for k in ("a", "c", "b", "d"))
    ns, ncl = st.max() + 1, cl.max() + 1

    def pooled(k):
        w_ = k[cl]
        A, C, B, D = (np.bincount(st, w_ * v, minlength=ns) for v in (a, c, b, d))
        ok = (C >= min_base) & (D >= min_base)
        if not ok.any():
            return np.nan, 0
        w = _weight(A[ok], C[ok], B[ok], D[ok])
        return float(np.sum(w * _logratio(A[ok], C[ok], B[ok], D[ok])) / np.sum(w)), int(ok.sum())

    point, n_ok = pooled(np.ones(ncl))
    rng = np.random.default_rng(seed)
    boot = np.array([pooled(rng.multinomial(ncl, np.full(ncl, 1.0 / ncl)).astype(float))[0] for _ in range(n_boot)])
    boot = boot[np.isfinite(boot)]
    lo, hi = (np.exp(np.percentile(boot, [2.5, 97.5])) if len(boot) > 20 else (np.nan, np.nan))
    return {"ratio": None if not np.isfinite(point) else float(np.exp(point)), "lo": None if not np.isfinite(lo) else float(lo), "hi": None if not np.isfinite(hi) else float(hi),
            "n_clusters": int(ncl), "n_strata": n_ok, "a": int(a.sum()), "b": int(b.sum()), "c": int(c.sum()), "d": int(d.sum())}


def moran_i(values: np.ndarray, xy: np.ndarray, k: int = 8, n_perm: int = 999, seed: int = 1) -> dict:
    """Moran's I with row-standardised k-nearest-neighbour weights and a one-sided permutation p (clustering above chance)."""
    from scipy.spatial import cKDTree
    v = np.asarray(values, float)
    n = len(v)
    if n < k + 3 or np.nanstd(v) == 0:
        return {"i": None, "p": None, "n": int(n)}
    z = v - v.mean()
    _, idx = cKDTree(xy).query(xy, k=k + 1)
    nb = idx[:, 1:]

    def moran(zz):
        return float((zz * zz[nb].mean(axis=1)).sum() / (zz * zz).sum())

    obs = moran(z)
    rng = np.random.default_rng(seed)
    perm = np.array([moran(rng.permutation(z)) for _ in range(n_perm)])
    return {"i": obs, "p": float((1 + (perm >= obs).sum()) / (n_perm + 1)), "n": int(n)}


def mann_kendall(x) -> dict:
    """Mann-Kendall trend test of a series in time order (tie-corrected variance); two-sided p; Sen slope per step."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    n = len(x)
    if n < 4:
        return {"s": None, "z": None, "p": None, "slope": None, "n": int(n)}
    s = sum(np.sign(x[j] - x[i]) for i in range(n - 1) for j in range(i + 1, n))
    _, counts = np.unique(x, return_counts=True)
    var = (n * (n - 1) * (2 * n + 5) - np.sum(counts * (counts - 1) * (2 * counts + 5))) / 18.0
    z = 0.0 if s == 0 else (s - np.sign(s)) / np.sqrt(var) if var > 0 else 0.0
    slopes = [(x[j] - x[i]) / (j - i) for i in range(n - 1) for j in range(i + 1, n)]
    return {"s": float(s), "z": float(z), "p": float(2 * (1 - stats.norm.cdf(abs(z)))), "slope": float(np.median(slopes)), "n": int(n)}


def spearman(x, y) -> dict:
    x, y = np.asarray(x, float), np.asarray(y, float)
    ok = np.isfinite(x) & np.isfinite(y)
    if ok.sum() < 5:
        return {"rho": None, "p": None, "n": int(ok.sum()), "lo": None, "hi": None}
    r = stats.spearmanr(x[ok], y[ok])
    n = int(ok.sum())
    z, se = np.arctanh(r.statistic), 1.0 / np.sqrt(n - 3)          # Fisher interval of a correlation: wide with a dozen units
    return {"rho": float(r.statistic), "p": float(r.pvalue), "n": n, "lo": float(np.tanh(z - 1.96 * se)), "hi": float(np.tanh(z + 1.96 * se))}
