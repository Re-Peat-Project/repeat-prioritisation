#!/usr/bin/env python3
"""Final national prioritisation of the KHG: four dimensions, a typology, validation and sensitivity.

  repeat-national-final --config configs/examples/national_profile.yaml

Every KHG gets four dimension scores, each the weighted mean of its indicators' percentile ranks (0-1, higher = more) among the
scoring pool (KHG with at least `final.min_peat_km2` of peat):
  urgency      risk of burning and further degradation       (fire history, hotspots, SKEG 2024 damage, canal-affected peat)
  stake        what is lost if it burns or drains            (deep peat, dome, protected FEG, peat area)
  complexity   how hard it is to act                         (tenure complexity, number of actor types, villages involved)
  feasibility  how easy rewetting is                         (dry-season water balance, existing BRGM structures)
and a type from urgency, complexity and stake (terciles of the pool):
  A  quick action                 urgency high, complexity low or medium
  B  multi-party coordination     urgency high, complexity high
  C  staged restoration           urgency medium
  D  protect and monitor          urgency low, stake high
  E  monitor                      urgency low, stake low or medium
Amendment 2026-11-17, after the first run and before any use: 99 of KLH's 337 have less than 25 km2 of KLH peat (median 9.7 km2;
together 0.09% of the 337's SKEG-damaged peat) and fell out of the pool, contrary to the agreed aim of ranking the 337. With
`final.score_all_337_with_peat: true` they are scored and typed against the pool's distribution (percentiles and tercile cuts
from the pool only, so the pool's results do not change) and flagged as less reliable; the 10 without any KLH peat stay unscored.
Ranks: within the type (by urgency, then stake) and overall by urgency, both among the pool and among KLH's 337 work-list KHG.
Feasibility does not change the type: a low tercile is flagged (`flag_low_feasibility`). Indicators that cover too few KHG are
reported, not scored (SiTMAT water-table depth: 164 KHG).

The rule (indicators, directions, weights, pool, typology, validation, sensitivity) is the `final` section of the config, written
2026-11-17 before any result; it is copied into final_meta.json. Inputs, all per KHG and already produced by the project:
  <out>/operational/profile.csv            fire and hotspot indicators (repeat-national-profile --mode operational, baseline to 2025)
  <out>/ppeg/ppeg_khg.csv                  KLH PPEG sums: peat, SKEG damage, dome, thickness, FEG, canal-affected, actors
  <out>/tenure_complexity/tenure_complexity.csv   tenure complexity v2
  <hub>/sites/khg_availability.csv         dry-season water balance, BRGM blocks, run class
  <hub>/sites/khg_klh_priority.csv         KLH 337 work list and the 362 PPEG priority KHG
Validation (pre-registered): urgency without this year's hotspots against the burned share of peat in the current year
(`u_burned_now`, BA_2026), next to fire history alone: Spearman, AUC (burned or not), share of this year's burned peat captured by
the top 20%. Sensitivity: `final.sensitivity.runs` draws multiplying every weight by U(0.5, 1.5); share of KHG keeping their type
and the median spread of the urgency rank.
Writes <out>/final/: final_khg.csv (one row per KHG), final_types.csv, final_gaps.csv, final_validation.json, final_meta.json.
"""
from __future__ import annotations

import argparse
import json
import logging
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

from repeat_prioritisation.national import land as L

log = logging.getLogger("prioritas.final")
TYPES = {"A": ("Aksi cepat", "Quick action"), "B": ("Koordinasi multipihak", "Multi-party coordination"),
         "C": ("Pemulihan bertahap", "Staged restoration"), "D": ("Lindungi dan pantau", "Protect and monitor"),
         "E": ("Pantau", "Monitor")}


def indicators(cfg, hub):
    out = Path(cfg["out"])
    prof = pd.read_csv(out / "operational" / "profile.csv")
    pp = pd.read_csv(out / "ppeg" / "ppeg_khg.csv")
    pp = pp[pp.khg_code.astype(str).str.startswith("KHG.")]
    tc = pd.read_csv(out / "tenure_complexity" / "tenure_complexity.csv")
    av = pd.read_csv(hub / "sites" / "khg_availability.csv")
    kp = pd.read_csv(hub / "sites" / "khg_klh_priority.csv")
    d = kp[["khg_code", "khg_name", "island", "provinces", "klh_337", "klh_337_team", "klh_priority_362", "priority_reason"]].copy()
    d = d.merge(prof[["khg_id", "u_fire_freq", "u_burn_repeat", "u_hotspot", "u_hotspot_now", "u_burned_now", "n_desa_target",
                      "n_dmpg", "n_tma_stations", "tma_deep_share"]].rename(columns={"khg_id": "khg_code"}), on="khg_code", how="left")
    p = pp.set_index("khg_code")
    peat = p["peat_ha"].replace(0, np.nan)
    ind = pd.DataFrame(index=p.index)
    ind["peat_km2"] = p["peat_ha"] / 100
    ind["damage_share"] = p["priority_ha"] / peat
    ind["canal_share"] = p["peat_canal_ha"] / peat
    ind["thick3m_share"] = p["peat_thick3m_ha"] / peat
    ind["dome_share"] = p["peat_dome_ha"] / peat
    ind["protected_share"] = p["peat_protected_feg_ha"] / peat
    act = p[["priority_company_ha", "priority_company_buffer_ha", "priority_mofor_ha", "priority_klh_ha"]]
    ind["actor_types"] = (act > 0).sum(axis=1)
    ind["priority_ha"] = p["priority_ha"]
    d = d.merge(ind.reset_index(), on="khg_code", how="left")
    d = d.merge(tc[["khg_id", "tenure_complexity", "c_contested", "c_holders"]].rename(columns={"khg_id": "khg_code"}), on="khg_code", how="left")
    d["villages"] = d["n_desa_target"].fillna(0) + d["n_dmpg"].fillna(0)
    a = av.set_index("code")
    a.index = "KHG." + a.index.astype(str)        # khg_availability codes carry no "KHG." prefix
    d["dry_balance_mm"] = d.khg_code.map(a["dry_shortfall_mm"])
    d["brgm_blocks_per_km2"] = d.khg_code.map(a["blocks_brgm"]) / d["peat_km2"].replace(0, np.nan)
    d["run_class"] = d.khg_code.map(a["run_class"])
    return d


def pct_against(x, ref):
    """Percentile of each value of x within the reference values (mid-rank for ties), so KHG outside the pool are scored
    against the pool without moving its distribution."""
    r = np.sort(ref.dropna().to_numpy())
    if not len(r):
        return pd.Series(np.nan, index=x.index)
    lo, hi = np.searchsorted(r, x.to_numpy(), "left"), np.searchsorted(r, x.to_numpy(), "right")
    out = pd.Series((lo + hi) / 2 / len(r), index=x.index)
    return out.where(x.notna())


def score(d, pool, spec, w_mult=None, scored=None):
    """Weighted mean of percentile ranks against the pool; missing indicators are left out of the mean for that KHG.
    `scored` (default: the pool) are the KHG that get a score."""
    scored = pool if scored is None else scored
    num, den = pd.Series(0.0, index=d.index), pd.Series(0.0, index=d.index)
    for name, s in spec.items():
        w = s["weight"] * (w_mult.get(name, 1.0) if w_mult else 1.0)
        if not w:
            continue
        x = d[name] if s.get("direction", "+") == "+" else -d[name]
        r = pct_against(x, x[pool])
        ok = r.notna()
        num[r.index[ok]] += w * r[ok]
        den[r.index[ok]] += w
    out = num / den.replace(0, np.nan)
    out[~scored] = np.nan
    return out


def classify(u, c, s, pool, scored=None):
    scored = pool if scored is None else scored
    q = lambda x: (x[pool].quantile(1 / 3), x[pool].quantile(2 / 3))
    (u1, u2), (c1, c2), (s1, s2) = q(u), q(c), q(s)
    t = pd.Series(pd.NA, index=u.index, dtype="object")
    hi_u, mid_u, lo_u = u >= u2, (u >= u1) & (u < u2), u < u1
    t[hi_u & (c < c2)] = "A"
    t[hi_u & (c >= c2)] = "B"
    t[mid_u] = "C"
    t[lo_u & (s >= s2)] = "D"
    t[lo_u & (s < s2)] = "E"
    t[hi_u & c.isna()] = "A"
    t[lo_u & s.isna()] = "E"
    t[~scored] = pd.NA
    return t, {"urgency": [u1, u2], "complexity": [c1, c2], "stake": [s1, s2]}


def auc(score_, positive):
    s, y = score_[score_.notna() & positive.notna()], positive[score_.notna() & positive.notna()].astype(bool)
    if y.sum() == 0 or (~y).sum() == 0:
        return None
    r = s.rank()
    return float((r[y].sum() - y.sum() * (y.sum() + 1) / 2) / (y.sum() * (~y).sum()))


def capture(score_, value, weight, top=0.2):
    ok = score_.notna() & value.notna()
    s, v = score_[ok], (value * weight)[ok]
    k = max(1, int(round(top * len(s))))
    return float(v[s.nlargest(k).index].sum() / v.sum()) if v.sum() > 0 else None


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    rule = cfg["final"]
    hub = Path(cfg.get("hub") or Path(cfg["registry"]).parents[1])
    d = indicators(cfg, hub)
    pool = d["peat_km2"].fillna(0) >= rule["min_peat_km2"]
    scored = pool | (d.klh_337 & (d["peat_km2"].fillna(0) > 0)) if rule.get("score_all_337_with_peat") else pool
    d["in_pool"] = pool
    dims = rule["dimensions"]
    for k, spec in dims.items():
        d[k] = score(d, pool, spec, scored=scored)
    d["type"], cuts = classify(d["urgency"], d["complexity"], d["stake"], pool, scored)
    d["type_id"] = d["type"].map(lambda t: TYPES[t][0] if isinstance(t, str) else pd.NA)
    d["type_en"] = d["type"].map(lambda t: TYPES[t][1] if isinstance(t, str) else pd.NA)
    f1 = d.loc[pool, "feasibility"].quantile(1 / 3)
    d["flag_low_feasibility"] = scored & (d["feasibility"] < f1)
    d["rank_urgency"] = d["urgency"].rank(ascending=False, method="min").astype("Int64")
    d["rank_urgency_337"] = d["urgency"].where(d.klh_337).rank(ascending=False, method="min").astype("Int64")
    d["rank_in_type"] = (d.assign(_k=d["urgency"] + 1e-6 * d["stake"].fillna(0)).groupby("type")["_k"]
                         .rank(ascending=False, method="min").astype("Int64"))
    # validation: urgency without this year's hotspots against this year's burned share of peat
    v = rule["validation"]
    spec_v = {k: s for k, s in dims["urgency"].items() if k not in v["exclude"]}
    u_v = score(d, pool, spec_v)
    fire = score(d, pool, {"u_fire_freq": {"weight": 1}})
    tgt = d[v["target"]]
    burned = (tgt > 0).where(tgt.notna())
    val = {"target": v["target"], "n_pool": int(pool.sum()), "n_burned": int(burned[pool].sum()), "excluded": v["exclude"]}
    for name, s in (("urgency", u_v), ("fire_history_only", fire)):
        ok = pool & tgt.notna()
        val[name] = {"spearman": round(float(s[ok].corr(tgt[ok], method="spearman")), 3),
                     "auc": None if auc(s[ok], burned[ok]) is None else round(auc(s[ok], burned[ok]), 3),
                     "capture_top20pct": None if capture(s[ok], tgt[ok], d.loc[ok, "peat_km2"]) is None else round(capture(s[ok], tgt[ok], d.loc[ok, "peat_km2"]), 3)}
    # sensitivity
    rng = np.random.default_rng(rule["sensitivity"]["seed"])
    keep, ranks = [], []
    for _ in range(rule["sensitivity"]["runs"]):
        sc = {k: score(d, pool, spec, {n: rng.uniform(0.5, 1.5) for n in spec}) for k, spec in dims.items()}
        t, _ = classify(sc["urgency"], sc["complexity"], sc["stake"], pool)
        keep.append((t == d["type"])[pool].to_numpy())
        ranks.append(sc["urgency"][pool].rank(ascending=False).to_numpy())
    d.loc[pool, "type_stability"] = np.mean(keep, axis=0)
    d.loc[pool, "rank_urgency_sd"] = np.std(ranks, axis=0)
    sens = {"runs": rule["sensitivity"]["runs"], "share_keeping_type_mean": round(float(np.mean(keep)), 3),
            "share_khg_type_stable_80pct": round(float((np.mean(keep, axis=0) >= 0.8).mean()), 3),
            "median_rank_sd": round(float(np.median(np.std(ranks, axis=0))), 1)}
    out = Path(cfg["out"]) / "final"
    out.mkdir(parents=True, exist_ok=True)
    d.round(5).to_csv(out / "final_khg.csv", index=False)
    pk = d[scored]
    types = (pk.groupby(["type", "type_id", "type_en"]).agg(khg=("khg_code", "size"), in_337=("klh_337", "sum"),
             peat_km2=("peat_km2", "sum"), priority_ha=("priority_ha", "sum"), low_feasibility=("flag_low_feasibility", "sum"))
             .reset_index())
    types.round(1).to_csv(out / "final_types.csv", index=False)
    gaps = pd.concat([
        d[d.klh_priority_362 & ~d.klh_337].assign(gap="PPEG priority (362) outside the 337"),
        d[pool & ~d.klh_priority_362 & (d["urgency"] >= cuts["urgency"][1])].assign(gap="high urgency outside the 362"),
        d[d.klh_337 & ~scored].assign(gap="in the 337 without KLH peat (not scored)"),
        d[d.klh_337 & scored & ~pool].assign(gap="in the 337 with less than min_peat_km2 of peat (scored against the pool, less reliable)"),
    ])[["gap", "khg_code", "khg_name", "island", "peat_km2", "urgency", "type", "priority_reason"]]
    gaps.round(4).to_csv(out / "final_gaps.csv", index=False)
    (out / "final_validation.json").write_text(json.dumps({"validation": val, "sensitivity": sens}, indent=1), encoding="utf-8")
    (out / "final_meta.json").write_text(json.dumps({"rule": rule, "run": str(date.today()), "tercile_cuts": {k: [round(x, 4) for x in v] for k, v in cuts.items()},
                                                     "feasibility_low_cut": round(float(f1), 4), "pool": int(pool.sum()), "scored": int(scored.sum())}, indent=1, default=str), encoding="utf-8")
    log.info("%d KHG, %d in the pool -> %s", len(d), pool.sum(), out)
    log.info("validation %s", val)
    log.info("sensitivity %s", sens)


if __name__ == "__main__":
    main()
