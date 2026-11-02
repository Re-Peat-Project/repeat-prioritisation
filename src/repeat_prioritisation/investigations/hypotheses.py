#!/usr/bin/env python3
"""Hypothesis tests on the 2026 fire season, by land tenure and place.

  repeat-hypotheses --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--boot 1000] [--seed 1] [--force]

Context: in 2026 the forest area (kawasan hutan) without a licence burned far above its own 2015-2025 level in several KHG. The
questions below test explanations that were put forward (water not held at the dome, drainage by neighbouring licences, the dry
season, management). Every question has a prediction and a verdict rule fixed here, in code, before any run: a result is "supports",
"rejects" or "inconclusive" by the rule, never by reading the number afterwards.

Inputs, all on disk (nothing is typed in): the tenure tables of `repeat-national-tenure` (34 KHG), the cell panels built here from the
licence-edge runs (14 KHG with a DTM; `hyp_panel`), the KHG-level rain and evapotranspiration by dekad (`03_neraca/inputs/khg_level`).
Every year is compared over the same calendar window (1 January to the last day of 2026 data). Baseline: 2015-2025.

Writes <out>/hypotheses/: hypotheses.json (the page of the dashboard reads it), one CSV per question, provenance.json (input
fingerprints, thresholds, seed, versions). Random draws (bootstrap, permutations) use the seed, so a rerun on the same data gives
the same numbers."""
from __future__ import annotations

import argparse
import datetime
import json
import logging
import platform
from pathlib import Path

import numpy as np
import pandas as pd
import scipy
from scipy import stats

from repeat_common import khg as K
from repeat_prioritisation.investigations import hyp_panel as HP
from repeat_prioritisation.investigations.hyp_stats import did_estimate, mann_kendall, moran_i, spearman
from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import profile as P

log = logging.getLogger("prioritas.hypotheses")
BASE_Y = list(range(2015, 2026))
NB = len(BASE_Y)
EFFECT = 1.25                     # a ratio of increases below this is not a meaningful excess; "supports" needs the interval above 1 and the estimate at or above it
TENURE_LABEL = {"licence": "Business licence", "forest": "Forest area, no licence", "other_land": "Other land"}
NEAR_LIC_M, FAR_LIC_M = 1000.0, (3000.0, 10000.0)      # forest cells within 1 km of a licence against 3-10 km away
NEAR_CANAL_M, FAR_CANAL_M = 500.0, 2000.0
ROAD_M = 1000.0
PANEL_COLS = ["khg_id", "x", "y", "bx", "by", "tenure", "sub", "dmpg", "position", "canal_m", "dist_lic_m", "road_m"] + [f"n_{y}" for y in HP.YEARS] \
    + [f"h_{y}" for y in HP.YEARS] + [f"ba_{y}" for y in HP.BA_YEARS + [2026]]


# ---------------------------------------------------------------------------------------------------------------- helpers

def clean(o):
    """JSON-safe copy: numpy scalars to Python, NaN and infinity to null."""
    if isinstance(o, dict):
        return {str(k): clean(v) for k, v in o.items()}
    if isinstance(o, (list, tuple)):
        return [clean(v) for v in o]
    if isinstance(o, (np.bool_, bool)):
        return bool(o)
    if isinstance(o, (np.integer, int)):
        return int(o)
    if isinstance(o, (np.floating, float)):
        return float(o) if np.isfinite(o) else None
    return o


def has_edge_run(kid):
    try:
        return (K.folder(kid.replace("KHG.", "", 1)) / "04_prioritisation" / "licence_edge" / "cells.csv.gz").exists()
    except Exception:       # a KHG without a folder or a registry entry
        return False


def f2(v):
    return "n/a" if v is None or not np.isfinite(v) else f"{v:.2f}"


def ci_text(r):
    return "no estimate" if r["ratio"] is None else f"ratio {r['ratio']:.2f} (95% interval {f2(r['lo'])} to {f2(r['hi'])}; {r['n_clusters']} clusters, {r['n_strata']} strata)"


def verdict_up(r, effect=EFFECT):
    """The group rose more than the reference: supports when the interval is above 1 and the ratio is at least `effect`; rejects when the
    upper end is below `effect`; otherwise inconclusive."""
    if r["ratio"] is None or r["lo"] is None:
        return "inconclusive", "Too few detections for an estimate."
    if r["lo"] > 1 and r["ratio"] >= effect:
        return "supports", ci_text(r)
    if r["hi"] < effect:
        return "rejects", ci_text(r) + (": the group rose less than the reference" if r["hi"] < 1 else "")
    return "inconclusive", ci_text(r)


def others_text(res, skip="forest"):
    """The same test in the other tenure classes, for the reader to see whether the result is specific to forest area."""
    return " Same test in the other classes: " + "; ".join(f"{TENURE_LABEL[t].lower()} {r['ratio']:.2f} ({f2(r['lo'])} to {f2(r['hi'])})" for t, r in res.items() if t != skip and r["ratio"] is not None) + "."


def ci_row(label, r, kind="khg", note=""):
    return {"label": label, "ratio": r["ratio"], "lo": r["lo"], "hi": r["hi"], "kind": kind, "note": note or f"{r['a']} vs {r['b']} in 2026"}


def counts(p, conf):
    pre = "h_" if conf == "high" else "n_"
    return p[f"{pre}2026"].to_numpy(), sum(p[f"{pre}{y}"] for y in BASE_Y).to_numpy()


def did_rows(p, mask, g1, g0, strat, conf="nh"):
    """Rows (cluster = KHG and 5 km block, stratum = KHG and the strat label) with the counts of group 1 and group 0 in 2026 and in the baseline."""
    n26, base = counts(p, conf)
    d = pd.DataFrame({"khg": p["khg_id"].to_numpy(), "bx": p["bx"].to_numpy(), "by": p["by"].to_numpy(), "strat": strat, "n26": n26, "base": base, "g1": g1, "g0": g0})
    d = d[np.asarray(mask) & (d["g1"] | d["g0"])]
    d = d.assign(a=d.n26 * d.g1, c=d.base * d.g1, b=d.n26 * d.g0, d=d.base * d.g0)
    r = d.groupby(["khg", "bx", "by", "strat"], as_index=False)[["a", "c", "b", "d"]].sum()
    return r.assign(cluster=r.khg + ":" + r.bx.astype(str) + ":" + r.by.astype(str), stratum=r.khg + "|" + r.strat)


def band_table(p, mask, col, edges, labels, cell_km2, conf="nh"):
    """Hotspots per 100 km2 of peat by band of a distance column: 2026 and the mean of 2015-2025."""
    n26, base = counts(p, conf)
    v = p[col].to_numpy()
    out = []
    for (lo, hi), lab in zip(zip(edges[:-1], edges[1:]), labels):
        m = np.asarray(mask) & (v > lo) & (v <= hi) if lo > 0 else np.asarray(mask) & (v >= lo) & (v <= hi)
        area = m.sum() * cell_km2
        out.append({"band": lab, "cells": int(m.sum()), "area_km2": area, "n2026": int(n26[m].sum()), "base_mean": float(base[m].sum() / NB),
                    "rate2026": float(100 * n26[m].sum() / area) if area else None, "rate_base": float(100 * base[m].sum() / NB / area) if area else None})
    return out


def groups_viz(title, rows, unit="hotspots per 100 km² of peat"):
    return {"type": "groups", "title": title, "unit": unit, "groups": [{"label": r["band"], "note": f"{r['area_km2']:.0f} km²", "series": [
        {"name": "mean 2015 to 2025", "value": r["rate_base"]}, {"name": "2026", "value": r["rate2026"]}]} for r in rows]}


def sample_pick(scores: dict, n=2, descending=True):
    return [k for k, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=descending)[:n]]


def rate_groups(df, key_col, title):
    """df rows: key, peat, n26, base (sum over baseline years)."""
    return {"type": "groups", "title": title, "unit": "hotspots per 100 km² of peat", "groups": [
        {"label": TENURE_LABEL.get(r[key_col], r[key_col]), "note": f"{r['peat']:.0f} km²", "series": [
            {"name": "mean 2015 to 2025", "value": 100 * r["base"] / NB / r["peat"]}, {"name": "2026", "value": 100 * r["n26"] / r["peat"]}]} for _, r in df.iterrows() if r["peat"] >= 5]}


# ---------------------------------------------------------------------------------------------------------------- data

def tenure_tables(cfg, conf):
    d = Path(cfg["out"]) / "tenure"
    area = pd.read_csv(d / "tenure_area.csv")
    hot = pd.read_csv(d / "tenure_hotspots.csv")
    hot = hot[hot["ytd"]]
    if conf == "high":
        hot = hot[hot["conf"] == "high"]
    return area, hot, [d / "tenure_area.csv", d / "tenure_hotspots.csv"]


def load_panels(cfg, ids, out, force):
    panels, hots, metas = {}, {}, {}
    for kid in ids:
        r = HP.build(cfg, kid, out, force)
        if r is None:
            log.info("%s: no licence-edge run, skipped in the cell tests", kid)
            continue
        panels[kid] = pd.read_parquet(r[0], columns=PANEL_COLS)
        hots[kid] = pd.read_parquet(r[1])
        metas[kid] = r[2]
        log.info("%s: %d cells", kid, len(panels[kid]))
    return panels, hots, metas


# ---------------------------------------------------------------------------------------------------------------- questions

def q_scar(panels, names, meta, **_):
    """Are the hotspot rises real burns? 2026 burnt-area share against the hotspot ratio, by KHG and tenure class."""
    rows = []
    for kid, p in panels.items():
        n26, base = counts(p, "nh")
        for ten, g in p.groupby("tenure"):
            if len(g) * meta[kid]["cell_m"] ** 2 / 1e6 < 20:
                continue
            ba_base = float(np.mean([g[f"ba_{y}"].mean() for y in HP.BA_YEARS]))
            ba26 = float(g["ba_2026"].mean())
            idx = g.index
            rows.append({"khg_id": kid, "khg": names[kid], "tenure": ten, "peat_km2": len(g) * meta[kid]["cell_m"] ** 2 / 1e6, "hot_ratio": (n26[idx].sum() + 0.5) / (base[idx].sum() / NB + 0.5),
                         "burn_share_2026": ba26, "burn_share_base_mean": ba_base, "burn_ratio": (ba26 + 0.005) / (ba_base + 0.005), "n2026": int(n26[idx].sum())})
    t = pd.DataFrame(rows)
    # the 2026 burnt-area layer must exist where the hotspots are: a KHG counts only if at least 1 km2 of its peat lies in a 2026 polygon
    scar_km2 = {k: float(p["ba_2026"].sum() * (meta[k]["cell_m"] / 1000) ** 2) for k, p in panels.items()}
    covered = [k for k, v in scar_km2.items() if v >= 1.0]
    hot_khg = [k for k, p in panels.items() if p["n_2026"].sum() >= 100]
    t["scar_layer_covers_khg"] = t["khg_id"].isin(covered)
    sp = spearman(np.log(t.loc[t.scar_layer_covers_khg, "hot_ratio"]), np.log(t.loc[t.scar_layer_covers_khg, "burn_ratio"]))
    label, why = "not testable", f"The 2026 burnt-area layer holds at least 1 km² of scar in {len(covered)} of the {len(panels)} KHG ({sum(k in covered for k in hot_khg)} of the {len(hot_khg)} KHG with 100 or more detections in 2026); {sp['n']} units are left, fewer than 8."
    if sp["n"] >= 8:
        label = "supports" if sp["rho"] >= 0.5 and sp["p"] < 0.05 else "rejects" if sp["hi"] < 0.5 else "inconclusive"
        why = f"Spearman rho {f2(sp['rho'])} (95% interval {f2(sp['lo'])} to {f2(sp['hi'])}), p {f2(sp['p'])} over {sp['n']} units in the {len(covered)} KHG where the 2026 scar layer has data."
    pts = [{"label": f"{r.khg.replace('KHG ', '')} · {TENURE_LABEL[r.tenure]}", "x": float(r.hot_ratio), "y": float(r.burn_ratio), "group": r.tenure} for r in t.itertuples()]
    return {"id": "q01", "title": "Do the hotspot rises match burn scars?", "group": "Is the signal real?",
            "question": "A hotspot is a satellite detection of heat, not a measure of burned ground. Where hotspots rose in 2026, did the burnt-area polygons rise as well?",
            "prediction": {"supports": "Across KHG and tenure classes, the 2026 hotspot ratio and the 2026 burn-scar ratio rank together (Spearman rho at least 0.5, p below 0.05).",
                           "rejects": "The upper end of the 95% interval of rho is below 0.5: burn scars do not confirm the hotspot pattern. Not testable if fewer than 8 units lie in KHG where the 2026 burnt-area layer has at least 1 km² of scar."},
            "method": ["Unit: a tenure class inside a KHG with at least 20 km² of peat in the cell panel.", "Hotspot ratio: 2026 detections divided by the mean of 2015 to 2025 over the same calendar window.",
                       "Burn-scar ratio: share of the class's peat cells inside a 2026 burnt-area polygon, divided by the mean share of 2015 to 2025 (0.5 percentage points added to both, so an empty class does not divide by zero).",
                       "Spearman rank correlation of the two ratios over all units."],
            "data": ["Cell panels (hotspots, burnt-area polygons BA_2015 to BA_2026 from burnt_area_2015_2026_Indonesia.gpkg)"],
            "result": {"spearman_rho": sp["rho"], "p": sp["p"], "units": sp["n"]},
            "verdict": {"label": label, "reason": why},
            "viz": [{"type": "scatter", "title": "Hotspot ratio against burn-scar ratio (2026 over 2015-2025; one dot per KHG and class; dots outside the KHG where the 2026 scar layer has data are not tested)", "xlabel": "hotspot ratio", "ylabel": "burn-scar ratio", "log": True, "points": pts, "ref": 1}, {"type": "table", "title": "2026 burnt area in the layer, by KHG", "cols": ["KHG", "2026 scar (km² of peat)", "detections in 2026"], "rows": [[names[k].replace("KHG ", ""), f"{scar_km2[k]:.1f}", int(panels[k]["n_2026"].sum())] for k in panels]}],
            "samples": [], "tables": {"q01_scar_vs_hotspot": t}}


def q_tenure(cfg, names, boot, seed, **_):
    area, hot, files = tenure_tables(cfg, "nh")
    hot_h = tenure_tables(cfg, "high")[1]

    def table(h):
        n = h.groupby(["khg_id", "tenure", "year"])["n"].sum().unstack("year").fillna(0)
        t = pd.DataFrame({"n26": n.get(2026, 0), "base": n[[y for y in BASE_Y if y in n.columns]].sum(axis=1)})
        pk = area.groupby(["khg_id", "tenure"])["peat_km2"].sum()
        t["peat"] = pk.reindex(t.index)
        return t.reset_index()

    t, th = table(hot), table(hot_h)

    def pair(tt, A, B, min_peat=20.0):
        a_, b_ = tt[tt.tenure == A].set_index("khg_id"), tt[tt.tenure == B].set_index("khg_id")
        ids = [k for k in a_.index.intersection(b_.index) if a_.loc[k, "peat"] >= min_peat and b_.loc[k, "peat"] >= min_peat]
        return pd.DataFrame({"cluster": ids, "stratum": ids, "a": a_.loc[ids, "n26"].to_numpy(), "c": a_.loc[ids, "base"].to_numpy(), "b": b_.loc[ids, "n26"].to_numpy(), "d": b_.loc[ids, "base"].to_numpy()})

    pairs = [("forest", "licence"), ("forest", "other_land"), ("licence", "other_land")]
    res, rows_csv = {}, []
    for A, B in pairs:
        r = pair(t, A, B)
        res[(A, B)] = did_estimate(r, boot, seed)
        res[(A, B, "high")] = did_estimate(pair(th, A, B), boot, seed)
        for x in r.itertuples():
            lr = np.log((x.a + .5) / (x.c + .5)) - np.log((x.b + .5) / (x.d + .5))
            se = np.sqrt(1 / (x.a + .5) + 1 / (x.c + .5) + 1 / (x.b + .5) + 1 / (x.d + .5))
            rows_csv.append({"a": A, "b": B, "khg_id": x.cluster, "khg": names[x.cluster], "n26_a": x.a, "base_a": x.c, "n26_b": x.b, "base_b": x.d,
                             "ratio": float(np.exp(lr)), "lo_approx": float(np.exp(lr - 1.96 * se)), "hi_approx": float(np.exp(lr + 1.96 * se))})
    csv = pd.DataFrame(rows_csv)
    fl, fo = res[("forest", "licence")], res[("forest", "other_land")]
    v1, v2 = verdict_up(fl)[0], verdict_up(fo)[0]
    label = "supports" if v1 == v2 == "supports" else "rejects" if fl["hi"] is not None and fo["hi"] is not None and fl["hi"] < EFFECT and fo["hi"] < EFFECT else "inconclusive"
    ci_rows = []
    for (A, B), lab in zip(pairs, ["Forest area vs business licence", "Forest area vs other land", "Business licence vs other land"]):
        ci_rows.append(ci_row(lab, res[(A, B)], "pooled", f"{res[(A, B)]['n_clusters']} KHG"))
        ci_rows.append(ci_row(lab + " (high confidence only)", res[(A, B, "high")], "pooled", f"{res[(A, B, 'high')]['n_clusters']} KHG"))
    both = csv[(csv.a == "forest") & (csv.b == "licence")].copy()
    samples = []
    pick = sample_pick(dict(zip(both.khg_id, both.n26_a)), 2) + ([both.sort_values("ratio").khg_id.iloc[0]] if len(both) else [])
    for k in dict.fromkeys(pick):
        why = ("one of the two KHG with the most forest-area detections in 2026 among those with licences" if k in pick[:2] else "the KHG with the lowest forest-versus-licence ratio") + f" ({names[k]})"
        sub = t[t.khg_id == k]
        row = both[both.khg_id == k].iloc[0]
        samples.append({"khg_id": k, "name": names[k], "why": why, "viz": [rate_groups(sub, "tenure", "2026 against the 2015-2025 mean, by tenure class"),
                        {"type": "table", "title": "Counts behind the ratio", "cols": ["", "2026", "2015-2025 total"], "rows": [["Forest area", int(row.n26_a), int(row.base_a)], ["Business licence", int(row.n26_b), int(row.base_b)], ["Ratio of increases", f2(row.ratio), f"{f2(row.lo_approx)} to {f2(row.hi_approx)} (approx.)"]]}]})
    return {"id": "q02", "title": "Is forest area more affected than licence land or other land, in the same KHG?", "group": "Where did fire rise?",
            "question": "The pooled national figures mix places: forest area is mostly in Kalimantan, licences mostly in Sumatra. Within one KHG, did the forest area rise more in 2026 than the licence land and the other land next to it?",
            "prediction": {"supports": f"The forest-area increase is above the licence-land increase and above the other-land increase, each with the interval above 1 and a ratio of at least {EFFECT}.",
                           "rejects": f"The upper end of the interval is below {EFFECT} against both: forest area did not rise more than its neighbours."},
            "method": ["Detections on peat over the same calendar window each year; counts per KHG and tenure class (tenure classes by precedence: licence, forest area without licence, other land).",
                       "Within each KHG: ratio of increases = (forest 2026 / forest 2015-2025 total) divided by (reference 2026 / reference 2015-2025 total). Exposure cancels. A KHG enters if both classes have 20 km² of peat and 10 baseline detections.",
                       "Pooled over KHG by inverse variance; the interval is the 2.5th to 97.5th percentile of a bootstrap that resamples KHG (seed fixed). Medium and high confidence together, and high alone.",
                       "The rows of single KHG use a Poisson approximation for the interval, which is too narrow when counts are large (detections of one KHG are not independent); the verdict rests on the pooled rows. Ratios beyond the axis are drawn at its end."],
            "data": ["tenure_area.csv and tenure_hotspots.csv of repeat-national-tenure (34 KHG)"],
            "result": {"forest_vs_licence": fl, "forest_vs_other": fo},
            "verdict": {"label": label, "reason": f"Forest vs licence: {ci_text(fl)}. Forest vs other land: {ci_text(fo)}."},
            "viz": [{"type": "ci", "title": "Ratio of increases (above 1: the first class rose more than the second)", "ref": 1, "effect": EFFECT, "rows": ci_rows + [ci_row(f"{r.khg.replace('KHG ', '')}", {"ratio": r.ratio, "lo": r.lo_approx, "hi": r.hi_approx, "a": r.n26_a, "b": r.n26_b}, "khg", f"forest {int(r.n26_a)} vs licence {int(r.n26_b)}") for r in both.sort_values("ratio", ascending=False).itertuples()]}],
            "samples": samples, "tables": {"q02_tenure_pairs": csv}}


def q_dmpg(cfg, names, boot, seed, **_):
    area, hot, _f = tenure_tables(cfg, "nh")
    n = hot.groupby(["khg_id", "tenure", "dmpg", "year"])["n"].sum().unstack("year").fillna(0)
    t = pd.DataFrame({"n26": n.get(2026, 0), "base": n[[y for y in BASE_Y if y in n.columns]].sum(axis=1)}).reset_index()
    pk = area.groupby(["khg_id", "tenure", "dmpg"])["peat_km2"].sum().reset_index()
    t = t.merge(pk, on=["khg_id", "tenure", "dmpg"], how="outer").fillna(0)

    def rows(ten):
        x = t if ten is None else t[t.tenure == ten]
        out = []
        for (k, tn), g in x.groupby(["khg_id", "tenure"]):
            yes, no = g[g.dmpg.astype(bool)], g[~g.dmpg.astype(bool)]
            if len(yes) and len(no) and yes.peat_km2.sum() >= 10 and no.peat_km2.sum() >= 10:
                out.append({"cluster": k, "stratum": f"{k}|{tn}", "a": yes.n26.sum(), "c": yes.base.sum(), "b": no.n26.sum(), "d": no.base.sum()})
        return pd.DataFrame(out)

    res = {None: did_estimate(rows(None), boot, seed)}
    for ten in TENURE_LABEL:
        res[ten] = did_estimate(rows(ten), boot, seed)
    r = res[None]
    label = "inconclusive"
    if r["ratio"] is not None and r["hi"] is not None:
        label = "supports" if r["hi"] < 1 and r["ratio"] <= 0.8 else "rejects" if r["lo"] > 0.8 else "inconclusive"
    ci_rows = [ci_row("All classes", r, "pooled", f"{r['n_clusters']} KHG")] + [ci_row(TENURE_LABEL[k], res[k], "pooled", f"{res[k]['n_clusters']} KHG") for k in TENURE_LABEL]
    flat = []
    for (k, tn), g in t.groupby(["khg_id", "tenure"]):
        yes, no = g[g.dmpg.astype(bool)], g[~g.dmpg.astype(bool)]
        if len(yes) and len(no) and yes.peat_km2.sum() >= 10 and no.peat_km2.sum() >= 10:
            flat.append({"khg_id": k, "khg": names[k], "tenure": tn, "peat_dmpg_km2": yes.peat_km2.sum(), "peat_other_km2": no.peat_km2.sum(), "n26_dmpg": yes.n26.sum(), "base_dmpg": yes.base.sum(), "n26_other": no.n26.sum(), "base_other": no.base.sum()})
    csv = pd.DataFrame(flat)
    samples = []
    forest = csv[csv.tenure == "forest"]
    for k in sample_pick(dict(zip(forest.khg_id, forest.n26_dmpg + forest.n26_other)), 2):
        g = csv[csv.khg_id == k]
        grp = [{"label": f"{TENURE_LABEL[x.tenure]} · {lab}", "note": f"{peat:.0f} km²", "series": [{"name": "mean 2015 to 2025", "value": 100 * base / NB / peat}, {"name": "2026", "value": 100 * n26 / peat}]}
               for x in g.itertuples() for lab, peat, base, n26 in (("DMPG village", x.peat_dmpg_km2, x.base_dmpg, x.n26_dmpg), ("outside DMPG", x.peat_other_km2, x.base_other, x.n26_other)) if peat >= 5]
        samples.append({"khg_id": k, "name": names[k], "why": f"one of the two KHG with the most forest-area detections among those with DMPG and non-DMPG land ({names[k]})", "viz": [{"type": "groups", "title": "Inside and outside DMPG villages, by tenure class", "unit": "hotspots per 100 km² of peat", "groups": grp}]})
    return {"id": "q03", "title": "Did DMPG villages see a smaller increase?", "group": "Where did fire rise?",
            "question": "DMPG villages (Desa Mandiri Peduli Gambut) have had programme support. Within the same KHG and tenure class, was the 2026 increase smaller on DMPG village land than on land outside it?",
            "prediction": {"supports": "The DMPG-to-outside ratio of increases is at most 0.8 with the upper end of the interval below 1.", "rejects": "The lower end of the interval is above 0.8: no meaningful reduction. A ratio above 1 means DMPG land rose more."},
            "method": ["Same ratio of increases as the previous question, with DMPG village land as the first group and land outside DMPG villages as the reference, within each KHG and tenure class (10 km² of peat in each).",
                       "Pooled over KHG and classes by inverse variance; the interval comes from a bootstrap that resamples KHG.", "This tests association with the programme area, not the effect of the programme: villages were not chosen at random."],
            "data": ["tenure_area.csv and tenure_hotspots.csv of repeat-national-tenure (34 KHG); DMPG village layer of the SiTMAT portal"],
            "result": {"all": r}, "verdict": {"label": label, "reason": ci_text(r)},
            "viz": [{"type": "ci", "title": "Ratio of increases, DMPG village land against land outside (below 1: smaller increase in DMPG villages)", "ref": 1, "effect": 0.8, "rows": ci_rows}], "samples": samples, "tables": {"q03_dmpg": csv}}


def q_licence_gradient(panels, names, meta, boot, seed, **_):
    cell_km2 = {k: (m["cell_m"] / 1000) ** 2 for k, m in meta.items()}
    parts = []
    for kid, p in panels.items():
        mask = (p.tenure == "forest").to_numpy()
        strat = (p.position + "|c" + (p.canal_m <= NEAR_CANAL_M).astype(int).astype(str) + "|r" + (p.road_m <= ROAD_M).astype(int).astype(str)).to_numpy()
        parts.append(did_rows(p, mask, (p.dist_lic_m <= NEAR_LIC_M).to_numpy(), ((p.dist_lic_m > FAR_LIC_M[0]) & (p.dist_lic_m <= FAR_LIC_M[1])).to_numpy(), strat))
    rows = pd.concat(parts, ignore_index=True)
    pooled = did_estimate(rows, boot, seed)
    per, ci_rows = {}, [ci_row("All KHG", pooled, "pooled", f"{pooled['n_clusters']} blocks")]
    for k in panels:
        per[k] = did_estimate(rows[rows.khg == k], max(200, boot // 4), seed)
        if per[k]["ratio"] is not None:
            ci_rows.append(ci_row(names[k].replace("KHG ", ""), per[k]))
    label, reason = verdict_up(pooled)
    edges, labels = [0, 1000, 3000, 10000, 1e9], ["0-1 km", "1-3 km", "3-10 km", "> 10 km"]
    samples = []
    ok = {k: per[k]["a"] + per[k]["b"] for k in per if per[k]["ratio"] is not None}
    for k in sample_pick(ok, 2):
        bt = band_table(panels[k], (panels[k].tenure == "forest").to_numpy(), "dist_lic_m", edges, labels, cell_km2[k])
        samples.append({"khg_id": k, "name": names[k], "why": f"one of the two KHG with most forest-area detections near and far from licences ({names[k]})", "viz": [groups_viz("Forest area without a licence, by distance to the nearest licence", bt), {"type": "ci", "title": "Ratio of increases, near (0-1 km) against far (3-10 km)", "ref": 1, "effect": EFFECT, "rows": [ci_row(names[k].replace("KHG ", ""), per[k])]}]})
    csv = pd.DataFrame([{"khg_id": k, "khg": names[k], **{kk: v for kk, v in per[k].items()}} for k in per])
    return {"id": "q04", "title": "Is forest next to licences more affected than forest far from them?", "group": "Why there? Mechanisms in space",
            "question": "If licence drainage pulls water out of neighbouring forest, forest within a short distance of a licence should have risen more in 2026 than forest farther away, once dome position, canal distance and road distance are held fixed.",
            "prediction": {"supports": f"Forest within 1 km of a licence rose more than forest 3 to 10 km away: ratio of increases at least {EFFECT} with the interval above 1.", "rejects": f"The upper end of the interval is below {EFFECT}: no gradient with distance."},
            "method": ["Cells: 200 m peat cells of the licence-edge run; forest area without a licence only. Distance to the nearest licence polygon of the 2025 layer (business licences used for the tenure classes).",
                       "Within strata of KHG, dome position (foot, slope, crest), canal within 500 m, road within 1 km: ratio of increases, near against far, pooled by inverse variance.", "The interval resamples 5 km spatial blocks (seed fixed), so that neighbouring cells do not count as independent.",
                       "Licences are the 2025 layer applied to every year; a licence granted or withdrawn since is not represented."],
            "data": ["Cell panels (licence-edge cells.csv.gz, licences, forest area, canals, roads Transportasi_Jalan_Detil.gpkg, VIIRS)"],
            "result": {"pooled": pooled, "per_khg": per}, "verdict": {"label": label, "reason": reason},
            "viz": [{"type": "ci", "title": "Ratio of increases, forest within 1 km of a licence against forest 3 to 10 km away", "ref": 1, "effect": EFFECT, "rows": ci_rows}], "samples": samples, "tables": {"q04_licence_gradient": csv}}


def q_canal(panels, names, meta, boot, seed, **_):
    cell_km2 = {k: (m["cell_m"] / 1000) ** 2 for k, m in meta.items()}
    res, per_ten = {}, {}
    for ten in TENURE_LABEL:
        parts = []
        for kid, p in panels.items():
            strat = (p.position + "|l" + (p.dist_lic_m <= NEAR_LIC_M).astype(int).astype(str)).to_numpy()
            parts.append(did_rows(p, (p.tenure == ten).to_numpy(), (p.canal_m <= NEAR_CANAL_M).to_numpy(), (p.canal_m > FAR_CANAL_M).to_numpy(), strat))
        rows = pd.concat(parts, ignore_index=True)
        res[ten] = did_estimate(rows, boot, seed)
        per_ten[ten] = rows
    r = res["forest"]
    label, reason = verdict_up(r)
    reason += others_text(res)
    ci_rows = [ci_row(TENURE_LABEL[t], res[t], "pooled", f"{res[t]['n_clusters']} blocks") for t in TENURE_LABEL]
    per = {k: did_estimate(per_ten["forest"][per_ten["forest"].khg == k], max(200, boot // 4), seed) for k in panels}
    ci_rows += [ci_row(names[k].replace("KHG ", "") + " (forest)", per[k]) for k in panels if per[k]["ratio"] is not None]
    samples = []
    for k in sample_pick({k: per[k]["a"] + per[k]["b"] for k in per if per[k]["ratio"] is not None}, 2):
        bt = band_table(panels[k], (panels[k].tenure == "forest").to_numpy(), "canal_m", [0, 500, 2000, 1e9], ["0-0.5 km", "0.5-2 km", "> 2 km"], cell_km2[k])
        samples.append({"khg_id": k, "name": names[k], "why": f"one of the two KHG with most forest-area detections near and far from canals ({names[k]})", "viz": [groups_viz("Forest area without a licence, by distance to the nearest canal", bt)]})
    csv = pd.DataFrame([{"khg_id": k, "khg": names[k], "tenure": "forest", **per[k]} for k in per])
    return {"id": "q05", "title": "Is peat close to canals more affected?", "group": "Why there? Mechanisms in space",
            "question": "Canals drain the peat beside them. If drainage drove the 2026 increase, peat within a few hundred metres of a canal should have risen more than peat far from any canal.",
            "prediction": {"supports": f"Forest area within 500 m of a canal rose more than forest more than 2 km from one: ratio at least {EFFECT}, interval above 1.", "rejects": f"The upper end of the interval is below {EFFECT}."},
            "method": ["Distance to the nearest mapped canal (the canal layer used by the licence-edge run). Strata: KHG, dome position, within 1 km of a licence or not.", "Ratio of increases near against far, pooled by inverse variance; block bootstrap (5 km blocks). Run for each tenure class; the verdict follows forest area.",
                       "The canal layer maps channels, not their depth or whether they are blocked: it measures proximity, not drainage."],
            "data": ["Cell panels (canal distance from the licence-edge run)"], "result": {"forest": r, "all": res}, "verdict": {"label": label, "reason": reason},
            "viz": [{"type": "ci", "title": "Ratio of increases, within 500 m of a canal against more than 2 km away", "ref": 1, "effect": EFFECT, "rows": ci_rows}], "samples": samples, "tables": {"q05_canal_proximity": csv}}


def q_dome(panels, names, meta, boot, seed, **_):
    cell_km2 = {k: (m["cell_m"] / 1000) ** 2 for k, m in meta.items()}
    res, rows_t = {}, {}
    for ten in TENURE_LABEL:
        parts = []
        for kid, p in panels.items():
            strat = ("c" + (p.canal_m <= NEAR_CANAL_M).astype(int).astype(str) + "|l" + (p.dist_lic_m <= NEAR_LIC_M).astype(int).astype(str)).to_numpy()
            parts.append(did_rows(p, (p.tenure == ten).to_numpy(), (p.position == "crest").to_numpy(), (p.position == "foot").to_numpy(), strat))
        rows_t[ten] = pd.concat(parts, ignore_index=True)
        res[ten] = did_estimate(rows_t[ten], boot, seed)
    r = res["forest"]
    label, reason = verdict_up(r)
    reason += others_text(res)
    ci_rows = [ci_row(TENURE_LABEL[t], res[t], "pooled", f"{res[t]['n_clusters']} blocks") for t in TENURE_LABEL]
    per = {k: did_estimate(rows_t["forest"][rows_t["forest"].khg == k], max(200, boot // 4), seed) for k in panels}
    ci_rows += [ci_row(names[k].replace("KHG ", "") + " (forest)", per[k]) for k in panels if per[k]["ratio"] is not None]
    samples = []
    for k in sample_pick({k: per[k]["a"] + per[k]["b"] for k in per if per[k]["ratio"] is not None}, 2):
        p = panels[k]
        n26, base = counts(p, "nh")
        grp = []
        for pos in ("crest", "slope", "foot"):
            m = ((p.tenure == "forest") & (p.position == pos)).to_numpy()
            a = m.sum() * cell_km2[k]
            if a >= 5:
                grp.append({"label": pos, "note": f"{a:.0f} km²", "series": [{"name": "mean 2015 to 2025", "value": 100 * base[m].sum() / NB / a}, {"name": "2026", "value": 100 * n26[m].sum() / a}]})
        samples.append({"khg_id": k, "name": names[k], "why": f"one of the two KHG with most forest-area detections on crest and foot ({names[k]})", "viz": [{"type": "groups", "title": "Forest area without a licence, by position on the dome", "unit": "hotspots per 100 km² of peat", "groups": grp}]})
    csv = pd.DataFrame([{"khg_id": k, "khg": names[k], "tenure": "forest", **per[k]} for k in per])
    return {"id": "q06", "title": "Did the dome centre rise more than the dome foot?", "group": "Why there? Mechanisms in space",
            "question": "Water drains first from the crown of a peat dome. If water was not held there, the crest should have risen more than the foot in 2026.",
            "prediction": {"supports": f"Forest-area crest cells rose more than foot cells: ratio at least {EFFECT}, interval above 1.", "rejects": f"The upper end of the interval is below {EFFECT}."},
            "method": ["Position: thirds of the KHG's peat by height above the nearest river (foot, slope, crest), from the DTM the licence-edge run chose.", "Strata: KHG, within 500 m of a canal, within 1 km of a licence. Ratio of increases, crest against foot, pooled by inverse variance; block bootstrap.",
                       "Position depends on the DTM; where no river has a DTM value the run uses height above the lowest 5% of cells."],
            "data": ["Cell panels (dome position from the licence-edge run)"], "result": {"forest": r, "all": res}, "verdict": {"label": label, "reason": reason},
            "viz": [{"type": "ci", "title": "Ratio of increases, crest against foot", "ref": 1, "effect": EFFECT, "rows": ci_rows}], "samples": samples, "tables": {"q06_dome_position": csv}}


def q_spatial(panels, names, meta, seed, **_):
    out, maps = [], {}
    for kid, p in panels.items():
        n26, base = counts(p, "nh")
        bx, by = np.floor(p.x.to_numpy() / 2000).astype(int), np.floor(p.y.to_numpy() / 2000).astype(int)
        d = pd.DataFrame({"bx": bx, "by": by, "n26": n26, "base": base, "cells": 1, "forest": (p.tenure == "forest").to_numpy().astype(float), "licence": (p.tenure == "licence").to_numpy().astype(float)})
        g = d.groupby(["bx", "by"]).sum().reset_index()
        g = g[g.cells >= 10]
        if len(g) < 30:
            continue
        area = g.cells * (meta[kid]["cell_m"] / 1000) ** 2
        anom = ((g.n26 - g.base / NB) / area * 100).to_numpy()
        xy = np.column_stack([g.bx * 2000 + 1000, g.by * 2000 + 1000]).astype(float)
        mi = moran_i(anom, xy, 8, 499, seed)
        from scipy.spatial import cKDTree
        _, idx = cKDTree(xy).query(xy, k=9)
        lag = anom[idx[:, 1:]].mean(axis=1)
        sh = np.column_stack([g.forest / g.cells, g.licence / g.cells])

        def r2(X):
            X = np.column_stack([np.ones(len(anom)), X])
            beta = np.linalg.lstsq(X, anom, rcond=None)[0]
            return float(1 - ((anom - X @ beta) ** 2).sum() / ((anom - anom.mean()) ** 2).sum())

        out.append({"khg_id": kid, "khg": names[kid], "blocks": len(g), "moran_i": mi["i"], "moran_p": mi["p"], "r2_tenure": r2(sh), "r2_neighbours": r2(lag)})
        maps[kid] = [[int(a_), int(b_), float(v)] for a_, b_, v in zip(g.bx, g.by, anom)]
    t = pd.DataFrame(out)
    n_ok = len(t)
    ten_better = int((t.r2_tenure > t.r2_neighbours).sum())
    sp_better = int((t.r2_neighbours > t.r2_tenure + 0.05).sum())
    label = "supports" if n_ok and ten_better >= 2 / 3 * n_ok else "rejects" if n_ok and sp_better >= 2 / 3 * n_ok else "inconclusive"
    samples = []
    for k in sample_pick({r.khg_id: r.blocks for r in t.itertuples()}, 2):
        r = t[t.khg_id == k].iloc[0]
        samples.append({"khg_id": k, "name": names[k], "why": f"one of the two largest KHG in the panel ({names[k]})", "viz": [
            {"type": "map", "title": "2026 increase over the 2015-2025 mean, per 2 km block (hotspots per 100 km² of peat)", "size": 2000, "cells": maps[k]},
            {"type": "table", "title": "Spatial structure", "cols": ["", "value"], "rows": [["Moran's I (8 nearest blocks)", f2(r.moran_i)], ["permutation p", f2(r.moran_p)], ["R² explained by tenure shares", f2(r.r2_tenure)], ["R² explained by the neighbours' mean", f2(r.r2_neighbours)]]}]})
    return {"id": "q07", "title": "Does the 2026 increase follow tenure boundaries or a regional pattern?", "group": "Is it spatially structured?",
            "question": "If tenure drove the increase, blocks of forest, licence and other land should differ sharply. If a regional cause (the dry season) drove it, the increase should vary smoothly across space and cross tenure boundaries.",
            "prediction": {"supports": "In at least two thirds of the KHG the tenure shares of a block explain more of its 2026 increase than the mean of its eight nearest blocks.",
                           "rejects": "In at least two thirds of the KHG the neighbours' mean explains more than tenure, by more than 0.05 of R²: the pattern is regional."},
            "method": ["Blocks of 2 km with at least 10 peat cells. Increase per block = (2026 detections minus the 2015-2025 mean) per 100 km² of peat.", "Moran's I with the 8 nearest blocks; p from 499 permutations (seed fixed).",
                       "R² of a regression of the block increase on the forest and licence shares of the block (tenure), and on the mean increase of its 8 nearest blocks (neighbours). A neighbour effect also captures any cause that is smooth in space, including tenure blocks that are large."],
            "data": ["Cell panels"], "result": {"khg_tested": n_ok, "tenure_better": ten_better, "space_better": sp_better}, "verdict": {"label": label, "reason": f"Tenure explained more in {ten_better} of {n_ok} KHG; the neighbours explained more by over 0.05 in {sp_better}."},
            "viz": [{"type": "table", "title": "By KHG", "cols": ["KHG", "blocks", "Moran's I", "p", "R² tenure", "R² neighbours"], "rows": [[r.khg.replace("KHG ", ""), int(r.blocks), f2(r.moran_i), f2(r.moran_p), f2(r.r2_tenure), f2(r.r2_neighbours)] for r in t.itertuples()]}],
            "samples": samples, "tables": {"q07_spatial_structure": t}}


def q_burnhist(panels, names, meta, boot, seed, **_):
    rng = np.random.default_rng(seed)
    res, tabs = {}, []
    for ten in TENURE_LABEL:
        rows = []
        for kid, p in panels.items():
            m = p.tenure == ten
            if m.sum() == 0:
                continue
            n26 = p["n_2026"].to_numpy()[m.to_numpy()]
            burned = p[[f"ba_{y}" for y in HP.BA_YEARS]].any(axis=1).to_numpy()[m.to_numpy()]
            d = pd.DataFrame({"bx": p.bx[m], "by": p.by[m], "n": n26, "nb": n26 * burned, "cells": 1, "cb": burned.astype(int)}).groupby(["bx", "by"], as_index=False).sum()
            d["khg"] = kid
            rows.append(d)
        d = pd.concat(rows, ignore_index=True)
        if d.n.sum() < 30:
            continue

        def enr(w):
            n, nb, c, cb = (np.sum(w * d[k].to_numpy()) for k in ("n", "nb", "cells", "cb"))
            return (nb / n) / (cb / c) if n and cb else np.nan

        est = enr(np.ones(len(d)))
        bs = np.array([enr(rng.multinomial(len(d), np.full(len(d), 1.0 / len(d))).astype(float)) for _ in range(boot)])
        lo, hi = np.nanpercentile(bs, [2.5, 97.5])
        res[ten] = {"ratio": float(est), "lo": float(lo), "hi": float(hi), "n_clusters": int(len(d)), "n_strata": 0, "a": int(d.nb.sum()), "b": int(d.n.sum()),
                    "share_hotspots_burned": float(d.nb.sum() / d.n.sum()), "share_cells_burned": float(d.cb.sum() / d.cells.sum())}
        tabs.append({"tenure": ten, **res[ten]})
    f = res.get("forest")
    label = "inconclusive"
    if f:
        label = "supports" if f["lo"] >= 1.5 else "rejects" if f["hi"] < 1.2 else "inconclusive"
    ci_rows = [ci_row(TENURE_LABEL[t], res[t], "pooled", f"{res[t]['share_hotspots_burned'] * 100:.0f}% of 2026 detections on land that burned before; {res[t]['share_cells_burned'] * 100:.0f}% of the land") for t in res]
    samples = []
    for k in sample_pick({k: float(p["n_2026"].sum()) for k, p in panels.items()}, 2):
        p = panels[k]
        burned = p[[f"ba_{y}" for y in HP.BA_YEARS]].any(axis=1)
        grp = []
        for ten in TENURE_LABEL:
            m = (p.tenure == ten)
            if m.sum() * (meta[k]["cell_m"] / 1000) ** 2 >= 5 and p.loc[m, "n_2026"].sum() > 0:
                grp.append({"label": TENURE_LABEL[ten], "note": f"{int(p.loc[m, 'n_2026'].sum())} detections", "series": [{"name": "share of the land burned 2015-2025", "value": 100 * float(burned[m].mean())}, {"name": "share of 2026 detections on that land", "value": 100 * float(p.loc[m & burned, "n_2026"].sum() / p.loc[m, "n_2026"].sum())}]})
        samples.append({"khg_id": k, "name": names[k], "why": f"one of the two KHG with the most detections in 2026 ({names[k]})", "viz": [{"type": "groups", "title": "Land that had burned before: its share of the land and of the 2026 detections", "unit": "%", "groups": grp}]})
    return {"id": "q08", "title": "Did 2026 fire return to land that had burned before?", "group": "Is it spatially structured?",
            "question": "Fire may recur on peat already damaged and drained by earlier burns, or it may reach ground that had not burned. Were the 2026 detections concentrated on land with a burn scar from 2015 to 2025?",
            "prediction": {"supports": "In forest area the share of 2026 detections on previously burned land is at least 1.5 times that land's share of the area (interval lower end at or above 1.5).", "rejects": "The upper end of the interval is below 1.2: 2026 fire is spread over burned and unburned land alike."},
            "method": ["A cell is previously burned if it lies inside a burnt-area polygon of any year 2015 to 2025 (burnt_area_2015_2026_Indonesia.gpkg).", "Enrichment = (share of 2026 detections on burned cells) / (share of cells that are burned), per tenure class, pooled over all KHG in the panel.", "The interval resamples 2 km blocks (seed fixed). Medium and high confidence together."],
            "data": ["Cell panels (burnt-area polygons, VIIRS)"], "result": res, "verdict": {"label": label, "reason": (ci_text(f) + f"; {f['share_hotspots_burned'] * 100:.0f}% of detections on {f['share_cells_burned'] * 100:.0f}% of the land." + others_text(res)) if f else "No forest area in the panel."},
            "viz": [{"type": "ci", "title": "Enrichment of 2026 detections on previously burned land (1 = in proportion to its area)", "ref": 1, "effect": 1.5, "rows": ci_rows}], "samples": samples, "tables": {"q08_burn_history": pd.DataFrame(tabs)}}


def q_climate(cfg, panels, names, meta, **_):
    rows = []
    for kid, p in panels.items():
        base = K.folder(kid.replace("KHG.", "", 1)) / "03_neraca" / "inputs" / "khg_level"
        fr = base / "balance_chirps_dekad.csv"
        if not fr.exists():
            continue

        def yearly(f):
            d = pd.read_csv(f, parse_dates=["start"])
            d = d[(d.start.dt.month * 100 + d.start.dt.day) <= 1021]
            return d.groupby(d.start.dt.year)["mm"].sum()

        rain = yearly(fr)
        yrs = [y for y in range(2018, 2026) if y in rain.index]
        if 2026 not in rain.index or len(yrs) < 6:
            continue
        z = lambda s: float((s[2026] - s[yrs].mean()) / s[yrs].std(ddof=1))
        rec = {"khg_id": kid, "khg": names[kid], "rain_2026_mm": float(rain[2026]), "rain_base_mm": float(rain[yrs].mean()), "rain_z": z(rain)}
        for ten in ["all"] + list(TENURE_LABEL):
            m = np.ones(len(p), bool) if ten == "all" else (p.tenure == ten).to_numpy()
            if m.sum() * (meta[kid]["cell_m"] / 1000) ** 2 < 20:
                rec[f"ratio_{ten}"] = np.nan
                continue
            n = [p.loc[m, f"n_{y}"].sum() for y in yrs]
            rec[f"ratio_{ten}"] = float((p.loc[m, "n_2026"].sum() + 0.5) / (np.mean(n) + 0.5))
        rows.append(rec)
    t = pd.DataFrame(rows)
    sp = {ten: spearman(t["rain_z"], np.log(t[f"ratio_{ten}"])) for ten in ["all"] + list(TENURE_LABEL)}
    a = sp["all"]
    below = int((t["rain_z"] < 0).sum())
    label = "inconclusive"
    if a["rho"] is not None:
        label = "supports" if a["rho"] <= -0.5 and a["p"] < 0.05 else "rejects" if a["lo"] > -0.5 else "inconclusive"
    pts = [{"label": r.khg.replace("KHG ", ""), "x": float(r.rain_z), "y": float(r.ratio_all), "group": "all"} for r in t.itertuples() if np.isfinite(r.ratio_all)]
    samples = []
    ext = t.dropna(subset=["ratio_all"]).copy()
    for k in list(ext.sort_values("rain_z").khg_id.iloc[:1]) + list(ext.sort_values("rain_z").khg_id.iloc[-1:]):
        r = ext[ext.khg_id == k].iloc[0]
        samples.append({"khg_id": k, "name": names[k], "why": "the driest KHG of the panel in 2026" if k == ext.sort_values("rain_z").khg_id.iloc[0] else "the wettest KHG of the panel in 2026",
                        "viz": [{"type": "table", "title": "Rain and fire, 1 January to the last day of data", "cols": ["", "value"], "rows": [["Rain 2026 (mm)", f"{r.rain_2026_mm:.0f}"], ["Mean rain 2018-2025 (mm)", f"{r.rain_base_mm:.0f}"], ["Rain anomaly (z)", f2(r.rain_z)], ["Hotspot ratio 2026 / 2018-2025 mean, all peat", f2(r.ratio_all)]]}]})
    return {"id": "q09", "title": "Does the 2026 fire anomaly follow the rain deficit?", "group": "Is it climate?",
            "question": "A drier 2026 would raise fire in every tenure class. Across KHG, did a larger rain deficit go with a larger hotspot increase?",
            "prediction": {"supports": "The 2026 rain anomaly and the hotspot ratio are negatively rank-correlated across KHG (Spearman rho at most -0.5, p below 0.05). With about a dozen KHG the interval of rho is wide, so the rule rejects only when the whole interval is above -0.5.", "rejects": "The lower end of the 95% interval of rho is above -0.5: a strong negative correlation is excluded."},
            "method": ["Rain: CHIRPS per KHG by dekad (repeat_common.fetch_gee_balance); dekads from 1 January to the dekad starting on 21 October, every year. Anomaly = z-score of 2026 against 2018 to 2025.",
                       "Evapotranspiration is not compared: the 2026 values (MOD16 near-real-time) give anomalies of about -20 to -35 standard deviations in every KHG, which is not plausible weather and has not been explained (see repeat-neraca/docs/reports/mod16_gf_vs_nrt.md for the two MOD16 products). Left out until checked.",
                       "Hotspot ratio: 2026 detections on peat divided by the 2018-2025 mean, same calendar window; per tenure class as well.", "Spearman rank correlation across the KHG of the panel. With about a dozen KHG a coefficient needs to be large to be told from chance: an inconclusive verdict means too little data to decide, not no effect.",
                       "Rain and evapotranspiration are KHG means; they do not differ between tenure classes of one KHG, so this tests the regional explanation, not the tenure contrast."],
            "data": ["balance_chirps_dekad.csv of each KHG folder (03_neraca/inputs/khg_level)", "Cell panels (hotspots)"],
            "result": {"rain_vs_all": a, "khg_below_mean": below, "by_tenure": sp}, "verdict": {"label": label, "reason": f"Spearman rho {f2(a['rho'])} (95% interval {f2(a['lo'])} to {f2(a['hi'])}), p {f2(a['p'])} over {a['n']} KHG. Rain in 2026 was below the 2018-2025 mean in {below} of {len(t)} KHG (z from {t['rain_z'].min():.1f} to {t['rain_z'].max():.1f})."},
            "viz": [{"type": "scatter", "title": "Hotspot ratio against the 2026 rain anomaly (one dot per KHG)", "xlabel": "rain anomaly, z (negative: drier than 2018-2025)", "ylabel": "hotspot ratio 2026 / mean 2018-2025", "log": False, "logy": True, "points": pts, "ref": 1},
                    {"type": "table", "title": "Spearman rho of the rain anomaly against the hotspot ratio, by tenure class", "cols": ["class", "rho", "p", "KHG"], "rows": [[("All peat" if k == "all" else TENURE_LABEL[k]), f2(v["rho"]), f2(v["p"]), v["n"]] for k, v in sp.items()]}],
            "samples": samples, "tables": {"q09_climate": t}}


def q_trend(cfg, names, **_):
    area, hot, _f = tenure_tables(cfg, "nh")
    n = hot.groupby(["khg_id", "tenure", "year"])["n"].sum().unstack("year").fillna(0)
    pk = area.groupby(["khg_id", "tenure"])["peat_km2"].sum()
    rows = []
    for (k, ten), r in n.iterrows():
        peat = pk.get((k, ten), 0)
        if peat < 20 or r[BASE_Y].sum() < 20:
            continue
        s = {y: 100 * r.get(y, 0) / peat for y in range(2012, 2027)}
        prev = [s[y] for y in range(2012, 2026)]
        mk = mann_kendall([s[y] for y in range(2012, 2026)])
        rows.append({"khg_id": k, "khg": names.get(k, k), "tenure": ten, "peat_km2": float(peat), "rate_2026": s[2026], "max_2012_2025": max(prev), "record_high": bool(s[2026] > max(prev)),
                     "rank_2026_of_15": int(1 + sum(v > s[2026] for v in prev)), "mk_trend_2012_2025_z": mk["z"], "mk_p": mk["p"], "series": s})
    t = pd.DataFrame(rows)
    fr = t[t.tenure == "forest"]
    ot = t[t.tenure != "forest"]
    sh_f, sh_o = float(fr.record_high.mean()), float(ot.record_high.mean())
    table = [[int(fr.record_high.sum()), int((~fr.record_high).sum())], [int(ot.record_high.sum()), int((~ot.record_high).sum())]]
    p = float(stats.fisher_exact(table).pvalue)
    label = "supports" if sh_f - sh_o >= 0.20 and p < 0.05 else "rejects" if sh_f - sh_o < 0.10 else "inconclusive"
    per = []
    for ten in TENURE_LABEL:
        g = t[t.tenure == ten]
        per.append([TENURE_LABEL[ten], len(g), int(g.record_high.sum()), f"{100 * g.record_high.mean():.0f}%" if len(g) else "n/a", f"{int((g.mk_trend_2012_2025_z > 1.96).sum())} up / {int((g.mk_trend_2012_2025_z < -1.96).sum())} down"])
    samples = []
    forest_hi = fr.sort_values("rate_2026", ascending=False)
    for k in list(forest_hi.khg_id.iloc[:1]) + list(fr[~fr.record_high].sort_values("rate_2026", ascending=False).khg_id.iloc[:1]):
        series = []
        for ten in TENURE_LABEL:
            g = t[(t.khg_id == k) & (t.tenure == ten)]
            if len(g):
                series.append({"name": TENURE_LABEL[ten], "tenure": ten, "points": [[y, g.iloc[0].series[y]] for y in range(2012, 2027)]})
        rec = bool(fr[fr.khg_id == k].record_high.iloc[0])
        samples.append({"khg_id": k, "name": names[k], "why": ("the forest area with the highest 2026 rate" if rec else "the forest area with the highest 2026 rate that is not a record high") + f" ({names[k]})",
                        "viz": [{"type": "lines", "title": "Hotspots per 100 km² of peat, 1 January to the last day of data, by year", "xlabel": "year", "ylabel": "per 100 km²", "series": series}]})
    return {"id": "q10", "title": "Was 2026 a record in forest area more often than elsewhere?", "group": "Is it climate?",
            "question": "If forest area was specially hit, 2026 should be the highest year since 2012 in forest area in more KHG than in licence land or other land. Otherwise 2026 looks like a bad year everywhere.",
            "prediction": {"supports": "The share of KHG in which 2026 is a record high is at least 20 percentage points higher for forest area than for the other classes (Fisher exact p below 0.05).", "rejects": "The difference is below 10 percentage points."},
            "method": ["Unit: a tenure class in a KHG with at least 20 km² of peat and 20 detections in 2015 to 2025. Rate = detections on peat per 100 km² over 1 January to the last day of 2026 data, each year 2012 to 2026.", "Record high: the 2026 rate exceeds every rate from 2012 to 2025.",
                       "Mann-Kendall trend of 2012 to 2025 (tie-corrected) for each unit, to show whether 2026 sits on a trend.", "Forest units against the other units, Fisher exact test."],
            "data": ["tenure_hotspots.csv and tenure_area.csv of repeat-national-tenure (34 KHG)"],
            "result": {"forest_record_share": sh_f, "other_record_share": sh_o, "fisher_p": p, "units_forest": len(fr), "units_other": len(ot)},
            "verdict": {"label": label, "reason": f"2026 is a record in {100 * sh_f:.0f}% of {len(fr)} forest units and {100 * sh_o:.0f}% of {len(ot)} other units (Fisher p {f2(p)})."},
            "viz": [{"type": "table", "title": "Units where 2026 is the highest year since 2012", "cols": ["class", "units", "record 2026", "share", "trend 2012-2025 (|z| > 1.96)"], "rows": per}], "samples": samples,
            "tables": {"q10_trend_units": t.drop(columns="series")}}


def q_timing(panels, hots, names, **_):
    rows, curves = [], {}
    for kid, h in hots.items():
        h = h.assign(doy=pd.to_datetime(h["date"]).dt.dayofyear, grp=np.where(h["tenure"] == "forest", "forest", "other"))
        res = {}
        for grp, g in h.groupby("grp"):
            t50 = {}
            for y, gy in g.groupby("year"):
                if len(gy) >= 30:
                    s = np.sort(gy["doy"].to_numpy())
                    t50[int(y)] = float(s[int(np.ceil(0.5 * len(s))) - 1])
            base = [t50[y] for y in BASE_Y if y in t50]
            if 2026 in t50 and len(base) >= 5:
                res[grp] = {"t50_2026": t50[2026], "t50_base_median": float(np.median(base)), "shift": t50[2026] - float(np.median(base)), "n26": int((g.year == 2026).sum())}
        if len(res) == 2:
            rows.append({"khg_id": kid, "khg": names[kid], "forest_shift_days": res["forest"]["shift"], "other_shift_days": res["other"]["shift"], "diff_days": res["forest"]["shift"] - res["other"]["shift"],
                         "forest_t50_2026": res["forest"]["t50_2026"], "forest_t50_base": res["forest"]["t50_base_median"], "other_t50_2026": res["other"]["t50_2026"], "other_t50_base": res["other"]["t50_base_median"]})
            cur = {}
            for grp, g in h.groupby("grp"):
                x = np.arange(1, 305, 7)
                c26 = np.array([(g[(g.year == 2026)].doy <= v).sum() for v in x], float)
                cb = np.median(np.array([[(g[(g.year == y)].doy <= v).sum() / max(1, (g.year == y).sum()) for v in x] for y in BASE_Y]), axis=0)
                cur[grp] = {"x": x, "c26": c26 / max(1, c26[-1]), "cb": cb}
            curves[kid] = cur
    t = pd.DataFrame(rows)
    label, reason = "not testable", f"Only {len(t)} KHG have 30 or more detections in the forest group and in the other group in 2026 and in at least 5 baseline years; 6 are needed."
    if len(t) >= 6:
        w = stats.wilcoxon(t["diff_days"])
        med = float(t["diff_days"].median())
        label = "supports" if med <= -7 and w.pvalue < 0.05 else "rejects" if med > -3 else "inconclusive"
        reason = f"Median of (forest shift minus other shift) {med:.0f} days over {len(t)} KHG (Wilcoxon signed-rank p {f2(w.pvalue)}); a negative value means forest burned earlier relative to its own baseline."
    samples = []
    for k in sample_pick({r.khg_id: abs(r.diff_days) for r in t.itertuples()}, 2):
        r = t[t.khg_id == k].iloc[0]
        series = []
        for grp, lab in (("forest", "Forest area"), ("other", "Licence and other land")):
            series += [{"name": f"{lab}, 2026", "points": [[int(x), float(v)] for x, v in zip(curves[k][grp]["x"], curves[k][grp]["c26"])]}, {"name": f"{lab}, median 2015-2025", "dash": True, "points": [[int(x), float(v)] for x, v in zip(curves[k][grp]["x"], curves[k][grp]["cb"])]}]
        samples.append({"khg_id": k, "name": names[k], "why": f"one of the two KHG with the largest difference in timing ({names[k]})", "viz": [{"type": "lines", "title": "Share of the season's detections reached by day of year (1 January to the last day of data)", "xlabel": "day of year", "ylabel": "cumulative share", "series": series},
                        {"type": "table", "title": "Day of year when half of the detections had occurred", "cols": ["", "2026", "median 2015-2025", "shift (days)"], "rows": [["Forest area", f"{r.forest_t50_2026:.0f}", f"{r.forest_t50_base:.0f}", f"{r.forest_shift_days:+.0f}"], ["Licence and other land", f"{r.other_t50_2026:.0f}", f"{r.other_t50_base:.0f}", f"{r.other_shift_days:+.0f}"]]}]})
    return {"id": "q11", "title": "Did the forest-area season start earlier or run later than elsewhere?", "group": "Is it climate?",
            "question": "Water held back at the dome delays the start of the fire season; a deficit shifts it earlier. Was 2026's fire season in forest area shifted in time relative to licence and other land, each against its own baseline?",
            "prediction": {"supports": "Forest-area fire reached half of its total at least 7 days earlier (relative to its own median of 2015 to 2025) than the other classes, in the median KHG (Wilcoxon p below 0.05).", "rejects": "The median difference is above -3 days: no earlier shift in forest area."},
            "method": ["Day of year on which half of the season's detections (1 January to the last day of data) had occurred, for forest area and for all other land, each year with at least 30 detections.", "Shift = 2026 minus the median of 2015 to 2025 (at least 5 baseline years). The test is on the difference of the two shifts, over KHG with both groups.",
                       "Day of year is the calendar day of the satellite pass (UTC date)."],
            "data": ["Hotspot list of the cell panels (dates, tenure class)"], "result": {"khg": len(t), "median_diff_days": float(t["diff_days"].median()) if len(t) else None}, "verdict": {"label": label, "reason": reason},
            "viz": [{"type": "table", "title": "Shift of the half-season date, 2026 against its own 2015-2025 median", "cols": ["KHG", "forest (days)", "other (days)", "difference"], "rows": [[r.khg.replace("KHG ", ""), f"{r.forest_shift_days:+.0f}", f"{r.other_shift_days:+.0f}", f"{r.diff_days:+.0f}"] for r in t.itertuples()]}],
            "samples": samples, "tables": {"q11_timing": t}}


# ---------------------------------------------------------------------------------------------------------------- run

def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*", help="khg_id of the cell panels (default: every KHG with a licence-edge run)")
    ap.add_argument("--boot", type=int, default=1000)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--force", action="store_true", help="rebuild the cell panels")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    out = Path(cfg["out"]) / "hypotheses"
    out.mkdir(parents=True, exist_ok=True)
    khg = P.load_khg(cfg)
    names = dict(zip(khg.khg_id, khg.nama))
    ids = a.khg or [k for k in khg.khg_id if has_edge_run(k)]
    panels, hots, metas = load_panels(cfg, ids, out, a.force)
    common = dict(cfg=cfg, panels=panels, hots=hots, names=names, meta=metas, boot=a.boot, seed=a.seed)
    qs = [f(**common) for f in (q_scar, q_tenure, q_dmpg, q_licence_gradient, q_canal, q_dome, q_spatial, q_burnhist, q_climate, q_trend, q_timing)]
    files = []
    for q in qs:
        for name, df in q.pop("tables").items():
            df.to_csv(out / f"{name}.csv", index=False)
            files.append(f"{name}.csv")
            q.setdefault("csv", []).append(f"{name}.csv")
        log.info("%s %s: %s", q["id"], q["title"], q["verdict"]["label"])
    tdir = Path(cfg["out"]) / "tenure"
    prov = {"generated": datetime.datetime.now(datetime.timezone.utc).isoformat(timespec="seconds"), "command": f"repeat-hypotheses --config {a.config} --boot {a.boot} --seed {a.seed}",
            "seed": a.seed, "bootstrap_draws": a.boot, "effect_threshold": EFFECT, "baseline_years": [BASE_Y[0], BASE_Y[-1]], "test_year": 2026,
            "window_last_day": json.loads((tdir / "tenure_meta.json").read_text())["last_2026"] if (tdir / "tenure_meta.json").exists() else None,
            "thresholds": {"near_licence_m": NEAR_LIC_M, "far_licence_m": FAR_LIC_M, "near_canal_m": NEAR_CANAL_M, "far_canal_m": FAR_CANAL_M, "road_m": ROAD_M},
            "khg_cell_panels": {k: {kk: v for kk, v in m.items()} for k, m in metas.items()}, "khg_tenure_tables": int(pd.read_csv(tdir / "tenure_area.csv").khg_id.nunique()),
            "software": {"python": platform.python_version(), "numpy": np.__version__, "pandas": pd.__version__, "scipy": scipy.__version__}, "csv": files}
    (out / "provenance.json").write_text(json.dumps(prov, indent=1, default=str), encoding="utf-8")
    (out / "hypotheses.json").write_text(json.dumps(clean({"provenance": prov, "questions": qs}), allow_nan=False), encoding="utf-8")
    log.info("%d questions -> %s", len(qs), out)


if __name__ == "__main__":
    main()
