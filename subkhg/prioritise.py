"""
Sub-KHG ranking by need for intervention (sekat kanal, sumur bor, pompa).

Differs from the national run (common.scoring.score), which classes units by risk x feasibility:
  - the rank depends on need only; feasibility is reported for choosing the measure afterwards
  - drainage (f_reach) and distance to dry-season water (f_water_dist) are need signals
    (sekat kanal / sumur bor criteria of Permen LHK 7/2022); intact forest lowers need
  - classes are tertiles of the need score (within each KHG with normalise_scope = khg)

Two methods, both always computed so they can be compared:
  need     (default) weighted mean of indicators rescaled to 0-1, need plus stakes
  ranksum  the team's earlier method (docs/prior_method.md): each indicator ranks the sub-KHG, total = sum of
           rank x weight. Rank 1 = highest priority (worst condition), so the lowest total is the top priority.
`scoring.method` picks which one sets kelas and peringkat. The other is kept as peringkat_need / peringkat_ranksum.

score_need(df, cfg) takes the per-unit indicator table from common.indicators.compute and returns
(ranked table, report), the same contract as common.scoring.score. Normalisation, group scores,
sensitivity and validation are the shared functions in common.scoring.
"""
from __future__ import annotations

import copy
import logging

import numpy as np
import pandas as pd

from common import scoring as SC

log = logging.getLogger("prioritas.subkhg")

NEED_CLASSES = ["Kebutuhan intervensi: tinggi", "Kebutuhan intervensi: sedang", "Kebutuhan intervensi: rendah"]
CLASS_COLORS = {NEED_CLASSES[0]: "#B8321F", NEED_CLASSES[1]: "#EF9F27", NEED_CLASSES[2]: "#D3D1C7",
                SC.CLASS_ORDER[5]: "#7FA7C9", SC.CLASS_ORDER[6]: "#9A9A9A"}

# group "u" = need, "i" = stakes (secondary), "f" = feasibility (reported, not ranked)
NEED_INDICATORS = {
    "f_reach":      {"group": "u", "weight": 1.5},                    # drained by canals -> sekat kanal
    "f_water_dist": {"group": "u", "direction": 1, "weight": 1.0},    # far from dry-season water -> sumur bor
    "i_forest":     {"group": "u", "direction": -1, "weight": 1.0},   # intact forest needs less
    # Climate layers are 4-25 km, so they are constant inside a KHG. Within a KHG they only vary through the
    # interpolation between cells or, for the water balance, through forest interception (forest then looks
    # drier, which cancels i_forest). Off until the neraca air module gives a sub-KHG water balance.
    # Set a weight in `indicators:` to use them anyway (e.g. with normalise_scope: all).
    **{k: {"weight": 0.0} for k in ("u_wb_mean", "u_deficit_months", "u_deficit", "u_deficit_elnino",
                                    "u_dryspell", "u_spell14")},
}

# The eight indicators of the earlier method. Direction +1: a higher value means more need, so it gets rank 1.
# Peat depth is +1 as on the slide (more peat, more at stake). The slide words the other seven the opposite way
# ("higher NDMI, smaller rank number"), which would put the best-conditioned sub-KHG first; here rank 1 is always
# the highest priority. The last four come from the neraca air module and the rainfall layers.
RANKSUM_INDICATORS = {
    "u_ndmi": -1,                 # drier land
    "u_ndvi": -1,                 # less green
    "i_peat_depth": +1,           # thicker peat
    "u_storage_decline_pct": +1,  # neraca air module (not built yet)
    "u_wb_daily_mean": -1,        # neraca air module (not built yet): lower balance
    "u_deficit_months": +1,       # more months in deficit
    "u_dry_days_mean": +1,        # longer dry runs
    "u_hotspot": +1,              # more hotspots
}


def _need_cfg(cfg: dict) -> dict:
    """Config with the need indicator settings underneath the user's own overrides."""
    c = copy.deepcopy(cfg)
    user = c.get("indicators") or {}
    c["indicators"] = {k: {**v, **(user.get(k) or {})} for k, v in NEED_INDICATORS.items()}
    c["indicators"].update({k: v for k, v in user.items() if k not in NEED_INDICATORS})
    return c


def ranksum(df: pd.DataFrame, sc: dict) -> tuple[pd.DataFrame, dict]:
    """Rank-sum score per unit.

    Each indicator ranks the units 1..n (1 = most need, ties share the average rank), within each KHG when
    scoring.normalise_scope is "khg". skor_ranksum = sum of rank x weight, as on the slide (weights 1 each).
    A unit missing an indicator is scaled up to the full weight. `scoring.ranksum_columns` maps a slide indicator to a
    different column of the table (e.g. u_deficit_months -> u_deficit_months_dry from the neraca air module). skor_ranksum_rel is the same on a 0-1 scale
    (0 = rank 1 everywhere, 1 = last everywhere) so units of KHG with different numbers of sub-KHG compare.
    """
    weights = {k: 1.0 for k in RANKSUM_INDICATORS}
    weights.update({k: float(v) for k, v in (sc.get("ranksum_weights") or {}).items()})
    dirs = {**RANKSUM_INDICATORS, **{k: int(v) for k, v in (sc.get("ranksum_directions") or {}).items()}}
    wanted = [k for k, w in weights.items() if w > 0]
    src = {k: (sc.get("ranksum_columns") or {}).get(k, k) for k in weights}     # slide indicator -> column of df
    cols = [k for k in wanted if src[k] in df.columns]
    groups = [g.index for _, g in df.groupby("khg_id")] if sc.get("normalise_scope", "all") == "khg" else [df.index]
    raw = pd.DataFrame(np.nan, index=df.index, columns=cols)
    rel = raw.copy()
    used = []
    for c in cols:
        for idx in groups:
            x = df.loc[idx, src[c]].astype(float)
            n = int(x.notna().sum())
            if n < 2 or x.nunique() < 2:
                continue
            r = x.rank(ascending=dirs[c] < 0, method="average")
            raw.loc[idx, c] = r
            rel.loc[idx, c] = (r - 1) / (n - 1)
        if raw[c].notna().any():
            used.append(c)
        else:
            log.warning("ranksum: indicator %s has no values or no spread; skipped", c)
    if not used:
        raise ValueError("ranksum: none of the indicators is available: " + ", ".join(wanted))
    w = pd.Series({c: weights[c] for c in used})
    w_av = raw[used].notna().mul(w).sum(axis=1)
    total = raw[used].fillna(0).mul(w).sum(axis=1) * (w.sum() / w_av.where(w_av > 0))
    out = pd.DataFrame({"skor_ranksum": total,
                        "skor_ranksum_rel": rel[used].fillna(0).mul(w).sum(axis=1) / w_av.where(w_av > 0),
                        "cakupan_ranksum": w_av / sum(weights[k] for k in wanted)}, index=df.index)
    for c in used:
        out["rk_" + c] = raw[c]
    info = {"used": used, "missing": [k for k in wanted if k not in used],
            "weights": {c: weights[c] for c in used}, "directions": {c: dirs[c] for c in used}}
    if info["missing"]:
        log.info("ranksum: not available: %s", ", ".join(info["missing"]))
    return out, info


def score_need(df: pd.DataFrame, cfg: dict) -> tuple[pd.DataFrame, dict]:
    cfg = _need_cfg(cfg)
    sc = cfg["scoring"]
    method = sc.get("method") or "need"
    if method not in ("need", "ranksum"):
        raise ValueError(f"scoring.method must be 'need' or 'ranksum', not {method!r}")
    spec, ahp_info = SC.resolve_weights(cfg)
    norm = SC.normalise_scoped(df, spec, sc)
    out = pd.concat([df, norm], axis=1)

    out["skor_urgensi"], out["cakupan_urgensi"] = SC.group_score(norm, spec, "u")      # need
    if "tidal_share" in out and sc.get("tidal_mode") == "downweight":
        out["skor_urgensi"] *= 1 - float(sc["tidal_factor"]) * out["tidal_share"].fillna(0)
    out["skor_dampak"], out["cakupan_dampak"] = SC.group_score(norm, spec, "i")        # stakes
    out["skor_kelayakan"], out["cakupan_kelayakan"] = SC.group_score(norm, spec, "f")  # not ranked
    a = float(sc["alpha_urgency"])
    out["skor_need"] = a * out["skor_urgensi"] + (1 - a) * out["skor_dampak"].fillna(out["skor_urgensi"])

    # the earlier rank-sum method, always computed so the two can be compared
    try:
        rs, rs_info = ranksum(df, sc)
    except ValueError:
        if method == "ranksum":
            raise
        rs, rs_info = None, {"used": [], "missing": list(RANKSUM_INDICATORS)}
    if rs is not None:
        out = pd.concat([out, rs], axis=1)
        out["skor_ranksum_need"] = 1 - out["skor_ranksum_rel"]           # higher = more need, like skor_need

    # skor_risiko is the ranking score (higher = more need); name kept for shared validation and maps
    out["skor_risiko"] = out["skor_ranksum_need"] if method == "ranksum" else out["skor_need"]

    q1, q2 = out["skor_risiko"].quantile([1 / 3, 2 / 3])
    out["kelas"] = np.where(out["skor_risiko"] >= q2, NEED_CLASSES[0],
                            np.where(out["skor_risiko"] >= q1, NEED_CLASSES[1], NEED_CLASSES[2]))
    if "tidal_share" in out and sc.get("tidal_mode") == "exclude":
        out.loc[out["tidal_share"].fillna(0) >= 0.5, "kelas"] = SC.CLASS_ORDER[5]
    if "porsi_dikecualikan" in out:
        out.loc[out["porsi_dikecualikan"].fillna(0) >= 0.5, "kelas"] = SC.CLASS_ORDER[6]
    order = {c: i for i, c in enumerate(NEED_CLASSES + SC.CLASS_ORDER[5:])}
    out["urutan_kelas"] = out["kelas"].map(order)
    out["peringkat_need"] = out["skor_need"].rank(ascending=False, method="min")
    if rs is not None:
        out["peringkat_ranksum"] = out["skor_ranksum_need"].rank(ascending=False, method="min")
    out = out.sort_values(["urutan_kelas", "skor_risiko"], ascending=[True, False])
    out["peringkat"] = np.arange(1, len(out) + 1)

    report = {"method": method, "weights": {k: v["weight"] for k, v in spec.items()}, "ahp": ahp_info,
              "class_thresholds": {"need": [float(q1), float(q2)]},
              "indicators_used": [c[2:] for c in norm.columns],
              "class_counts": out["kelas"].value_counts().to_dict(), "ranksum": rs_info}
    if rs is not None:
        k = max(1, int(round(0.2 * len(out))))
        top_n = set(out.nsmallest(k, "peringkat_need").index)
        top_r = set(out.nsmallest(k, "peringkat_ranksum").index)
        rho = out["skor_need"].corr(out["skor_ranksum_need"], method="spearman")
        report["ranking_agreement"] = {"spearman": None if not np.isfinite(rho) else float(rho),
                                       f"top{k}_overlap": len(top_n & top_r) / k, "n_units": int(len(out))}
        log.info("need score and rank-sum: Spearman %.2f, top %d overlap %d of %d",
                 rho, k, len(top_n & top_r), k)
    report.update(SC.correlation_report(norm, sc))
    if method == "need" and sc["sensitivity_runs"] > 0:
        out, report["sensitivity"] = SC.sensitivity(
            out, norm, spec, sc, p_col="p_kebutuhan_tinggi",
            high_fn=lambda r, f: r >= r.quantile(2 / 3))
    report["validation"] = SC.validate(out, sc)
    return out, report
