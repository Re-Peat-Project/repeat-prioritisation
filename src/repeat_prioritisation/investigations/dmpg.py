#!/usr/bin/env python3
"""Do Desa Peduli Gambut (DPG, later DMPG) villages burn less? Fire record of the DPG villages against comparable villages.

  python -m repeat_prioritisation.investigations.dmpg --config configs/investigations/dmpg.yaml [--reuse]

Units: the 2,004 Bluebook 2026 target villages (desa_target_pemulihan_ekosistem_gambut.gpkg) plus the DPG villages that are
not among them. Treated: the villages of the BRG Atlas Desa Peduli Gambut with a boundary (repeat_common.fetch_dpg_atlas,
fetch_dpg_boundaries; KLH 2023 polygons, BIG 2026 as fallback), mapped June 2018 to July 2019. Controls: the other target villages, compared inside the same KHG. A second comparison takes, in every
KHG that holds DPG villages, the DPG part of the KHG against the rest of the KHG, so it does not depend on how the Bluebook
picked its targets in 2026.
Fire per unit and year with the national profile readers: FIRMS VIIRS hotspots 2012-2025 (main outcome, per km2 of peat),
burned area 2015-2025 (share of peat burned), KLH MODIS hotspots 2026 (descriptive). Peat: GFW composite extent.
Estimates: Mantel-Haenszel rate ratios of fire per km2 of peat, DPG against the others, stratified by KHG, per year and per
period (`periods`), with bootstrap 95% intervals (villages resampled within KHG; whole KHG in the second comparison). The
change after the mapping is the post-period ratio over a baseline ratio (`contrasts`); two baselines are kept because 2015,
the extreme fire year, may be the year the villages were picked for. The "no fire" shares are given per year under several
definitions because the answer depends on the definition.
Outputs in `out`: dmpg.html (the evidence page, template and script in investigations/assets), units.csv, unit_year.csv,
results.json, figures/*.png and report.md; each measurement step is cached in
`out`/cache, so an interrupted run resumes (delete the cache when the data change). --reuse skips the fire measurements and
reads unit_year.csv.
"""
from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path

import geopandas as gpd
import matplotlib
import matplotlib.ticker
import numpy as np
import pandas as pd
import pyogrio
import shapely
import yaml

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
ASSETS = Path(__file__).resolve().parent / "assets"
from repeat_prioritisation.national import overlay as O  # noqa: E402
from repeat_prioritisation.national import profile as P  # noqa: E402

log = logging.getLogger("investigations.dmpg")
VIIRS_YEARS = list(range(2012, 2026))
BURN_YEARS = list(range(2015, 2026))
EXTRA_ID = 900_000     # OBJECTID offset of DPG villages that are not Bluebook target villages
C_DPG, C_CTL, C_NOW = "#eb6834", "#2a78d6", "#52514e"


# ---------------------------------------------------------------- units

def villages(cfg):
    data, inp = Path(cfg["data"]), cfg["inputs"]
    v = pyogrio.read_dataframe(data / inp["villages"], columns=["OBJECTID", "PROV_2023", "KABKO_2023", "KEC_2023", "DESA_2023"])
    v["geometry"] = shapely.make_valid(v.geometry.values)
    dpg = pyogrio.read_dataframe(data / inp["dpg"])
    dpg = dpg[dpg.geometry.notna()].assign(geometry=lambda d: shapely.make_valid(d.geometry.values))
    ids = dpg.dropna(subset=["target_objectid"]).assign(target_objectid=lambda d: d.target_objectid.astype(int))
    v = v.merge(ids[["target_objectid", "mapped"]].rename(columns={"target_objectid": "OBJECTID"}), on="OBJECTID", how="left")
    # DPG villages outside the Bluebook target villages: own units, OBJECTID = EXTRA_ID + feature id in the boundary source
    extra = dpg[dpg["target_objectid"].isna()]
    v = pd.concat([v, gpd.GeoDataFrame({"OBJECTID": EXTRA_ID + extra["boundary_id"].astype(int).to_numpy(), "PROV_2023": extra["province"].to_numpy(),
                                        "KABKO_2023": extra["kabupaten"].to_numpy(), "KEC_2023": extra["kecamatan"].to_numpy(),
                                        "DESA_2023": extra["desa"].to_numpy(), "mapped": extra["mapped"].to_numpy()},
                                       geometry=extra.geometry.to_numpy(), crs=extra.crs)], ignore_index=True)
    v["dpg"] = v["mapped"].notna()
    khg = P.load_khg({"data": cfg["data"], "inputs": {"khg": inp["khg"]}, "registry": cfg["registry"]})
    rp = gpd.GeoDataFrame(geometry=v.geometry.representative_point(), crs=v.crs)
    j = gpd.sjoin(rp, khg[["khg_id", "nama", "geometry"]], how="left", predicate="within")
    j = j[~j.index.duplicated()]
    v["khg"], v["khg_name"] = j["khg_id"].to_numpy(), j["nama"].to_numpy()
    v["khg_id"] = "v" + v["OBJECTID"].astype(str)          # the profile readers key every unit on khg_id
    proj = v.to_crs(P.AEA)
    v["area_km2"], v["geom_aea"] = proj.geometry.area.to_numpy() / 1e6, shapely.make_valid(proj.geometry.values, method="structure", keep_collapsed=False)
    return v, khg


def khg_halves(v, khg):
    """In each KHG holding DPG villages: the DPG part and the rest of the KHG, as two units."""
    rows = []
    for kid, grp in v[v["dpg"] & v["khg"].notna()].groupby("khg"):
        k = khg[khg.khg_id == kid].iloc[0]
        d = shapely.intersection(shapely.union_all(grp.geometry.values), k.geometry)
        for part, geom in (("dpg", d), ("rest", shapely.difference(k.geometry, d))):
            rows.append({"khg_id": f"{kid}|{part}", "khg": kid, "khg_name": k.nama, "dpg": part == "dpg", "geometry": geom})
    h = gpd.GeoDataFrame(rows, crs=4326)
    proj = h.to_crs(P.AEA)
    h["area_km2"], h["geom_aea"] = proj.geometry.area.to_numpy() / 1e6, shapely.make_valid(proj.geometry.values, method="structure", keep_collapsed=False)
    return h


def licence_shares(cfg, units):
    """Share of each unit's area inside a licence and in the ring_km ring around licences (outside every licence), from a
    250 m grid of points per unit and national.overlay.near_licences."""
    lic = pyogrio.read_dataframe(Path(cfg["data"]) / cfg["inputs"]["licences"], columns=[])
    lic_m = shapely.make_valid(O.to_aea(shapely.make_valid(lic.geometry.values)), method="structure", keep_collapsed=False)
    tree, ring_m, out = shapely.STRtree(lic_m), 1000.0 * cfg["ring_km"], []
    for g, ga in zip(units.geometry.values, units["geom_aea"].values):
        lon, lat, _, _ = O.grid(g, cell=250.0)
        if not len(lon):
            out.append((np.nan, np.nan))
            continue
        cand = tree.query(shapely.buffer(shapely.envelope(ga), ring_m))
        inside, pi, _ = O.near_licences(lon, lat, lic_m[cand], ring_m)
        near = np.isin(np.arange(len(lon)), pi)
        out.append((inside.mean(), (near & ~inside).mean()))
    return pd.DataFrame(out, columns=["share_licence", "share_ring"], index=units.index)


# ---------------------------------------------------------------- fire per unit and year

def cached(path, fn):
    """Read path if an earlier run wrote it, else compute and write it, so an interrupted run resumes."""
    if path.exists():
        log.info("cached %s", path.name)
        return pd.read_csv(path)
    d = fn()
    d.to_csv(path, index=False)
    return d


def measure(cfg, units, sampler, cache):
    data, inp = Path(cfg["data"]), cfg["inputs"]
    peat = cached(cache / "peat.csv", lambda: P.peat_table(sampler, units))
    units = units.merge(peat, on="khg_id", how="left")
    units["peat_km2"] = units["area_km2"] * units["peat_frac"]
    log.info("burned area for %d units", len(units))
    yb = cached(cache / "burned.csv", lambda: P.burned_by_year(data / inp["burned"], units, (2015, 2025), sampler)[0])
    log.info("VIIRS hotspots")
    hs = cached(cache / "viirs.csv", lambda: P.hotspots_by_year(data / inp["hotspots"], units, cfg["hotspots"], sampler))
    log.info("KLH hotspots 2026")
    now = cached(cache / "klh2026.csv", lambda: P.hotspots_now(data / inp["hotspots_now"], units, cfg["now"], sampler)[0])
    grid = pd.MultiIndex.from_product([units["khg_id"], range(2012, 2027)], names=["khg_id", "year"]).to_frame(index=False)
    uy = grid.merge(yb, on=["khg_id", "year"], how="left").merge(hs[["khg_id", "year", "n_hotspot", "n_hotspot_peat"]], on=["khg_id", "year"], how="left")
    n26 = now.groupby("khg_id")[["n_kept", "n_kept_peat"]].sum().reset_index().assign(year=2026)
    uy = uy.merge(n26, on=["khg_id", "year"], how="left")
    for c in ("burned_km2", "burned_peat_km2", "n_hotspot", "n_hotspot_peat", "n_kept", "n_kept_peat"):
        uy[c] = uy[c].fillna(0)
    return units, uy


# ---------------------------------------------------------------- estimation

def rate_arrays(units, uy, count, years, min_peat):
    """Fire amount per unit and year (C), peat km2 (T), DPG flag (D) and KHG stratum (S), for units in a KHG with enough
    peat, in KHG that hold both DPG and other units."""
    u = units[units["khg"].notna() & (units["peat_km2"] >= min_peat)]
    g = u.groupby("khg")["dpg"].agg(["any", "all"])
    u = u[u["khg"].isin(g.index[g["any"] & ~g["all"]])].reset_index(drop=True)
    C = uy[uy["year"].isin(years)].pivot(index="khg_id", columns="year", values=count).reindex(index=u["khg_id"], columns=years).fillna(0)
    return C.to_numpy(float), u["peat_km2"].to_numpy(float), u["dpg"].to_numpy(bool), pd.factorize(u["khg"])[0]


def mh(C, T, D, S, w=None):
    """Mantel-Haenszel rate ratio, DPG against other units, stratified by S, for each column of C; w = unit weights."""
    w = np.ones(len(T)) if w is None else w
    ns = S.max() + 1

    def tot(m, sel):
        out = np.zeros((ns,) + m.shape[1:])
        np.add.at(out, S[sel], m[sel])
        return out
    a, b = tot(C * w[:, None], D), tot(C * w[:, None], ~D)
    t1, t0 = tot(T * w, D)[:, None], tot(T * w, ~D)[:, None]
    ok, tt = (t1 > 0) & (t0 > 0), np.maximum(t1 + t0, 1e-12)
    num, den = np.where(ok, a * t0 / tt, 0).sum(0), np.where(ok, b * t1 / tt, 0).sum(0)
    return np.where(den > 0, num / np.where(den > 0, den, 1), np.nan)


def boot_weights(S, D, reps, seed, by="unit"):
    """Bootstrap unit weights: units resampled within each KHG and group (by='unit'), or whole KHG resampled (by='stratum')."""
    rng = np.random.default_rng(seed)
    if by == "stratum":
        members = [np.flatnonzero(S == s) for s in range(S.max() + 1)]
    else:
        members = [m for m in (np.flatnonzero((S == s) & (D == d)) for s in range(S.max() + 1) for d in (True, False)) if len(m)]
    for _ in range(reps):
        w = np.zeros(len(S))
        if by == "stratum":
            for s in rng.integers(0, len(members), len(members)):
                w[members[s]] += 1
        else:
            for m in members:
                np.add.at(w, rng.choice(m, len(m)), 1)
        yield w


def rate_ratios(units, uy, count, years, cfg, by="unit"):
    """Rate ratio per year and per period, the post/pre contrasts, with bootstrap 95% intervals."""
    C, T, D, S = rate_arrays(units, uy, count, years, cfg["min_peat_km2"])
    periods = {k: [y for y in v if y in years] for k, v in cfg["periods"].items()}
    periods = {k: v for k, v in periods.items() if v}
    cols = [C] + [C[:, [years.index(y) for y in v]].sum(1, keepdims=True) for v in periods.values()]
    X = np.hstack(cols)
    names = [str(y) for y in years] + list(periods)
    est = mh(X, T, D, S)
    B = np.array([mh(X, T, D, S, w) for w in boot_weights(S, D, cfg["bootstrap"], cfg["seed"], by)])
    ci = lambda b: (float(np.nanpercentile(b, 2.5)), float(np.nanpercentile(b, 97.5)))
    out = {"n_dpg": int(D.sum()), "n_ctl": int((~D).sum()), "n_khg": int(S.max() + 1),
           "by_year": [{"year": y, "rr": float(est[j]), **dict(zip(("lo", "hi"), ci(B[:, j])))} for j, y in enumerate(years)],
           "periods": {k: {"years": v, "rr": float(est[len(years) + i]), **dict(zip(("lo", "hi"), ci(B[:, len(years) + i])))}
                       for i, (k, v) in enumerate(periods.items())},
           "contrasts": []}
    for a, b in cfg["contrasts"]:
        if a in periods and b in periods:
            ia, ib = names.index(a), names.index(b)
            out["contrasts"].append({"post": a, "pre": b, "ratio": float(est[ia] / est[ib]), **dict(zip(("lo", "hi"), ci(B[:, ia] / B[:, ib])))})
    return out


# ---------------------------------------------------------------- "no fire" shares

NO_FIRE = [("no_viirs_hotspot", "No VIIRS hotspot in the village"), ("no_viirs_hotspot_peat", "No VIIRS hotspot on its peat"),
           ("lt5_viirs_hotspots", "Fewer than 5 VIIRS hotspots"), ("no_burned_area", "No burned area"),
           ("burned_lt1pct", "Less than 1% of the village burned"), ("no_klh_hotspot", "No KLH hotspot (2026, Jan-Sep)")]


def no_fire(units, uy, which):
    """Share of units with no fire per year, under several definitions."""
    d = uy.merge(units[["khg_id", "dpg", "area_km2"]], on="khg_id")
    d = d[d["dpg"] == which]
    out = []
    for y, g in d.groupby("year"):
        row = {"year": int(y), "n": len(g)}
        if y in VIIRS_YEARS:
            row["no_viirs_hotspot"] = float((g["n_hotspot"] == 0).mean())
            row["no_viirs_hotspot_peat"] = float((g["n_hotspot_peat"] == 0).mean())
            row["lt5_viirs_hotspots"] = float((g["n_hotspot"] < 5).mean())
        if y in BURN_YEARS:
            row["no_burned_area"] = float((g["burned_km2"] == 0).mean())
            row["burned_lt1pct"] = float((g["burned_km2"] < 0.01 * g["area_km2"]).mean())
        if y == 2026:
            row["no_klh_hotspot"] = float((g["n_kept"] == 0).mean())
        out.append(row)
    return out


# ---------------------------------------------------------------- figures

def _style(ax, title, unit):
    ax.set_title(title, loc="left", fontsize=10)
    ax.set_ylabel(unit, fontsize=8)
    ax.spines[["top", "right"]].set_visible(False)
    ax.tick_params(labelsize=8)
    ax.grid(axis="y", color="#e4e3dc", lw=0.6)


def fig_rr(panels, path, mapped):
    fig, axes = plt.subplots(1, len(panels), figsize=(4.4 * len(panels), 3.2))
    for ax, (title, r) in zip(np.atleast_1d(axes), panels):
        rows = sorted(r["by_year"], key=lambda x: x["year"])
        x = [q["year"] for q in rows]
        ax.fill_between(x, [q["lo"] for q in rows], [q["hi"] for q in rows], color=C_DPG, alpha=0.15, lw=0)
        ax.plot(x, [q["rr"] for q in rows], color=C_DPG, lw=1.8, marker="o", ms=3)
        ax.axhline(1, color="#777", lw=0.8)
        ax.axvspan(mapped[0], mapped[1], color="#777", alpha=0.08, lw=0)
        ax.text(sum(mapped) / 2, 1.0, "BRG mapping", transform=ax.get_xaxis_transform(), ha="center", va="bottom", fontsize=7, color="#6f6e69")
        ax.set_yscale("log")
        ax.yaxis.set_major_locator(matplotlib.ticker.FixedLocator([0.25, 0.5, 1, 2, 4, 8]))
        ax.yaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:g}"))
        ax.yaxis.set_minor_formatter(matplotlib.ticker.NullFormatter())
        _style(ax, title, "DPG rate / other villages' rate")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_means(units, uy, path, min_peat):
    d = uy[uy["year"].isin(VIIRS_YEARS)].merge(units[["khg_id", "khg", "dpg", "peat_km2"]], on="khg_id")
    d = d[d["khg"].notna() & (d["peat_km2"] >= min_peat)]
    m = d.groupby(["year", "dpg"])[["n_hotspot_peat", "peat_km2"]].sum()
    m = (m["n_hotspot_peat"] / m["peat_km2"]).unstack()
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    ax.plot(m.index, m[True], color=C_DPG, lw=1.8, label="DPG villages")
    ax.plot(m.index, m[False], color=C_CTL, lw=1.8, label="other target villages")
    ax.legend(frameon=False, fontsize=8)
    _style(ax, "VIIRS hotspots on peat per km2 of peat", "per km2 per year")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


def fig_nofire(rows_dpg, rows_ctl, path):
    fig, ax = plt.subplots(figsize=(5.4, 3.2))
    for rows, c, lab in ((rows_dpg, C_DPG, "DPG villages"), (rows_ctl, C_CTL, "other target villages")):
        d = pd.DataFrame(rows).set_index("year")
        for col, ls, what in (("no_viirs_hotspot", "-", "no VIIRS hotspot"), ("no_burned_area", "--", "no burned area")):
            s = d[col].dropna()
            ax.plot(s.index, 100 * s, color=c, ls=ls, lw=1.6, label=f"{lab}: {what}")
        if pd.notna(d.loc[2026].get("no_klh_hotspot", np.nan)):
            ax.plot([2026], [100 * d.loc[2026, "no_klh_hotspot"]], "o", color=c, ms=4)
    ax.axhline(99, color=C_NOW, lw=0.8, ls=":")
    ax.text(2012, 96, "99%", color=C_NOW, fontsize=7, va="top")
    ax.set_ylim(0, 100)
    ax.legend(frameon=False, fontsize=7)
    _style(ax, "Villages without fire (dots: no KLH hotspot, 2026)", "% of villages")
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)


# ---------------------------------------------------------------- report

def pct(x):
    return f"{100 * x:.0f}%"


def rr_txt(q):
    return f"{q['rr']:.2f} ({q['lo']:.2f} to {q['hi']:.2f})"


def report(cfg, R, path):
    nf, nc = pd.DataFrame(R["no_fire_dpg"]).set_index("year"), pd.DataFrame(R["no_fire_ctl"]).set_index("year")
    yrs = [y for y in range(2015, 2027) if y in nf.index]
    v, h = R["rr"]["viirs"], R["rr"]["burned"]
    P_ = cfg["periods"]
    lab = {k: (f"{v[0]}-{v[-1]}" if v == list(range(v[0], v[-1] + 1)) and len(v) > 2 else ", ".join(map(str, v))) for k, v in P_.items()}
    L = ["# Do Desa Peduli Gambut villages burn less?", "",
         "Generated by `python -m repeat_prioritisation.investigations.dmpg --config configs/investigations/dmpg.yaml`. Data and limits: last sections. "
         "Interactive page with maps: [dmpg.html](dmpg.html).", "",
         "## Question", "",
         "The World Bank asked whether DMPG villages are safe from fire and whether DMPG should weigh in the prioritisation. "
         "KLH stated in a meeting that 99% of DMPG villages had no fire; no source file for that figure is in the workspace.", "",
         "## Villages", "",
         f"- DPG: {R['n_dpg']} of the {R['n_atlas']} villages of the BRG Atlas Desa Peduli Gambut (participatory mapping June 2018 to "
         f"July 2019), matched by name to village boundaries (KLH 2023, BIG 2026); {R['n_dpg_khg']} lie in a KHG.",
         f"- Comparison: the other {R['n_ctl']} target villages, always within the same KHG.",
         "- The atlas is part of the DPG programme and holds none of the DMPG villages added later; the official DMPG list is not in the workspace.", "",
         "## The 99% figure", "",
         "![no fire](figures/no_fire.png)", "",
         "Share of villages without fire, per year (DPG / other target villages):", "",
         "| Definition | " + " | ".join(map(str, yrs)) + " |", "|---|" + "---|" * len(yrs)]
    for col, name in NO_FIRE:
        cells = [f"{pct(nf.loc[y, col])} / {pct(nc.loc[y, col])}" if col in nf and pd.notna(nf.loc[y].get(col, np.nan)) else "" for y in yrs]
        L.append(f"| {name} | " + " | ".join(cells) + " |")
    m = R["max_no_fire_dpg"]
    L += ["", f"The highest share of DPG villages without fire under any definition in any year is {pct(m['share'])} "
          f"({m['definition']}, {m['year']}); other target villages that year: {pct(m['share_ctl'])}. "
          + ("No definition reaches 99%." if m["share"] < 0.99 else "That reaches 99%."),
          f"Over {cfg['post_from']}-2025, {pct(R['ever_viirs_dpg'])} of the DPG villages had at least one VIIRS hotspot and "
          f"{pct(R['ever_burn_dpg'])} had some burned area.", "",
          "## Fire in DPG villages against other target villages", "",
          "Rate ratio: hotspots (or burned area) per km2 of peat in DPG villages divided by the same in other target villages of the "
          "same KHG (Mantel-Haenszel, stratified by KHG). 1 means equal; 2 means twice the rate. 95% intervals from "
          f"{cfg['bootstrap']} bootstrap samples of villages within KHG. Shaded: the mapping period.", "",
          "![rate ratio](figures/rate_ratio.png)", "",
          "| Period | VIIRS hotspots | Burned area |", "|---|---|---|"]
    for k in P_:
        a, b = v["periods"].get(k), h["periods"].get(k)
        L.append(f"| {lab[k]} | {rr_txt(a) if a else ''} | {rr_txt(b) if b else ''} |")
    L += ["", f"Change of the ratio after mapping (post-period ratio divided by the baseline ratio; below 1 means DPG villages "
          "improved against the others):", "", "| Comparison | VIIRS hotspots | Burned area |", "|---|---|---|"]
    for c in v["contrasts"]:
        cb = next((x for x in h["contrasts"] if x["post"] == c["post"] and x["pre"] == c["pre"]), None)
        f = lambda q: f"{q['ratio']:.2f} ({q['lo']:.2f} to {q['hi']:.2f})"
        L.append(f"| {lab[c['post']]} against {lab[c['pre']]} | {f(c)} | {f(cb) if cb else ''} |")
    L += ["", f"{v['n_dpg']} DPG and {v['n_ctl']} other villages in {v['n_khg']} KHG.", "",
          "![means](figures/means_hs.png)", "",
          "### The DPG part of each KHG against the rest of the KHG", "",
          "The Bluebook chose its target villages in 2026, possibly for their fire in 2019-2025, which would bias the comparison above. "
          "Here the comparison is all land outside the DPG villages in the same KHG; intervals from resampling whole KHG.", "",
          "| Period | VIIRS hotspots | Burned area |", "|---|---|---|"]
    hv, hb = R["rr"]["halves_viirs"], R["rr"]["halves_burned"]
    for k in P_:
        a, b = hv["periods"].get(k), hb["periods"].get(k)
        L.append(f"| {lab[k]} | {rr_txt(a) if a else ''} | {rr_txt(b) if b else ''} |")
    for c in hv["contrasts"]:
        L.append(f"- {lab[c['post']]} against {lab[c['pre']]} (VIIRS): {c['ratio']:.2f} ({c['lo']:.2f} to {c['hi']:.2f})")
    L += ["", "### Near licences", "",
          f"Villages with at least half their area inside a licence or within {cfg['ring_km']} km of one, and the rest (VIIRS hotspots):", "",
          "| Period | In or near a licence | Farther |", "|---|---|---|"]
    rn, rf = R["rr"].get("near"), R["rr"].get("far")
    for k in P_:
        a = rn["periods"].get(k) if rn else None
        b = rf["periods"].get(k) if rf else None
        L.append(f"| {lab[k]} | {rr_txt(a) if a else ''} | {rr_txt(b) if b else ''} |")
    L += ["", "## Before the mapping (2012-2017 means)", "", "| | DPG villages | Other target villages |", "|---|---|---|"]
    for k, name in (("peat_km2", "Peat, km2"), ("hs_density", "VIIRS hotspots per km2 of peat per year"), ("share_licence", "Share inside a licence"),
                    ("share_ring", f"Share within {cfg['ring_km']} km of a licence, outside it")):
        b = R["balance"][k]
        L.append(f"| {name} | {b['dpg']:.3g} | {b['ctl']:.3g} |")
    L += ["", "## Limits", "",
          f"- The DPG set is the {R['n_dpg']} atlas villages with a polygon, not the DMPG list behind KLH's figure.",
          "- The atlas date is the mapping date; the year each village joined the programme is not in the data.",
          "- Village outlines are the Bluebook 2026 polygons, not the boundaries drawn in the participatory mapping.",
          "- Hotspots mark active fire at the satellite overpass; small or short fires are missed.",
          "- Fire is concentrated in dry years (2014, 2015, 2019, 2023); ratios in wet years rest on few hotspots.",
          "", "## Data", "",
          "- Villages: Bluebook 2026 target villages (`desa_target_pemulihan_ekosistem_gambut.gpkg`); BRG Atlas Desa Peduli Gambut (`dpg/dpg_villages_boundaries.gpkg`).",
          "- Fire: FIRMS VIIRS S-NPP 2012-2025, nominal and high confidence, vegetation fires (`hotspot_viirs_snpp_2012_2025.gpkg`); "
          "burned area 2015-2026 (`burnt_area_2015_2026_Indonesia.gpkg`); KLH MODIS hotspots January-September 2026, medium and high (`_data_hotspot_Januari_September_2026.gpkg`).",
          "- Peat: GFW composite peat extent. Licences: business licences 2025 (`landstatus/`). KHG: SK.129/2017 boundaries.", ""]
    path.write_text("\n".join(L), encoding="utf-8")


# ---------------------------------------------------------------- page

def pooled_rates(units, uy, cfg):
    """Fire per km2 of peat pooled over each group, per year, in the KHG that hold both groups (the rate-ratio sample)."""
    out = {}
    for k, count, years, scale in (("viirs", "n_hotspot_peat", VIIRS_YEARS, 1.0), ("burned", "burned_peat_km2", BURN_YEARS, 100.0)):
        C, T, D, _ = rate_arrays(units, uy, count, years, cfg["min_peat_km2"])
        out[k] = [[y, round(scale * C[D, j].sum() / T[D].sum(), 4), round(scale * C[~D, j].sum() / T[~D].sum(), 4)] for j, y in enumerate(years)]
    return out


def verdicts(R, forest):
    """Verdict cards, worded from the numbers so that a rerun with other data rewords them."""
    m, v, b = R["max_no_fire_dpg"], R["rr"]["viirs"], R["rr"]["burned"]
    out = []
    if m["share"] < 0.99:
        out.append({"title": "Not fire-safe", "figure": pct(m["share"]) + "<small>at best</small>",
                    "text": f"No year and no definition reaches 99% of DPG villages without fire. The best was {m['year']} "
                            f"({m['definition']}), a year when {pct(m['share_ctl'])} of the other target villages were also without fire."})
    else:
        out.append({"title": "99% reached", "figure": pct(m["share"]),
                    "text": f"{m['year']}, {m['definition']}; other target villages: {pct(m['share_ctl'])}."})
    pre, post, bpost = v["periods"]["dry_pre"], v["periods"]["dry_post"], b["periods"]["dry_post"]
    more = [q for q in (post, bpost) if q["lo"] > 1]
    out.append({"title": "Still more fire than comparable villages" if more else "About as much fire as comparable villages",
                "figure": f"{bpost['rr']:.1f}×<small>burned peat, 2019 and 2023</small>",
                "text": f"Per km2 of peat, against other target villages of the same KHG: hotspots {rr_txt(pre)} times in 2014 and 2015, "
                        f"{rr_txt(post)} in 2019 and 2023; burned area {rr_txt(bpost)} in 2019 and 2023."})
    c = next(x for x in v["contrasts"] if x["post"] == "dry_post")
    shrank, grew = [f for f in forest if f["hi"] < 1], [f for f in forest if f["lo"] > 1]
    t = ("No detectable drop after the mapping" if not shrank else "The gap shrank in some comparisons")
    x = (f"The hotspot gap in 2019 and 2023 divided by the gap in 2014 and 2015: {c['ratio']:.2f} ({c['lo']:.2f} to {c['hi']:.2f}). "
         f"Of {len(forest)} comparisons, {len(shrank) or 'none'} show the gap shrinking"
         + (f" and {len(grew)} show it growing ({'; '.join(g['label'] + ': ' + format(g['ratio'], '.2f') for g in grew)})." if grew else "."))
    out.append({"title": t, "figure": f"{c['ratio']:.2f}<small>({c['lo']:.2f}–{c['hi']:.2f})</small>", "text": x})
    if m["share"] < 0.99 and not shrank:
        out.append({"title": "For the prioritisation", "figure": "",
                    "text": "DPG presence is no reason to lower a KHG's priority. An effect of the programme can only be measured "
                            "with the official DMPG list and the year each village joined."})
    return out


def page_data(cfg, R, rates, mapd):
    nf, nc = pd.DataFrame(R["no_fire_dpg"]).set_index("year"), pd.DataFrame(R["no_fire_ctl"]).set_index("year")
    ser = (lambda d, col: [[int(y), round(100 * d.loc[y, col], 1)] for y in d.index if col in d and pd.notna(d.loc[y, col])])
    k26 = [nf.loc[2026, "no_klh_hotspot"], nc.loc[2026, "no_klh_hotspot"]] if 2026 in nf.index else None
    panels = [{"title": "No hotspot in the village, % of villages (VIIRS; dots: KLH 2026, Jan-Sep)", "dpg": ser(nf, "no_viirs_hotspot"),
               "ctl": ser(nc, "no_viirs_hotspot"), "xdom": [2012, 2026],
               "points": [[2026, round(100 * k26[0], 1), "--dpg"], [2026, round(100 * k26[1], 1), "--ctl"]] if k26 else []},
              {"title": "No burned area, % of villages", "dpg": ser(nf, "no_burned_area"), "ctl": ser(nc, "no_burned_area"), "xdom": [2015, 2025], "points": []},
              {"title": "Less than 1% of the village burned, % of villages", "dpg": ser(nf, "burned_lt1pct"), "ctl": ser(nc, "burned_lt1pct"), "xdom": [2015, 2025], "points": []}]
    rr = {k: [[q["year"], round(q["rr"], 3), round(q["lo"], 3), round(q["hi"], 3)] for q in sorted(R["rr"][k]["by_year"], key=lambda q: q["year"])] for k in ("viirs", "burned")}
    lab = {k: (f"{v[0]}-{v[-1]}" if v == list(range(v[0], v[-1] + 1)) and len(v) > 2 else " and ".join(map(str, v))) for k, v in cfg["periods"].items()}
    designs = [("viirs", "Other target villages", "hotspots"), ("burned", "Other target villages", "burned area"),
               ("halves_viirs", "Rest of the KHG", "hotspots"), ("halves_burned", "Rest of the KHG", "burned area"),
               ("near", "Villages in or near a licence", "hotspots"), ("far", "Villages farther from licences", "hotspots")]
    forest = []
    for key, against, what in designs:
        for c in R["rr"][key]["contrasts"]:
            if key != "viirs" and c["post"] != "dry_post":
                continue
            forest.append({"label": f"{against} · {what} · {lab[c['post']]} vs {lab[c['pre']]}", "ratio": c["ratio"], "lo": c["lo"], "hi": c["hi"],
                           "what": f"DPG {what} rate ÷ {against.lower()}, {lab[c['post']]}, divided by the same ratio in {lab[c['pre']]}"})
    rows = []
    for key, against, what in designs:
        r = R["rr"][key]
        for k, q in r["periods"].items():
            rows.append([against, what, lab[k], f"{q['rr']:.2f}", f"{q['lo']:.2f}–{q['hi']:.2f}", r["n_dpg"], r["n_ctl"]])
    m = R["max_no_fire_dpg"]
    v = R["rr"]["viirs"]
    return {
        "generated": pd.Timestamp.today().date().isoformat(), "map": mapd, "n_dpg": R["n_dpg"], "n_ctl": R["n_ctl"], "verdicts": verdicts(R, forest),
        "lead1": f"KLH reported that 99% of DMPG villages had no fire. Under any reading, the DPG villages fall short: "
                 f"{pct(R['ever_viirs_dpg'])} had a VIIRS hotspot and {pct(R['ever_burn_dpg'])} some burned area in {cfg['post_from']}-2025. "
                 f"In wet years the shares without fire are high in both groups alike.",
        "no_fire_panels": panels, "rates": rates, "rr": rr,
        "lead3": f"Fire per km2 of peat in DPG villages divided by the same in other target villages of the same KHG "
                 f"(Mantel-Haenszel, stratified by KHG), with the 95% interval from {cfg['bootstrap']} bootstrap samples. "
                 f"Above 1×: DPG villages burn more. {v['n_dpg']} DPG and {v['n_ctl']} other villages in {v['n_khg']} KHG.",
        "lead4": "The ratio after the mapping divided by the ratio before it. Two baselines are shown because 2015, the extreme fire "
                 "year, may be the year the villages were picked for. The second design compares the DPG part of each KHG with the "
                 "rest of the KHG, which does not depend on how the Bluebook picked its target villages.",
        "forest": forest,
        "table": {"cols": ["Compared with", "Measure", "Years", "Rate ratio", "95% interval", "DPG units", "Other units"], "rows": rows},
        "method": [f"Units: the Bluebook 2026 target villages and the DPG villages outside them ({R['n_dpg'] + R['n_ctl']:,} in all); DPG = the {R['n_dpg']} of the {R['n_atlas']} BRG atlas villages with a boundary (KLH 2023, BIG 2026), matched by name.",
                   "Fire per village and year: FIRMS VIIRS hotspots on peat (2012-2025), burned peat (2015-2025), KLH MODIS hotspots (2026, January to September); peat from the GFW composite extent.",
                   "Rate ratio: Mantel-Haenszel, DPG against other villages, stratified by KHG, so every comparison is inside one KHG.",
                   "Intervals: villages resampled within KHG and group (KHG resampled whole for the rest-of-KHG design).",
                   f"In or near a licence: at least half the village inside a licence or within {cfg['ring_km']} km of one."],
        "limits": [f"The DPG set is the {R['n_dpg']} atlas villages with a polygon, not the DMPG list behind KLH's 99%.",
                   "The atlas gives the mapping date, not the year each village joined the programme.",
                   "Village outlines are the Bluebook 2026 polygons, not the boundaries drawn in the participatory mapping.",
                   "Hotspots mark active fire at the satellite overpass; small or short fires are missed.",
                   "Fire is concentrated in dry years; ratios in wet years rest on few hotspots."],
        "data": ["Bluebook 2026 target villages: desa_target_pemulihan_ekosistem_gambut.gpkg. BRG Atlas Desa Peduli Gambut: dpg/dpg_villages_boundaries.gpkg (repeat_common.fetch_dpg_atlas, fetch_dpg_boundaries; boundaries from batas_desa_indonesia_2023_KLH.gpkg).",
                 "FIRMS VIIRS S-NPP 2012-2025, nominal and high confidence, vegetation fires. Burned area 2015-2026. KLH MODIS hotspots January-September 2026, medium and high.",
                 "GFW composite peat extent. Business licences 2025. KHG boundaries SK.129/2017.",
                 "Rerun: python -m repeat_prioritisation.investigations.dmpg --config configs/investigations/dmpg.yaml (--reuse reads the cached fire table)."]}


def map_data(v, khg, vu, uy, cfg):
    """Village polygons with their fire per km2 of peat, and the outlines of the KHG that hold DPG villages."""
    per = lambda years, col: uy[uy["year"].isin(years)].groupby("khg_id")[col].mean()
    m = vu.set_index("khg_id")[["peat_km2"]].join([per([2014, 2015], "n_hotspot_peat").rename("a"), per([2019, 2023], "n_hotspot_peat").rename("b"),
                                                    per(range(cfg["post_from"], 2026), "burned_peat_km2").rename("u")])
    ok = m["peat_km2"] >= cfg["min_peat_km2"]
    for c in ("a", "b"):
        m[c] = (m[c] / m["peat_km2"]).where(ok)
    m["u"] = (100 * m["u"] / m["peat_km2"]).where(ok)
    r = lambda x: None if pd.isna(x) else round(float(x), 3)
    vs = v.set_index("khg_id")
    out = []
    for kid, g in vs.iterrows():
        q = m.loc[kid] if kid in m.index else None
        out.append({"n": f"{g['DESA_2023']}, {g['KEC_2023']}, {g['KABKO_2023']}", "d": int(bool(g["dpg"])), "k": g["khg_name"] if isinstance(g["khg_name"], str) else "",
                    "p": r(q["peat_km2"]) if q is not None else None, "a": r(q["a"]) if q is not None else None,
                    "b": r(q["b"]) if q is not None else None, "u": r(q["u"]) if q is not None else None, "r": O._rings(g.geometry, 0.0015)})
    hk = khg[khg["khg_id"].isin(v.loc[v["dpg"], "khg"].dropna())]
    b = v[v["dpg"]].total_bounds
    return {"villages": out, "khg": [{"n": k.nama, "r": O._rings(k.geometry, 0.002)} for k in hk.itertuples()],
            "bounds": [round(float(x), 3) for x in b]}


def assemble_page(data, path):
    nat = ROOT / "national" / "assets"
    tpl = (ASSETS / "dmpg.html").read_text(encoding="utf-8")
    data = {**data, "style": json.loads((nat / "basemap-positron.json").read_text(encoding="utf-8"))}
    html = (tpl.replace("/*D3*/", (nat / "d3.v7.9.0.min.js").read_text(encoding="utf-8"))
            .replace("/*ML*/", (nat / "maplibre-gl.v5.24.0.js").read_text(encoding="utf-8"))
            .replace("/*MLCSS*/", (nat / "maplibre-gl.v5.24.0.css").read_text(encoding="utf-8"))
            .replace("/*JS*/", (ASSETS / "dmpg.js").read_text(encoding="utf-8"))
            .replace("/*DATA*/", "const DATA=" + json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";"))
    path.write_text(html, encoding="utf-8")


# ---------------------------------------------------------------- main

def run(cfg, reuse=False):
    out = Path(cfg["out"])
    cache = out / "cache"
    for d in (out / "figures", cache):
        d.mkdir(parents=True, exist_ok=True)
    v, khg = villages(cfg)
    halves = khg_halves(v, khg)
    if reuse and (out / "unit_year.csv").exists():
        units = pd.read_csv(out / "units.csv")
        uy = pd.read_csv(out / "unit_year.csv")
    else:
        sampler = P.PeatSampler(cfg["peat_extent"])
        ls = cached(cache / "licence_shares.csv", lambda: licence_shares(cfg, v).assign(khg_id=v["khg_id"].to_numpy()))
        v = v.merge(ls, on="khg_id", how="left")
        allu = pd.concat([v.assign(kind="village"), halves.assign(kind="khg_half")], ignore_index=True)
        allu = gpd.GeoDataFrame(allu, geometry="geometry", crs=4326)
        units, uy = measure(cfg, allu, sampler, cache)
        units.drop(columns=["geometry", "geom_aea"]).to_csv(out / "units.csv", index=False)
        uy.to_csv(out / "unit_year.csv", index=False)
    vu, hu = units[units["kind"] == "village"], units[units["kind"] == "khg_half"]
    mp, pf = cfg["min_peat_km2"], cfg["post_from"]
    R = {"n_atlas": int(len(pyogrio.read_dataframe(Path(cfg["data"]) / cfg["inputs"]["dpg"], read_geometry=False))), "n_dpg": int(vu["dpg"].sum()),
         "n_dpg_khg": int((vu["dpg"] & vu["khg"].notna()).sum()), "n_ctl": int((~vu["dpg"]).sum())}
    R["no_fire_dpg"], R["no_fire_ctl"] = no_fire(vu, uy, True), no_fire(vu, uy, False)
    nf, nc = pd.DataFrame(R["no_fire_dpg"]).set_index("year"), pd.DataFrame(R["no_fire_ctl"]).set_index("year")
    cols = [c for c, _ in NO_FIRE if c in nf]
    y, c = nf[cols].stack().idxmax()
    R["max_no_fire_dpg"] = {"year": int(y), "definition": dict(NO_FIRE)[c].lower(), "share": float(nf.loc[y, c]), "share_ctl": float(nc.loc[y, c])}
    w = uy[uy["year"].between(pf, 2025)].groupby("khg_id")[["n_hotspot", "burned_km2"]].sum()
    dv = vu.set_index("khg_id").join(w)
    R["ever_viirs_dpg"] = float((dv.loc[dv["dpg"], "n_hotspot"] > 0).mean())
    R["ever_burn_dpg"] = float((dv.loc[dv["dpg"], "burned_km2"] > 0).mean())
    near = vu.set_index("khg_id")[["share_licence", "share_ring"]].sum(axis=1) >= 0.5
    R["rr"] = {"viirs": rate_ratios(vu, uy, "n_hotspot_peat", VIIRS_YEARS, cfg),
               "burned": rate_ratios(vu, uy, "burned_peat_km2", BURN_YEARS, cfg),
               "halves_viirs": rate_ratios(hu, uy, "n_hotspot_peat", VIIRS_YEARS, cfg, by="stratum"),
               "halves_burned": rate_ratios(hu, uy, "burned_peat_km2", BURN_YEARS, cfg, by="stratum"),
               "near": rate_ratios(vu[vu["khg_id"].map(near).fillna(False).to_numpy(bool)], uy, "n_hotspot_peat", VIIRS_YEARS, cfg),
               "far": rate_ratios(vu[~vu["khg_id"].map(near).fillna(False).to_numpy(bool)], uy, "n_hotspot_peat", VIIRS_YEARS, cfg)}
    pre = uy[uy["year"].between(2012, 2017)].groupby("khg_id")["n_hotspot_peat"].mean()
    b = vu.set_index("khg_id").join(pre.rename("n_pre"))
    b = b[b["khg"].notna() & (b["peat_km2"] >= mp)].assign(hs_density=lambda d: d["n_pre"] / d["peat_km2"])
    R["balance"] = {k: {"dpg": float(b.loc[b["dpg"], k].mean()), "ctl": float(b.loc[~b["dpg"], k].mean())}
                    for k in ("peat_km2", "hs_density", "share_licence", "share_ring")}
    fig_rr([("VIIRS hotspots on peat", R["rr"]["viirs"]), ("Burned peat", R["rr"]["burned"])], out / "figures" / "rate_ratio.png", cfg["mapped"])
    fig_means(vu, uy, out / "figures" / "means_hs.png", mp)
    fig_nofire(R["no_fire_dpg"], R["no_fire_ctl"], out / "figures" / "no_fire.png")
    for old in ("event_study.png",):
        (out / "figures" / old).unlink(missing_ok=True)
    (out / "results.json").write_text(json.dumps(R, indent=1), encoding="utf-8")
    report(cfg, R, out / "report.md")
    assemble_page(page_data(cfg, R, pooled_rates(vu, uy, cfg), map_data(v, khg, vu, uy, cfg)), out / "dmpg.html")
    log.info("-> %s", out)
    return R


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--reuse", action="store_true", help="read unit_year.csv instead of measuring fire again")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    run(P._expand(yaml.safe_load(Path(a.config).read_text(encoding="utf-8"))), a.reuse)


if __name__ == "__main__":
    main()
