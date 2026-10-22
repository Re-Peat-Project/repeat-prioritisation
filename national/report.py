#!/usr/bin/env python3
"""Self-contained HTML report of the national KHG profile: ranking, method, validation, and a profile page per top KHG.

  python -m national.report --config configs/examples/national_profile.yaml [--top 25] [--out report.html]

Reads what `python -m national.profile` wrote (operational/ for the ranking, validate/ for the held-out test) and the
input layers named in the config, for the maps of the top KHG. Every number comes from those files; the sentences are
rules over the numbers. Needs the same environment variables as the profile run, plus repeat-common on the path.
"""
from __future__ import annotations

import argparse
import copy
import html
import json
import sys
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import pyogrio
import shapely
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT.parent / "repeat-common" / "src"))
from national import profile as P  # noqa: E402
from repeat_common import htmlkit as H  # noqa: E402

esc = html.escape
CLASS_LABEL = {"Fokus nasional: tinggi": "High", "Fokus nasional: sedang": "Medium", "Fokus nasional: rendah": "Low",
               "Tidak diperingkat (KHG kecil)": "Not ranked (small)"}
CONF_LABEL = {"tinggi": "high", "sedang": "medium", "rendah": "low"}
INDICATORS = [  # code, label, unit, nd, source, direction
    ("u_fire_freq", "Mean annual burned share", "% of KHG area per year", 2, "Burnt-area polygons", "higher = more fire"),
    ("u_burn_repeat", "Share burned twice or more", "% of KHG area", 2, "Burnt-area polygons", "higher = repeat burns"),
    ("u_hotspot", "Hotspot density", "per km2 per year", 2, "FIRMS VIIRS S-NPP", "higher = more fire"),
    ("u_hotspot_now", "Hotspots this year (KLH)", "hotspots per km2, year to date", 2, "KLH MODIS hotspots 2026", "higher = more fire this year"),
    ("u_canal_density", "Canal density", "km per km2", 2, "OSM-derived canal layer", "higher = more drained"),
]
PCT = {"u_fire_freq", "u_burn_repeat"}   # stored as fractions, shown as %
BASIS = {"v": "area"}                    # set in build(): "peat" when the rates are per km2 of peat


def unit_text(u):
    return (u.replace("KHG area", "peat area").replace("per km2 per year", "per peat km2 per year").replace("per km2, year", "per peat km2, year")
            if BASIS["v"] == "peat" else u)


NOW = {"period": "", "months": []}      # set in build(): label of the current-year period and its months


def num(v, nd=1):
    return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v:,.{nd}f}"


def load_results(cfg, mode_rank, mode_valid="validate"):
    base = Path(cfg["out"])
    prof = pd.read_csv(base / mode_rank / "profile.csv", dtype={"khg_id": str})
    yearly = pd.read_csv(base / mode_rank / "yearly.csv", dtype={"khg_id": str})
    rep = json.loads((base / mode_rank / "report.json").read_text(encoding="utf-8"))
    vrep = json.loads((base / mode_valid / "report.json").read_text(encoding="utf-8")) if (base / mode_valid / "report.json").exists() else None
    return prof, yearly, rep, vrep


def selected_table(prof, ranked):
    """The team's 12 main KHG and reserves from re-peat/sites/selected_khg.csv, placed in the ranking."""
    path = Path(P.os.environ.get("REPEAT_HUB", ROOT.parent / "re-peat")) / "sites" / "selected_khg.csv"
    if not path.exists():
        return []
    sel = pd.read_csv(path).fillna("")
    reg = prof[["khg_id", "nama"]].assign(_k=lambda d: d.nama.map(P.norm_name))
    rows = []
    for r in sel.itertuples():
        name = r.khg_name_in_gpkg or ""
        note = ""
        if not name and "Lalang" in r.match_status:
            name, note = "KHG Air Banyuasin - Air Lalang", "candidate, not yet confirmed by the team"
        m = reg[reg._k == P.norm_name(name)] if name else reg.iloc[0:0]
        rows.append((r, m.khg_id.iloc[0] if len(m) else None, note))
    out = []
    for r, kid, note in rows:
        d = prof[prof.khg_id == kid].iloc[0] if kid else None
        given = r.name_as_given.split("corrected by team:")[-1].strip(" )") if "corrected by team:" in r.name_as_given else r.name_as_given
        out.append({"province": r.province, "role": r.role, "given": given, "kid": kid, "note": note,
                    "nama": None if d is None else d.nama, "rank": None if d is None or pd.isna(d.peringkat) else int(d.peringkat),
                    "kelas": None if d is None else d.kelas, "area": None if d is None else d.area_km2,
                    "conf": None if d is None else d.confidence,
                    "score": None if d is None else d.skor_risiko,
                    "rank_now": None if d is None or pd.isna(d.get("peringkat_now")) else int(d.peringkat_now)})
    return out


def narrative(r, ranked, nb_years, peak=None):
    """Rule-based sentences over the numbers of one KHG. No number is typed here."""
    pct = lambda col: 100 * (ranked[col].dropna() < r[col]).mean() if pd.notna(r[col]) else np.nan
    above = lambda col: "the highest of the ranked KHG" if pct(col) >= 99.5 else f"higher than {pct(col):.0f}% of the ranked KHG"
    s = [f"{r.nama} (<code>{esc(r.khg_id)}</code>) covers {num(r.area_km2, 0)} km2 in {esc(str(r.province))}. "
         f"It ranks {int(r.peringkat)} of {len(ranked)} ranked KHG (score {r.skor_risiko:.2f})."]
    peat = BASIS["v"] == "peat"
    if peat and pd.notna(r.get("peat_km2")):
        gpm = r.get("peat_frac_gpm1km")
        s.append(f"Peat covers {num(r.peat_km2, 0)} km2 of it ({num(100 * r.peat_frac, 0)}%, GFW composite extent"
                 + (f"; the 1 km Global Peatland Map gives {num(100 * gpm, 0)}%" if pd.notna(gpm) else "") + "). Fire is counted on peat only, and rates are per km2 of peat.")
    s.append(f"On average {num(100 * r.u_fire_freq, 1)}% of its {'peat ' if peat else ''}area burned per year in the baseline, and {num(100 * r.burned_ever_frac, 0)}% burned at least once "
             f"({num(100 * r.u_burn_repeat, 1)}% twice or more); this is {above('u_fire_freq')}.")
    s.append(f"VIIRS recorded {num(r.u_hotspot, 2)} hotspots per km2 per year ({above('u_hotspot')}), "
             f"with a mean fire radiative power of {num(r.frp_mean_mw, 1)} MW per detection; {num(100 * r.hs_high_share, 0)}% are high-confidence.")
    if pd.notna(r.get("u_hotspot_now")):
        s.append(f"This year ({NOW['period']}, KLH hotspots of medium or high confidence): {num(r.hs_now_kept, 0)} hotspots {'on peat' if peat else 'in the KHG'}, "
                 f"{num(r.u_hotspot_now, 2)} per km2{' of peat' if peat else ''} ({above('u_hotspot_now')}); {num(100 * r.hs_now_high_share, 0)}% are high confidence"
                 + (f"; the busiest month is {peak}" if peak else "")
                 + (f". On this year's hotspots alone it ranks {int(r.peringkat_now)} of {len(ranked)} by density and {int(r.peringkat_now_n)} by number of hotspots." if pd.notna(r.get("peringkat_now")) else "."))
    if pd.notna(r.u_canal_density):
        s.append(f"The canal layer has {num(r.canal_km, 0)} km of canals ({num(r.u_canal_density, 2)} km per km2, {above('u_canal_density')})"
                 + (f" and {int(r.n_infra_ada)} existing hydrological structures." if r.n_infra_ada > 0 else "; no existing structures are recorded."))
    else:
        s.append("The canal layer has no canals here, which means not mapped; canal density is not scored for this KHG.")
    if r.get("n_tma_stations", 0) and r.n_tma_stations > 0:
        s.append(f"SiTMAT has {int(r.n_tma_stations)} station(s) inside; the water table was deeper than 0.4 m on {num(100 * r.tma_deep_share, 0)}% of days "
                 f"({str(r.tma_period_start)[:10]} to {str(r.tma_period_end)[:10]}, one season).")
    if pd.notna(r.get("deficit_mean_mm")):
        s.append(f"Climate (TerraClimate, 2015-2021): the dry-season water deficit averages {num(r.deficit_mean_mm, 0)} mm and June-October rain {num(r.rain_dry_mean_mm, 0)} mm"
                 + ".")
    if pd.notna(r.get("lc_tree")):
        s.append(f"Land cover (ESA WorldCover, sampled at 250 m): {num(100 * r.lc_tree, 0)}% tree, {num(100 * r.lc_shrub, 0)}% shrub, {num(100 * r.lc_grass, 0)}% grass, "
                 f"{num(100 * r.lc_crop, 0)}% cropland, {num(100 * r.lc_wetland, 0)}% herbaceous wetland, {num(100 * r.lc_mangrove, 0)}% mangrove.")
    if pd.notna(r.peat_cover_frac):
        s.append(f"The BBSDLP peat depth map covers {num(100 * r.peat_cover_frac, 0)}% of the KHG (mean class midpoint {num(r.peat_depth_mean_cm, 0)} cm); "
                 "this map is incomplete nationally, so it is shown but not scored.")
    return " ".join(s)


def layers_for(cfg, r, years):
    """JSON layers for the map of one KHG, read from the input layers with a mask on its boundary."""
    data, inp = Path(cfg["data"]), cfg["inputs"]
    g = shapely.make_valid(r.geom)
    tol = 0.0003 + 0.00002 * np.sqrt(r.area_km2)
    out = {"bounds": list(g.bounds), "outline": H._rings(g, tol)}
    # burned patches by number of burns in the window
    ycols = [f"BA_{y}" for y in range(2015, 2027)]
    b = P._read_mask(data / inp["burned"], g, columns=ycols)
    items = []
    if len(b):
        win = [c for c in ycols if years[0] <= int(c[3:]) <= years[1]]
        n = b[win].notna().sum(axis=1).to_numpy()
        geom = shapely.intersection(shapely.make_valid(b.geometry.values), g)
        for k in (1, 2, 3, 4):
            sel = (n == k) if k < 4 else (n >= 4)
            if sel.any():
                u = shapely.union_all(geom[sel])
                if not u.is_empty:
                    items.append({"polys": H._rings(u, tol), "p": {"n": k}})
    out["burn"] = items
    # canals and rivers
    for key, src, cap in (("canals", "canals", 9000), ("rivers", "rivers", 4000)):
        if src not in inp:
            out[key] = []
            continue
        c = P._read_mask(data / inp[src], g, columns=[])
        lines = []
        if len(c):
            geo = shapely.intersection(shapely.make_valid(c.geometry.values), g)
            lines = H.pack_lines(pd.DataFrame({"geometry": geo}), tol=tol / 2)
            lines.sort(key=lambda t: -len(t[1]))
            lines = lines[:cap]
        out[key] = [{"pts": ln[1]} for ln in lines]
    # structures
    s = P._read_mask(data / inp["blocks"], g, columns=[])
    pts = [] if s.empty else [(p.x, p.y) for p in s.geometry if g.contains(p)]
    step = max(1, len(pts) // 2500)
    out["infra"] = [{"x": round(x, 4), "y": round(y, 4)} for x, y in pts[::step]]
    out["infra_n"] = len(pts)
    # hotspot bins (kept detections in the window)
    h = P._read_mask(data / inp["hotspots"], g, columns=["year", "confidence", "type", "frp"])
    cell = 0.01 if r.area_km2 < 1500 else 0.02
    bins = []
    if len(h):
        h = h[h["type"].isin(cfg["hotspots"]["types"]) & h["confidence"].astype(str).str.lower().isin([c.lower() for c in cfg["hotspots"]["confidence"]])
              & h["year"].between(*years)]
        xs, ys = h.geometry.x.to_numpy(), h.geometry.y.to_numpy()
        inside = shapely.contains_xy(g, xs, ys)
        d = pd.DataFrame({"i": np.floor(xs[inside] / cell).astype(int), "j": np.floor(ys[inside] / cell).astype(int), "frp": h["frp"].to_numpy()[inside]})
        a = d.groupby(["i", "j"]).agg(n=("frp", "size"), frp=("frp", "sum")).reset_index()
        a = a.sort_values("n", ascending=False).head(3500)
        bins = [{"x": round((i + .5) * cell, 4), "y": round((j + .5) * cell, 4), "n": int(n)} for i, j, n in zip(a.i, a.j, a.n)]
    out["hot"], out["hot_cell_km"] = bins, round(cell * 111, 1)
    # this year's hotspots as they are (points, not cells): medium and high confidence inside the KHG, on or off peat
    now_pts = []
    if inp.get("hotspots_now") and (data / inp["hotspots_now"]).exists():
        h2 = P._read_mask(data / inp["hotspots_now"], g, columns=["layer", "C_LEVEL", "Kepercayaa"])
        if len(h2):
            lvl = h2["C_LEVEL"].fillna(h2["Kepercayaa"]).astype("string").str.lower().map(P.LEVEL)
            keep = lvl.isin(cfg["now"]["levels"]).to_numpy()
            h2, lvl = h2[keep], lvl[keep]
            xs, ys = h2.geometry.x.to_numpy(), h2.geometry.y.to_numpy()
            inside = shapely.contains_xy(g, xs, ys)
            xs, ys, lvl, h2 = xs[inside], ys[inside], lvl[inside], h2[inside]
            pe = cfg.get("peat", {}).get("extent")
            ps = P.PeatSampler(pe) if pe and Path(pe).exists() else None
            onp = (ps.sample(ps.window(g), xs, ys) == 1) if ps is not None else np.ones(len(xs), bool)
            mon = h2["layer"].str[:2].astype(int).to_numpy()
            hi = (lvl == "high").to_numpy()
            order = np.argsort(-hi.astype(int), kind="stable")[:9000]        # keep every high-confidence point first if a KHG has more than 9000
            now_pts = [{"x": round(float(xs[k]), 4), "y": round(float(ys[k]), 4), "m": int(mon[k]), "h": int(hi[k]), "p": int(onp[k])} for k in order]
            out["now_total"] = int(len(xs))
    out["now"] = now_pts
    out["now_n"] = out.get("now_total", len(now_pts))
    return out


def indicator_rows(r, ranked):
    rows = []
    for code, lab, unit, nd, src, dirn in INDICATORS:
        v = r[code]
        scale = 100 if code in PCT else 1
        p = float((ranked[code].dropna() < v).mean() * 100) if pd.notna(v) else None
        med = ranked[code].median()
        rows.append({"label": lab, "unit": unit_text(unit), "v": None if pd.isna(v) else round(float(v) * scale, 3), "p": p,
                     "med": round(float(med) * scale, 3), "src": src})
    return rows


def kv_info(r):
    return [("Official code", r.khg_id), ("Province", r.province), ("Kabupaten", r.kabupaten),
            ("Area (boundary file)", f"{num(r.area_km2, 0)} km2"), ("Area (Kepmen 2017)", f"{num(r.area_ha_kepmen / 100, 0)} km2"),
            ("Existing structures (BRGM)", f"{int(r.n_infra_ada)}"), ("Target villages (Bluebook 2026)", f"{int(r.n_desa_target)}"),
            ("Hotspots kept, baseline", f"{num(r.hs_kept_baseline, 0)} ({num(100 * r.hs_high_share, 0)}% high conf.)"),
            ("Mean FRP per detection", f"{num(r.frp_mean_mw, 1)} MW"),
            ("SiTMAT stations / days deeper than 0.4 m", "none" if not r.get("n_tma_stations", 0) else f"{int(r.n_tma_stations)} / {num(100 * r.tma_deep_share, 0)}%"),
            ("Peat extent (GFW, 76 m)", "n/a" if pd.isna(r.get("peat_km2")) else f"{num(r.peat_km2, 0)} km2 ({num(100 * r.peat_frac, 0)}% of KHG)"),
            ("Peat extent (Global Peatland Map, 1 km)", "n/a" if pd.isna(r.get("peat_frac_gpm1km")) else f"{num(100 * r.peat_frac_gpm1km, 0)}% of KHG"),
            ("Rank with rates per km2 of KHG instead", "n/a" if pd.isna(r.get("peringkat_area")) else f"{int(r.peringkat_area)}"),
            ("Peat depth map coverage (BBSDLP)", "none" if pd.isna(r.peat_cover_frac) else f"{num(100 * r.peat_cover_frac, 0)}% of area"),
            ("Sensitivity: share of weight draws in the high class", num(100 * r.p_fokus_tinggi, 0) + "%"),
            ("Data confidence", CONF_LABEL.get(r.confidence, r.confidence))]


SECTION_CSS = """
.prof h3{margin:0}.prof .meta{display:flex;gap:8px;flex-wrap:wrap;margin:6px 0 10px}
.prof .maps{display:grid;grid-template-columns:minmax(0,1.25fr) minmax(0,1fr);gap:14px;margin-top:10px}
@media (max-width:900px){.prof .maps{grid-template-columns:minmax(0,1fr)}}
.prof canvas.map{height:420px}.prof .layers{display:flex;gap:14px;flex-wrap:wrap;font-size:12.5px;margin-top:6px;color:var(--muted)}
.prof .layers label{display:inline-flex;gap:5px;align-items:center}
.prof p.txt{max-width:92ch;margin:6px 0}
table.ind{border-collapse:collapse;width:100%;font-size:13px;margin-top:8px}table.ind td,table.ind th{padding:4px 6px;border-bottom:1px solid var(--grid);text-align:right}
table.ind td:first-child,table.ind th:first-child{text-align:left}table.ind th{color:var(--muted);font-weight:600}
.pbar{display:inline-block;width:70px;height:7px;background:var(--grid);border-radius:4px;vertical-align:middle;margin-right:6px;overflow:hidden}
.pbar i{display:block;height:100%;background:var(--blue);border-radius:4px}
.toc{columns:3;column-gap:24px;font-size:13.5px}@media (max-width:900px){.toc{columns:1}}.toc a{display:block;text-decoration:none;padding:1px 0}
.rk td.n,.rk th.n{text-align:right}.rk td{white-space:nowrap}.rk input{width:240px}
.badge.med{color:var(--warn)}
.srt th{cursor:pointer}
table.data.l3 th:nth-child(-n+3),table.data.l3 td:nth-child(-n+3){text-align:left}
table.data.l2 th:nth-child(-n+2),table.data.l2 td:nth-child(-n+2){text-align:left}
table.data.l3 th:first-child,table.data.l3 td:first-child{text-align:left}
.rk th:nth-child(2),.rk th:nth-child(3){text-align:left}
.prof .legend{position:static;margin-top:8px;max-width:none;display:flex;gap:14px;flex-wrap:wrap;align-items:center}
.prof .legend .cat{margin:0}.prof .legend>div:first-child{font-weight:600;color:var(--fg)}
#scatter{max-width:820px}
"""


def build(cfg, top_n, mode, out_path):
    prof, yearly, rep, vrep = load_results(cfg, mode)
    nb = cfg["years"]["baseline"] if mode == "validate" else [cfg["years"]["baseline"][0], cfg["years"]["validation"][1]]
    nyears = nb[1] - nb[0] + 1
    ranked = prof[prof.skor_risiko.notna()].sort_values("peringkat").reset_index(drop=True)
    small = prof[prof.skor_risiko.isna()]
    top = ranked.head(top_n)
    khg = P.load_khg(cfg)[["khg_id", "geometry", "island"]]
    prof = prof.merge(khg[["khg_id", "geometry"]].rename(columns={"geometry": "geom"}), on="khg_id", how="left")
    BASIS["v"] = str(prof["basis"].iloc[0]) if "basis" in prof else "area"
    nowrep = rep.get("now") or {}
    NOW["period"] = f"1 Jan to {pd.Timestamp(nowrep['last_date']).strftime('%d %b %Y').lstrip('0')}" if nowrep.get("last_date") else str(cfg["now"]["year"])
    NOW["months"] = nowrep.get("months", [])
    MONTH = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    s3dir = Path(cfg["out"]) / "stage3"
    s3p = pd.read_csv(s3dir / "stage3_profile.csv", dtype={"khg_id": str}) if (s3dir / "stage3_profile.csv").exists() else None
    s3y = pd.read_csv(s3dir / "stage3_yearly.csv", dtype={"khg_id": str}) if (s3dir / "stage3_yearly.csv").exists() else None
    if s3p is not None:
        prof = prof.merge(s3p.drop(columns=[c for c in s3p.columns if c in prof.columns and c != "khg_id"]), on="khg_id", how="left")
    prof_by = prof.set_index("khg_id")

    # ---------------------------------------------------------------- national map data
    cols = ["nama", "khg_id", "province", "area_km2", "skor_risiko", "peringkat", "kelas", "confidence", "u_fire_freq", "u_hotspot", "u_canal_density", "peat_km2", "u_hotspot_now"]
    import geopandas as gpd
    g = gpd.GeoDataFrame(prof[cols], geometry=prof["geom"], crs=4326)
    g["u_fire_freq"] = g["u_fire_freq"] * 100
    g["peringkat"] = g["peringkat"].where(g["peringkat"].notna(), None)
    g["kelas"] = g["kelas"].map(CLASS_LABEL)
    g["confidence"] = g["confidence"].map(CONF_LABEL)
    nat = H.pack_polygons(g, cols, tol=0.01)
    sel = selected_table(prof, ranked)
    sel_ids = {s["kid"] for s in sel if s["kid"] and s["role"] == "main" and not s["note"]}   # unconfirmed candidates are not highlighted
    for it in nat:
        it["p"]["sel"] = it["p"]["khg_id"] in sel_ids
        it["p"]["top"] = it["p"]["khg_id"] in set(top.khg_id)
    bounds = [94.5, -11.5, 141.5, 6.5]

    # ---------------------------------------------------------------- headline numbers
    hi = ranked[ranked.kelas == "Fokus nasional: tinggi"]
    peatb = BASIS["v"] == "peat"
    den_col = "peat_km2" if peatb else "area_km2"
    burn_km2 = lambda d: float((d.u_fire_freq * d[den_col]).sum())          # km2 burned per year, on peat under the peat basis
    facts = [("KHG profiled", f"{len(prof)}"), ("Ranked", f"{len(ranked)}"), ("Baseline", f"{nb[0]}-{nb[1]}"),
             ("Hotspot archive", "VIIRS S-NPP 2012-2025"), ("This year", "KLH MODIS " + NOW["period"]), ("Generated", date.today().isoformat())]
    hs_col = "hs_peat_baseline" if peatb and "hs_peat_baseline" in ranked else "hs_kept_baseline"
    share_h = 100 * hi[hs_col].sum() / ranked[hs_col].sum()
    share_b = 100 * burn_km2(hi) / burn_km2(ranked)
    share_a = 100 * hi[den_col].sum() / ranked[den_col].sum()
    top_a = top.area_km2.sum()
    top_p = top[den_col].sum()
    lede = (f"All {len(prof)} peat hydrological units (KHG) of Indonesia, profiled from open and project data and ranked on fire history, "
            f"hotspots and drainage. The {top_n} highest-ranked KHG get a full profile page. Everything on this page is computed from the data files by "
            f"<code>python -m national.profile</code> and <code>python -m national.report</code>, so it can be rerun when the data are updated.")

    # ---------------------------------------------------------------- sections
    sec = []
    sec.append(f"""<section id="summary"><h2>Summary</h2>
<p class="lede">The high-priority third of the {len(ranked)} ranked KHG holds {share_h:.0f}% of the vegetation-fire hotspots {'on peat' if peatb else ''} and {share_b:.0f}% of the burned {'peat ' if peatb else ''}area, on {share_a:.0f}% of the ranked KHG's {'peat' if peatb else ''} area.
The top {top_n} cover {num(top_a, 0)} km2 of KHG ({num(top_a / 10, 0)} thousand ha){f', {num(top_p, 0)} km2 of it peat' if peatb else ''}.</p>
<div class="grid2"><div class="card"><h3 style="margin-top:0">Top {top_n} for rewetting attention</h3><div class="tablewrap"><table class="data l3"><thead><tr><th>#</th><th>KHG</th><th>Province</th><th>km2</th><th>Score</th><th>Data confidence</th></tr></thead><tbody>
{''.join(f'<tr><td>{int(r.peringkat)}</td><td><a href="#p-{i}">{esc(r.nama)}</a></td><td style="text-align:left">{esc(str(r.province))}</td><td>{num(r.area_km2, 0)}</td><td>{r.skor_risiko:.2f}</td><td>{CONF_LABEL.get(r.confidence)}</td></tr>' for i, r in top.reset_index(drop=True).iterrows())}
</tbody></table></div></div>
<div class="card"><h3 style="margin-top:0">Read this first</h3>
<div class="note"><b>A screening, not a verdict.</b> The score ranks KHG on four data-derived indicators. Climate, land cover and water table are shown for the top {top_n} but not scored; peat depth, concessions and feasibility are not included yet; see Limits.</div>
<div class="note"><b>{'Rates per km2 of peat.' if BASIS['v'] == 'peat' else 'Normalised by KHG area.'}</b> {'Fire is counted on peat only (GFW peat extent, 76 m) and divided by the KHG peat area, so a KHG that is mostly non-peat is not diluted. The column "rank on KHG area" in the table shows what this changes.' if BASIS['v'] == 'peat' else 'Peat area per KHG was not available, so KHG with little peat are diluted.'}</div>
<div class="note"><b>Severity is approximated.</b> No fire-severity layer (dNBR) is available locally. Repeat burns and fire radiative power stand in for it.</div>
<div class="note"><b>Small KHG are not ranked.</b> {len(small)} KHG under {cfg['min_area_km2']} km2{(' or with under ' + str(cfg['peat']['min_peat_km2']) + ' km2 of peat') if BASIS['v'] == 'peat' else ''} are profiled but left out of the ranking (a few detections give extreme densities).</div></div></div></section>""")

    sec.append("""<section id="map"><h2>National map</h2><p class="lede">Every KHG, coloured by the chosen measure. Click one for its numbers; scroll to zoom, drag to pan, double-click to reset. KHG outlined in orange are the team's 12 main KHG.</p>
<div class="controls"><label>Colour by <select id="mapvar"><option value="skor_risiko">Priority score</option><option value="u_fire_freq">Burned share per year (%)</option><option value="u_hotspot">Hotspots per km2 per year</option><option value="u_canal_density">Canal density (km per km2)</option><option value="u_hotspot_now">Hotspots this year per km2 (KLH)</option><option value="peat_km2">Peat area (km2)</option></select></label></div>
<div class="maprow"><div class="mapbox"><canvas class="map" id="natmap"></canvas><div class="legend" id="natleg"></div><div class="hint">scroll, drag</div></div>
<div class="card side" id="natside"><h3>Selected KHG</h3><p style="color:var(--muted)">Click a KHG on the map.</p></div></div></section>""")

    def sel_row(s):
        if s["kid"] is None:
            return f'<tr><td style="text-align:left">{esc(s["province"])}</td><td style="text-align:left">{esc(s["given"])}</td><td colspan="6" style="text-align:left">not matched to the boundary file</td></tr>'
        rk = "not ranked" if s["rank"] is None else s["rank"]
        cl = CLASS_LABEL.get(s["kelas"], s["kelas"])
        note = f' <span class="badge warn">{esc(s["note"])}</span>' if s["note"] else ""
        return (f'<tr><td style="text-align:left">{esc(s["province"])}</td><td style="text-align:left">{esc(s["given"])}{note}</td><td style="text-align:left">{esc(s["role"])}</td>'
                f'<td>{rk}</td><td>{"n/a" if s["rank_now"] is None else s["rank_now"]}</td><td>{cl}</td><td>{CONF_LABEL.get(s["conf"], "")}</td><td>{num(s["area"], 0)}</td></tr>')
    sec.append(f"""<section id="selected"><h2>Where the team's selected KHG fall</h2><p class="lede">The 12 main KHG (and reserves) the team chose, placed in the data-driven ranking out of {len(ranked)}. A low rank does not remove a KHG from the project; it says that fire history, hotspots and canal density alone do not single it out.</p>
<div class="card tablewrap"><table class="data l3"><thead><tr><th>Province</th><th>As named by the team</th><th>Role</th><th>Rank</th><th>Rank this year</th><th>Class</th><th>Confidence</th><th>km2</th></tr></thead><tbody>{''.join(sel_row(s) for s in sel)}</tbody></table></div></section>""")

    # this year
    if "peringkat_now" in ranked and ranked.peringkat_now.notna().any():
        wn = (rep.get("now") or {}).get("weight")
        nt = ranked[ranked.peringkat_now.notna()].sort_values("peringkat_now").head(15)
        nt2 = ranked[ranked.peringkat_now_n.notna()].sort_values("peringkat_now_n").head(15)
        top_ids = {kid: i for i, kid in enumerate(top.khg_id)}

        def nrow(r, rank_col="peringkat_now"):
            name = f'<a href="#p-{top_ids[r.khg_id]}">{esc(r.nama)}</a>' if r.khg_id in top_ids else esc(r.nama)
            return (f"<tr><td>{int(getattr(r, rank_col))}</td><td>{name}</td><td style='text-align:left'>{esc(str(r.province))}</td><td>{num(getattr(r, 'peat_km2', r.area_km2), 0)}</td>"
                    f"<td>{num(r.hs_now_kept, 0)}</td><td>{num(r.u_hotspot_now, 2)}</td><td>{num(100 * r.hs_now_high_share, 0)}%</td><td>{num(r.u_hotspot, 2)}</td>"
                    f"<td>{int(r.peringkat)}</td><td>{CONF_LABEL.get(r.confidence, '')}</td></tr>")
        sec.append(f"""<section id="now"><h2>This year's fire</h2>
<p class="lede">The KLH-curated hotspots of {NOW['period']} (MODIS, medium and high confidence), counted on peat per km2 of peat. They carry their own weight in the score ({'weight ' + format(wn, 'g') if wn is not None else 'see the config'}; setting it to 0 drops them) and give a ranking of their own, below. The historical hotspots (VIIRS 2015-2025) are unchanged.</p>
<div class="card"><h3 style="margin-top:0">Top 15 by hotspot density this year</h3><div class="tablewrap"><table class="data l2"><thead><tr><th>Rank this year (density)</th><th>KHG</th><th>Province</th><th>Peat km2</th><th>Hotspots</th><th>per km2 of peat</th><th>High conf.</th><th>Historical /km2/yr</th><th>Overall rank</th><th>Data conf.</th></tr></thead><tbody>
{''.join(nrow(r) for r in nt.itertuples())}</tbody></table></div></div>
<div class="card" style="margin-top:14px"><h3 style="margin-top:0">Top 15 by number of hotspots</h3><p style="color:var(--muted);font-size:13px;margin:0 0 6px">Density favours KHG with little peat; the count favours large ones. Which one answers "most severe this year" depends on whether the question is about intensity or about total burden.</p><div class="tablewrap"><table class="data l2"><thead><tr><th>Rank this year (count)</th><th>KHG</th><th>Province</th><th>Peat km2</th><th>Hotspots</th><th>per km2 of peat</th><th>High conf.</th><th>Historical /km2/yr</th><th>Overall rank</th><th>Data conf.</th></tr></thead><tbody>
{''.join(nrow(r, "peringkat_now_n") for r in nt2.itertuples())}</tbody></table></div></div>
<div class="grid2" style="margin-top:14px"><div class="card"><div class="chart" id="scatter_now"></div></div>
<div class="card">
<div class="note"><b>Different sensor.</b> The 2026 file is MODIS (1 km); the history is VIIRS (375 m). Counts are not comparable between the two, so they enter as separate indicators, and the chart shows rates, not a trend.</div>
<div class="note"><b>Two schemas in one file.</b> January, April, August and September carry a numeric confidence, a class (Rendah, Sedang, Tinggi), FRP and date; February, March, May, June and July have only Low, Medium or High and no FRP or date. Confidence is harmonised across all nine months; FRP covers four of nine, so it is not scored or summed.</div>
<div class="note"><b>Year to date.</b> The record ends {NOW['period'].split(' to ')[-1]}; the usual peak of the dry season may still be to come.</div></div></div></section>""")

    # ranking table
    sec.append(f"""<section id="ranking"><h2>Full ranking</h2><p class="lede">All {len(ranked)} ranked KHG. Type to filter by name, province or code; click a header to sort.</p>
<div class="controls"><label>Filter <input id="rkfilter" type="search" placeholder="e.g. Kalimantan Tengah, Sebangau, KHG.62"></label><label>Class <select id="rkclass"><option value="">All</option><option>High</option><option>Medium</option><option>Low</option></select></label><span id="rkcount" style="color:var(--muted)"></span></div>
<div class="card tablewrap"><table class="data srt rk" id="rktable"><thead><tr><th>#</th><th>KHG</th><th>Province</th><th>km2</th><th>Peat km2</th><th>Burned %/yr</th><th>Repeat %</th><th>Hotspots /km2/yr</th><th>Hotspots this year /km2</th><th>Canals km/km2</th><th>Score</th><th>Class</th><th>Conf.</th><th>Rank on KHG area</th><th>Rank this year</th></tr></thead><tbody></tbody></table></div>
<p style="margin-top:6px"><button type="button" id="rkmore">Show more</button></p></section>""")

    # method
    w = rep["weights"]
    wrows = "".join(f"<tr><td>{esc(lab)}</td><td style='text-align:left'>{esc(unit_text(unit))}</td><td style='text-align:left'>{esc(src)}</td><td style='text-align:left'>{esc(dirn)}</td><td>{w.get(code, 0):g}</td></tr>" for code, lab, unit, nd, src, dirn in INDICATORS)
    sec.append(f"""<section id="method"><h2>Method</h2>
<p class="lede">One row per KHG, from vector layers clipped to each boundary in an equal-area projection. Scoring is the shared engine of <code>repeat-prioritisation</code> (<code>common.scoring</code>).</p>
<div class="grid2"><div class="card"><h3 style="margin-top:0">Indicators and weights</h3><div class="tablewrap"><table class="data l3"><thead><tr><th>Indicator</th><th>Unit</th><th>Source</th><th>Reading</th><th>Weight</th></tr></thead><tbody>{wrows}</tbody></table></div>
<p style="color:var(--muted);font-size:13px">Weights are provisional and set in the config. Hotspots this year have their own weight (and a standalone rank). Fire radiative power, peat depth and the SiTMAT water table are computed and shown but not scored (see Limits).</p></div>
<div class="card"><h3 style="margin-top:0">Steps</h3><ol style="margin:0;padding-left:18px;color:var(--muted)">
<li><b>Registry.</b> The official table of SK.129/MENLHK/2017 (865 KHG, code, province, kabupaten, area) is parsed from the PDF and joined to the boundary file by name; areas agree to a median 0.003%.</li>
<li><b>Peat.</b> {'The GFW composite peat extent (Miettinen et al. 2016 and Gumbricht et al. 2017 for Indonesia, 76 m here) gives each KHG its peat area. Fire is counted on peat only, and rates are divided by peat area.' if BASIS['v'] == 'peat' else 'Peat extent was not used; rates are per km2 of KHG.'}</li>
<li><b>Fire history.</b> Burnt-area polygons carry the years they burned. Per KHG: burned area per year, and the area burned once, twice, three times in {nb[0]}-{nb[1]}{' (a patch counts as peat if its representative point is on a peat cell)' if BASIS['v'] == 'peat' else ''}.</li>
<li><b>Hotspots.</b> FIRMS VIIRS S-NPP detections, vegetation-fire type only, low confidence dropped (nominal and high kept); counted per KHG and year, with fire radiative power{' (only detections on peat count)' if BASIS['v'] == 'peat' else ''}.</li>
<li><b>Drainage.</b> Canal length per km2; existing hydrological structures and target villages counted.</li>
<li><b>Score.</b> Each indicator is scaled 0 to 1 between the 5th and 95th percentile of all KHG, weighted and averaged. Where an indicator is missing the others are re-weighted. Classes are tertiles of the rank; KHG with no fire signal are always Low.</li>
<li><b>Checks.</b> 300 random weight draws give the share of draws in which each KHG stays in the High class; a held-out test scores on the baseline and compares to later years.</li></ol></div></div></section>""")

    # validation
    def vblock(tgt, label):
        b = (vrep or {}).get("validation", {}).get(tgt)
        if not b:
            return ""
        r_, f_ = b["skor_risiko"], b["hanya_riwayat_kebakaran"]
        cap = [k for k in r_ if k.startswith("capture")][0]
        return (f"<tr><td style='text-align:left'>{label}</td><td>{b['positive_units']} of {b['n_units']}</td><td>{r_['auc']:.2f}</td><td>{f_['auc']:.2f}</td>"
                f"<td>{100 * r_[cap]:.0f}%</td><td>{100 * f_[cap]:.0f}%</td><td>{100 * b['random_capture_expected']:.0f}%</td></tr>")
    vy = cfg["years"]["validation"]
    vs = []
    for tgt, lab in (("v_burned_frac", "later burned area"), ("v_hotspot", "later hotspots")):
        b = (vrep or {}).get("validation", {}).get(tgt)
        if b:
            a1, a2 = b["skor_risiko"]["auc"], b["hanya_riwayat_kebakaran"]["auc"]
            verdict = ("higher than" if a1 - a2 > 0.02 else "lower than" if a1 - a2 < -0.02 else "about the same as")
            vs.append(f"For {lab} the score has AUC {a1:.2f}, {verdict} the {a2:.2f} of fire history alone"
                      f"{' (so it adds little beyond where it burned before)' if verdict == 'about the same as' else ''}.")
    vsentence = " ".join(vs)
    ilabel = {c: l for c, l, *_ in INDICATORS}
    sec.append(f"""<section id="validation"><h2>Validation and robustness</h2>
<p class="lede">The baseline score ({cfg['years']['baseline'][0]}-{cfg['years']['baseline'][1]}) is tested against what happened in {vy[0]}-{vy[1]}, a period it never saw. The test is run in <code>--mode validate</code>; the ranking above uses the baseline extended to {vy[1]}.</p>
<div class="card tablewrap"><table class="data"><thead><tr><th>Later fire measured as</th><th>KHG above threshold</th><th>AUC: score</th><th>AUC: fire history only</th><th>Top 20% captures: score</th><th>: fire history only</th><th>: random</th></tr></thead><tbody>
{vblock('v_burned_frac', f'Burned area share {vy[0]}-{vy[1]} (at least 5%)')}{vblock('v_hotspot', f'Any hotspot {vy[0]}-{vy[1]}')}</tbody></table></div>
<div class="note"><b>How to read it.</b> AUC 0.5 is chance, 1.0 is perfect. {vsentence} The test shows the ranking is consistent over time, not that rewetting will pay off.</div>
<div class="note"><b>Stability.</b> {100 * (rep.get('sensitivity') or {}).get('share_units_stable_class', float('nan')):.0f}% of ranked KHG stay in the same class (High or not) in at least 80% of 300 weight draws; the typical rank moves by about {(rep.get('sensitivity') or {}).get('median_rank_sd', float('nan')):.0f} places (standard deviation).
Indicators that move together (double counting): {', '.join(f"{ilabel.get(p['a'], p['a'])} and {ilabel.get(p['b'], p['b'])} (rho {p['spearman']:.2f})" for p in rep.get('correlated_pairs', [])) or 'none above the threshold'}.</div>
<div class="chart card" id="scatter"></div></section>""")

    # profiles
    prof_html, prof_data = [], []
    for i, r in top.reset_index(drop=True).iterrows():
        row = prof_by.loc[r.khg_id].copy()
        row["khg_id"] = r.khg_id
        lay = layers_for(cfg, type("R", (), {"geom": row.geom, "area_km2": row.area_km2})(), nb)
        yr = yearly[yearly.khg_id == r.khg_id]
        pe = BASIS["v"] == "peat" and pd.notna(row.get("peat_km2"))
        den = float(row.peat_km2) if pe else float(row.area_km2)
        burned = yr[yr.metric == ("burned_peat_km2" if pe else "burned_km2")].set_index("year").value.to_dict()
        hs = yr[yr.metric == ("n_hotspot_peat" if pe else "n_hotspot")].set_index("year").value.to_dict()
        def series(metric, nd=1):
            if s3y is None:
                return []
            t = s3y[(s3y.khg_id == r.khg_id) & (s3y.metric == metric)].sort_values("year")
            return [[int(y), round(float(v), nd)] for y, v in zip(t.year, t.value)]
        LC = [("lc_tree", "Tree cover"), ("lc_shrub", "Shrubland"), ("lc_grass", "Grassland"), ("lc_crop", "Cropland"), ("lc_built", "Built-up"),
              ("lc_water", "Open water"), ("lc_wetland", "Herbaceous wetland"), ("lc_mangrove", "Mangrove"), ("lc_other", "Other")]
        pk = "hs_now_peat_m" if BASIS["v"] == "peat" else "hs_now_all_m"
        nowm = [[m, int(yr[yr.metric == f"{pk}{m:02d}"].value.sum()), int(yr[yr.metric == f"hs_now_all_m{m:02d}"].value.sum())] for m in NOW["months"]]
        peak = MONTH[max(nowm, key=lambda t: t[1])[0] - 1] if nowm and max(t[1] for t in nowm) > 0 else None
        s3 = {"deficit": series("deficit_mm", 0), "rain_dry": series("rain_dry_season_mm", 0),
              "lc": [[lab, round(100 * float(row[k]), 1)] for k, lab in LC if k in row and pd.notna(row[k])]}
        has_s3 = bool(s3["deficit"] or s3["lc"])
        prof_data.append({"now_m": nowm, "s3": s3 if has_s3 else None, "lay": lay, "burned": [[y, round(100 * burned.get(y, 0) / den, 3)] for y in range(2015, 2027)], "unit": "peat" if pe else "KHG",
                          "hs": [[y, int(hs.get(y, 0))] for y in range(2012, 2026)], "area": den,
                          "ind": indicator_rows(row, ranked), "nb": nb})
        badge = {"tinggi": "good", "sedang": "warn", "rendah": "bad"}[row.confidence]
        inds = "".join(f"<tr><td>{esc(x['label'])}<br><span style='color:var(--faint);font-size:11.5px'>{esc(x['unit'])}</span></td><td>{'n/a' if x['v'] is None else num(x['v'], 2)}</td><td>{num(x['med'], 2)}</td>"
                       f"<td>{'' if x['p'] is None else f'<span class=pbar><i style=width:{x['p']:.0f}%></i></span>{x['p']:.0f}'}</td></tr>" for x in prof_data[-1]["ind"])
        kv = "".join(f"<div>{esc(k)}</div><div>{esc(str(v))}</div>" for k, v in kv_info(row))
        prof_html.append(f"""<section class="card prof" id="p-{i}" data-i="{i}"><h3>{int(r.peringkat)}. {esc(r.nama)}</h3>
<div class="meta"><span class="badge good">{CLASS_LABEL.get(r.kelas, r.kelas)} priority</span><span class="badge {badge}">data confidence: {CONF_LABEL[row.confidence]}</span><span class="badge">{esc(str(row.province))}</span></div>
<p class="txt">{narrative(row, ranked, nyears, peak)}</p>
<div class="maps"><div><div class="mapbox"><canvas class="map" id="m{i}"></canvas><div class="legend" id="l{i}"></div></div>
<div class="layers" id="t{i}"></div></div>
<div><table class="ind"><thead><tr><th>Indicator</th><th>This KHG</th><th>Median</th><th>Percentile</th></tr></thead><tbody>{inds}</tbody></table>
<div class="kv" style="margin-top:12px">{kv}</div></div></div>
<div class="grid2" style="margin-top:12px"><div class="chart" id="cb{i}"></div><div class="chart" id="ch{i}"></div></div>
<div class="grid2" style="margin-top:12px"><div class="chart" id="cm{i}"></div><div class="chart" id="cd{i}"></div></div>
{f'<div class="grid2" style="margin-top:12px"><div class="chart" id="cr{i}"></div><div class="chart" id="cl{i}"></div></div>' if has_s3 else ''}</section>""")
    s3table = ""
    if s3p is not None:
        def cell(v, nd=0, mult=1):
            return "n/a" if v is None or (isinstance(v, float) and not np.isfinite(v)) else f"{v * mult:,.{nd}f}"
        rows3 = "".join(f"<tr><td>{int(r.peringkat)}</td><td><a href='#p-{i}'>{esc(r.nama)}</a></td><td>{cell(prof_by.loc[r.khg_id].get('peat_km2'))}</td>"
                        f"<td>{cell(prof_by.loc[r.khg_id].get('deficit_mean_mm'))}</td><td>{cell(prof_by.loc[r.khg_id].get('rain_dry_mean_mm'))}</td>"
                        f"<td>{cell(prof_by.loc[r.khg_id].get('lc_tree'), 0, 100)}</td>"
                        f"<td>{cell(prof_by.loc[r.khg_id].get('lc_crop'), 0, 100)}</td><td>{cell(prof_by.loc[r.khg_id].get('water_perm_frac'), 1, 100)}</td>"
                        f"<td>{cell(prof_by.loc[r.khg_id].get('tma_deep_share'), 0, 100)}</td></tr>" for i, r in top.reset_index(drop=True).iterrows())
        s3table = f"""<h3 style="margin-top:18px">Climate, land cover and water table side by side</h3>
<div class="card tablewrap"><table class="data l2"><thead><tr><th>#</th><th>KHG</th><th>Peat km2</th><th>Dry-season deficit mm (TC 2015-21)</th><th>Jun-Oct rain mm (TC)</th><th>Tree %</th><th>Crop %</th><th>Permanent water %</th><th>Days deeper than 0.4 m % (SiTMAT)</th></tr></thead><tbody>{rows3}</tbody></table></div>
<p style="color:var(--muted);font-size:13px;margin-top:6px">TC = TerraClimate (4 km), so it separates regions rather than neighbouring KHG. Land cover is ESA WorldCover sampled at 250 m. Permanent water is the share of cells with open water in 10 or more months a year, from the JRC Global Surface Water dataset (European Commission Joint Research Centre, Landsat-based). None of these is in the score.</p>"""
    sec.append(f"""<section id="profiles"><h2>Profiles of the top {top_n} KHG</h2><p class="lede">Each profile repeats the same measures so the KHG can be read side by side. Maps show burn counts, hotspot density, canals, rivers and existing structures from the project data; toggle the layers under each map.</p>
<div class="card"><div class="toc">{''.join(f'<a href="#p-{i}">{int(r.peringkat)}. {esc(r.nama)}</a>' for i, r in top.reset_index(drop=True).iterrows())}</div></div>
{s3table}</section>{''.join(prof_html)}""")

    # data and limits
    cat = pd.read_csv(Path(P.os.environ.get("REPEAT_HUB", ROOT.parent / "re-peat")) / "sites" / "data_catalog.csv", dtype=str).fillna("")
    used = [Path(v).name for v in cfg["inputs"].values()] + [Path(cfg["peat"][k]).name for k in ("extent", "global") if cfg["peat"].get(k)]
    cat = cat[cat.path.isin(used) | cat.kind.isin(["cloud", "external"])]
    crow = "".join(f"<tr><td style='text-align:left'>{esc(r.path)}</td><td style='text-align:left'>{esc(r.description)}</td><td>{esc(r.features)}</td><td style='text-align:left'>{esc(r.year)}</td><td style='text-align:left;white-space:normal;max-width:460px'>{esc(r.remarks)}</td></tr>" for r in cat.itertuples())
    n_nocanal = int(prof.canal_segments.eq(0).sum())
    gpm_text = "n/a"
    if "peat_frac_gpm1km" in prof and "island" in prof:
        gg = prof.dropna(subset=["peat_frac", "peat_frac_gpm1km"]).groupby("island")
        gpm_text = "; ".join(f"{k.replace('PULAU ', '').title()}: GFW {100 * g_.peat_frac.median():.0f}% against {100 * g_.peat_frac_gpm1km.median():.0f}% ({len(g_)} KHG)" for k, g_ in gg)
    sec.append(f"""<section id="limits"><h2>Data and limits</h2>
<div class="card tablewrap"><table class="data l2"><thead><tr><th>File</th><th>What it is</th><th>Features</th><th>Year</th><th>Remarks</th></tr></thead><tbody>{crow}</tbody></table></div>
{'<div class="note"><b>Peat extent.</b> The GFW layer combines five published datasets. For Indonesia it is the union of Miettinen et al. 2016 and Gumbricht et al. 2017 (GFW\'s own description), taken here from its public tile cache at about 76 m, so the peat area can be larger than either source alone gives. The Miettinen paper covers Peninsular Malaysia, Sumatra and Borneo (its title), so in Papua the layer rests on Gumbricht et al. 2017, a modelled map. Cells with partial transparency at peat edges count as peat; counting only fully opaque cells would lower peat area by about 6% (24 tiles sampled). Cross-check with the 1 km Global Peatland Map (non-commercial licence), median peat share per island: ' + gpm_text + '. &quot;On peat&quot; is a point sample: a burned patch by its representative point, a hotspot by the peat cell under it (a MODIS pixel is far larger than a 76 m cell). The BBSDLP 1:50,000 depth map covers only ' + str(int(prof.peat_cover_frac.notna().sum())) + ' KHG, so depth is reported, not scored.</div>' if BASIS['v'] == 'peat' else '<div class="note bad"><b>Peat extent is not used.</b> Rates are per km2 of KHG.</div>'}
<div class="note"><b>Canals.</b> {n_nocanal} KHG have no canal in the OSM-derived layer. That means not mapped; canal density is left missing, and the other indicators carry the score.</div>
<div class="note"><b>Hotspots.</b> One satellite (VIIRS S-NPP, two overpasses a day) counts detections, not fires; clouds and overpass timing hide some. Low-confidence detections and non-vegetation types are excluded. 2026 is not in the archive.</div>
<div class="note"><b>This year's hotspots.</b> MODIS, 1 km, curated by KLH, to {NOW['period'].split(' to ')[-1]}; two attribute schemas in one file (confidence harmonised, FRP in four of nine months only). Medium and high confidence are kept. The current-year term is left out of the held-out validation, because it comes after the validation years.</div>
<div class="note"><b>Water table.</b> SiTMAT covers one season (2026) and 164 KHG; it is shown on profiles and not scored.</div>
<div class="note"><b>Shown for the top {top_n}, not scored:</b> climate water deficit and rain (TerraClimate 2015-2021, 4 km), land cover (WorldCover sampled at 250 m), surface water. NDMI, concessions, tidal influence, burn severity (dNBR) and feasibility are not in the report yet.</div>
<h3>Reproduce</h3><div class="card"><code>python -m repeat_common.fetch_firms</code>, <code>python -m repeat_common.fetch_peat_extent</code>, <code>python tools/catalog_data.py</code>, <code>python tools/parse_kepmen_khg.py</code><br>
<code>python -m national.profile --config configs/examples/national_profile.yaml --mode validate</code> and <code>--mode operational</code><br>
<code>python -m national.stage3 select|dryspells|summarize</code> and <code>python -m national.run --config configs/examples/national_stage3.yaml --fetch-only</code> (Stage 3)<br>
<code>python -m national.report --config configs/examples/national_profile.yaml --top {top_n}</code></div></section>""")

    nav = [("summary", "Summary"), ("map", "Map"), ("selected", "Selected KHG"), ("now", "This year"), ("ranking", "Ranking"), ("method", "Method"),
           ("validation", "Validation"), ("profiles", "Profiles"), ("limits", "Limits")]

    # ---------------------------------------------------------------- script
    table_rows = [[int(r.peringkat), r.nama, str(r.province), round(r.area_km2), None if pd.isna(getattr(r, "peat_km2", np.nan)) else round(r.peat_km2),
                   round(100 * r.u_fire_freq, 2), round(100 * r.u_burn_repeat, 2),
                   round(r.u_hotspot, 2), None if pd.isna(getattr(r, "u_hotspot_now", np.nan)) else round(r.u_hotspot_now, 2),
                   None if pd.isna(r.u_canal_density) else round(r.u_canal_density, 2), round(r.skor_risiko, 3),
                   CLASS_LABEL.get(r.kelas, r.kelas), CONF_LABEL.get(r.confidence, ""), r.khg_id,
                   None if pd.isna(getattr(r, "peringkat_area", np.nan)) else int(r.peringkat_area),
                   None if pd.isna(getattr(r, "peringkat_now", np.nan)) else int(r.peringkat_now)] for r in ranked.itertuples()]
    sc_pts = [{"x": round(100 * r.u_fire_freq, 3), "y": round(r.u_hotspot, 3), "sel": bool(r.khg_id in sel_ids), "tip": f"<b>{esc(r.nama)}</b><br>rank {int(r.peringkat)}"}
              for r in ranked.itertuples()]
    sc_now = [{"x": round(float(r.u_hotspot), 3), "y": round(float(r.u_hotspot_now), 3), "sel": bool(r.khg_id in sel_ids),
               "tip": f"<b>{esc(r.nama)}</b><br>overall rank {int(r.peringkat)} - this year {int(r.peringkat_now)}"}
              for r in ranked.itertuples() if pd.notna(getattr(r, "u_hotspot_now", np.nan))]
    script = SCRIPT
    html_out = H.page("National KHG profile and ranking", lede, facts, nav, "".join(sec),
                      {"nat": nat, "bounds": bounds, "rows": table_rows, "prof": prof_data, "sc": sc_pts, "sc_now": sc_now, "top_n": top_n, "basis": BASIS["v"]},
                      script, footer=f"Generated {date.today().isoformat()} from {esc(str(cfg['data']))}; baseline {nb[0]}-{nb[1]}. Weights are provisional.",
                      extra_css=SECTION_CSS)
    Path(out_path).write_text(html_out, encoding="utf-8")
    print(f"{out_path}: {len(html_out) / 1e6:.1f} MB, {len(ranked)} ranked, {top_n} profiles")


SCRIPT = r"""
// ---- national map
const natCanvas=$('#natmap');const nat=new MapView(natCanvas,DATA.bounds);
const natLayer=nat.addLayer({type:'poly',items:DATA.nat,selectable:true,pickable:true,style:(it)=>{
  const v=it.p[natVar];const base=document.documentElement;
  const st={lw:it.p.sel?2.4:.5,stroke:it.p.sel?css('--orange'):css('--axis')};
  if(v==null||it.p.peringkat==null&&natVar==='skor_risiko'){st.fill=css('--grid');return st}
  st.fill=ramp((v-natLo)/(natHi-natLo||1));return st}});
let natVar='skor_risiko',natLo=0,natHi=1;
const natLabels={skor_risiko:['Priority score',x=>fmt(x,2)],u_fire_freq:['Burned % of area per year',x=>fmt(x,1)],u_hotspot:['Hotspots per km2 per year',x=>fmt(x,2)],u_canal_density:['Canal km per km2',x=>fmt(x,1)],peat_km2:['Peat area, km2',x=>fmt(x,0)],u_hotspot_now:['Hotspots this year per km2 (KLH)',x=>fmt(x,2)]};
function natRange(){const vs=DATA.nat.map(i=>i.p[natVar]).filter(v=>v!=null&&isFinite(v)).sort((a,b)=>a-b);natLo=vs[Math.floor(vs.length*.05)];natHi=vs[Math.floor(vs.length*.95)];
  const [t,f]=natLabels[natVar];legendCont($('#natleg'),t+' (grey: no value)',natLo,natHi,f)}
function natUpdate(){natVar=$('#mapvar').value;natRange();nat.draw()}
$('#mapvar').onchange=natUpdate;natRange();
nat.onhover=h=>{const p=h.item.p;return '<b>'+esc(p.nama)+'</b><br><span>'+esc(p.province||'')+'</span><br>'+(p.peringkat!=null?'rank '+p.peringkat+' · '+p.kelas:'not ranked')};
nat.onclick=h=>{const el=$('#natside');if(!h){el.innerHTML='<h3>Selected KHG</h3><p style="color:var(--muted)">Click a KHG on the map.</p>';return}
  const p=h.item.p,ix=DATA.nat.indexOf(h.item);let rows=[['Code',p.khg_id],['Province',p.province],['Area (km2)',fmt(p.area_km2,0)],['Rank',p.peringkat!=null?p.peringkat:'not ranked'],['Class',p.kelas||''],['Score',fmt(p.skor_risiko,2)],
   ['Burned % per year',fmt(p.u_fire_freq,2)],['Hotspots /km2/yr',fmt(p.u_hotspot,2)],['Canals km/km2',fmt(p.u_canal_density,2)],['Peat area (km2)',fmt(p.peat_km2,0)],['Hotspots this year /km2',fmt(p.u_hotspot_now,2)],['Data confidence',p.confidence||'']];
  el.innerHTML='<h3>'+esc(p.nama)+'</h3><table>'+rows.map(r=>'<tr><td>'+r[0]+'</td><td>'+esc(String(r[1]))+'</td></tr>').join('')+'</table>'+(p.top?'<p><a href="#p-'+DATA.rows.findIndex(r=>r[13]===p.khg_id)+'">Open profile</a></p>':'')};
window.addEventListener('themechange',()=>{natRange();nat.draw()});
// ---- ranking table
let rkShown=60;
function rkRender(){const q=$('#rkfilter').value.toLowerCase(),c=$('#rkclass').value;let rows=DATA.rows.filter(r=>(!c||r[11]===c)&&(!q||(r[1]+' '+r[2]+' '+r[13]).toLowerCase().includes(q)));
  if(rkSort.k!=null)rows=rows.slice().sort((a,b)=>{const x=a[rkSort.k],y=b[rkSort.k];return (x==null)-(y==null)||(typeof x==='string'?x.localeCompare(y):x-y)*rkSort.d});
  $('#rkcount').textContent=rows.length+' KHG';$('#rkmore').style.display=rows.length>rkShown?'':'none';
  $('#rktable tbody').innerHTML=rows.slice(0,rkShown).map(r=>'<tr><td>'+r[0]+'</td><td style="text-align:left">'+esc(r[1])+'</td><td style="text-align:left">'+esc(r[2])+'</td><td>'+fmt(r[3],0)+'</td><td>'+fmt(r[4],0)+'</td><td>'+fmt(r[5],2)+'</td><td>'+fmt(r[6],2)+'</td><td>'+fmt(r[7],2)+'</td><td>'+fmt(r[8],2)+'</td><td>'+fmt(r[9],2)+'</td><td>'+fmt(r[10],2)+'</td><td>'+r[11]+'</td><td>'+r[12]+'</td><td>'+(r[14]==null?'n/a':r[14])+'</td><td>'+(r[15]==null?'n/a':r[15])+'</td></tr>').join('')}
let rkSort={k:null,d:1};
$$('#rktable th').forEach((th,i)=>th.onclick=()=>{rkSort={k:i,d:rkSort.k===i?-rkSort.d:1};rkRender()});
$('#rkfilter').oninput=()=>{rkShown=60;rkRender()};$('#rkclass').onchange=()=>{rkShown=60;rkRender()};$('#rkmore').onclick=()=>{rkShown+=200;rkRender()};rkRender();
// ---- scatter: burned share against hotspot density
(function(){const pts=DATA.sc.map(p=>({x:Math.min(p.x,20),y:Math.min(p.y,4),tip:p.tip+'<br>burned '+fmt(p.x,1)+'% per year · '+fmt(p.y,2)+' hotspots /km2/yr',fill:p.sel?'var(--orange)':'var(--blue)'}));
  chartScatter($('#scatter'),pts,{title:'One dot per ranked KHG; orange = team main KHG (axes clipped at 20% and 4)',xl:'Mean burned share per year, % of '+(DATA.basis==='peat'?'peat':'KHG')+' area',yl:'Hotspots per '+(DATA.basis==='peat'?'peat ':'')+'km2 per year',w:760,h:380,r:4})})();
// ---- scatter: history against this year
(function(){const el=$('#scatter_now');if(!el)return;const xs=DATA.sc_now.map(p=>p.x).sort((a,b)=>a-b),ys=DATA.sc_now.map(p=>p.y).sort((a,b)=>a-b);
  const cx=Math.max(.5,xs[Math.floor(xs.length*.99)]),cy=Math.max(.5,ys[Math.floor(ys.length*.99)]);
  const pts=DATA.sc_now.map(p=>({x:Math.min(p.x,cx),y:Math.min(p.y,cy),tip:p.tip+'<br>history '+fmt(p.x,2)+' - this year '+fmt(p.y,2)+' per km2 of peat',fill:p.sel?'var(--orange)':'var(--blue)'}));
  chartScatter(el,pts,{title:'History against this year, per km2 of peat (orange: team main KHG)',xl:'Historical hotspots, VIIRS, per km2 of peat per year (clipped at 99th pct)',yl:'Hotspots this year, KLH, per km2 of peat (year to date)',w:560,h:380,r:4})})();
// ---- columns chart
function chartCols(el,rows,o){const W=o.w||520,H=o.h||230,m={l:44,r:10,t:30,b:30};const hi=Math.max(o.min||0,...rows.map(r=>r.v));const Y=v=>H-m.b-v/(hi||1)*(H-m.t-m.b);
  const bw=Math.min(24,(W-m.l-m.r)/rows.length-2),X=i=>m.l+(i+.5)*(W-m.l-m.r)/rows.length;let s='<text class="ttl" x="6" y="16">'+esc(o.title)+'</text>';
  niceTicks(0,hi,4).forEach(v=>{s+='<line class="gr" x1="'+m.l+'" x2="'+(W-m.r)+'" y1="'+Y(v)+'" y2="'+Y(v)+'"/><text x="'+(m.l-6)+'" y="'+(Y(v)+4)+'" text-anchor="end">'+fmt(v,hi<10?1:0)+'</text>'});
  rows.forEach((r,i)=>{const x=X(i)-bw/2,y=Y(r.v),h=Math.max(0,H-m.b-y);
    s+='<path d="M'+x+' '+(H-m.b)+'V'+(y+4)+'a4 4 0 0 1 4 -4h'+(bw-8)+'a4 4 0 0 1 4 4V'+(H-m.b)+'Z" fill="'+(r.part?'var(--axis)':'var(--blue)')+'" data-tip="'+esc(r.tip)+'"/>';
    if(o.all||i%2===0||rows.length<9)s+='<text x="'+X(i)+'" y="'+(H-m.b+14)+'" text-anchor="middle">'+r.l+'</text>'});
  s+='<line class="ax" x1="'+m.l+'" x2="'+(W-m.r)+'" y1="'+(H-m.b)+'" y2="'+(H-m.b)+'"/>';el.innerHTML=SV(W,H,s)}
// ---- one profile
function initProfile(i){const d=DATA.prof[i],L=d.lay,cv=$('#m'+i);const mv=new MapView(cv,[L.bounds[0],L.bounds[1],L.bounds[2],L.bounds[3]]);
  const burnCol=n=>ramp(.2+.8*(n-1)/3);
  const ls={};
  mv.addLayer({type:'poly',items:[{polys:L.outline,p:{}}],style:()=>({fill:null,stroke:css('--fg'),lw:1.6})});
  ls.burn=mv.addLayer({type:'poly',items:L.burn,style:it=>({fill:burnCol(it.p.n),stroke:'transparent',lw:0}),pickable:true});
  ls.rivers=mv.addLayer({type:'line',items:L.rivers,style:()=>({lw:1,stroke:css('--aqua'),dash:[]})});
  ls.canals=mv.addLayer({type:'line',items:L.canals,style:()=>({lw:.7,stroke:css('--faint')})});
  const hmax=Math.max(1,...L.hot.map(h=>h.n));
  ls.hot=mv.addLayer({type:'point',items:L.hot,pickable:true,style:it=>({r:1.6+2.6*Math.sqrt(it.n/hmax),fill:rampO(.3+.7*it.n/hmax),ring:.5})});
  ls.infra=mv.addLayer({type:'point',items:L.infra,style:()=>({r:2.2,fill:css('--fg'),ring:1})});
  // this year's hotspots as points: filled = on peat, hollow = off peat; larger = high confidence
  ls.now=mv.addLayer({type:'point',items:L.now,pickable:true,style:it=>({r:it.h?3.6:2.5,fill:it.p?css('--bad'):'transparent',stroke:it.p?css('--surface'):css('--bad'),ring:it.p?.8:1.4})});
  const MONTHS=['January','February','March','April','May','June','July','August','September','October','November','December'];
  mv.onhover=h=>h.layer===ls.hot?'<b>'+h.item.n+' hotspots</b><br><span>in a '+L.hot_cell_km+' km cell, baseline</span>':h.layer===ls.burn?'<b>burned '+h.item.p.n+(h.item.p.n>=4?'+':'')+' time(s)</b>':h.layer===ls.now?'<b>Hotspot, '+MONTHS[h.item.m-1]+'</b><br><span>'+(h.item.h?'high':'medium')+' confidence, '+(h.item.p?'on peat':'off peat')+'</span>':null;
  const names=[['burn','Burn count',true],['now','Hotspots this year ('+L.now_n+')',true],['hot','Hotspot cells, baseline',false],['canals','Canals',true],['rivers','Rivers',false],['infra','Existing structures ('+L.infra_n+')',false]];
  $('#t'+i).innerHTML=names.map(n=>'<label><input type="checkbox" data-k="'+n[0]+'" '+(n[2]?'checked':'')+'>'+n[1]+'</label>').join('');
  names.forEach(n=>ls[n[0]].visible=n[2]);
  $$('#t'+i+' input').forEach(c=>c.onchange=()=>{ls[c.dataset.k].visible=c.checked;mv.draw()});
  const leg=()=>legendCat($('#l'+i),'Burns '+d.nb[0]+'-'+d.nb[1],[[burnCol(1),'1'],[burnCol(2),'2'],[burnCol(3),'3'],[burnCol(4),'4 or more'],[css('--bad'),'hotspot this year, on peat (large: high conf.)'],['transparent','hotspot this year, off peat'],[rampO(.7),'baseline hotspot cells']]);
  leg();mv.draw();window.addEventListener('themechange',()=>{leg();mv.draw()});
  const a=d.area;
  chartCols($('#cb'+i),d.burned.map(r=>({l:r[0],v:r[1],part:r[0]===2026,tip:'<b>'+r[0]+(r[0]===2026?' (partial year)':'')+'</b><br>'+fmt(r[1],2)+'% of the '+d.unit+' burned ('+fmt(r[1]*a/100,1)+' km2)'})),{title:'Burned area, % of '+d.unit+' per year (grey: 2026, partial)'});
  chartCols($('#cm'+i),d.now_m.map(r=>({l:MONTHS[r[0]-1].slice(0,3),v:r[1],tip:'<b>'+MONTHS[r[0]-1]+'</b><br>'+fmt(r[1],0)+' hotspots on peat ('+fmt(r[2],0)+' in the whole KHG), medium or high confidence'})),{title:'Hotspots this year by month (KLH, on peat)',all:true});
  chartCols($('#ch'+i),d.hs.map(r=>({l:r[0],v:r[1],tip:'<b>'+r[0]+'</b><br>'+fmt(r[1],0)+' hotspots'+(d.unit==='peat'?' on peat':'')+' (vegetation fire, nominal or high confidence)'})),{title:'Hotspots'+(d.unit==='peat'?' on peat':'')+' per year (VIIRS S-NPP)'});
  if(d.s3){const s3=d.s3;
    chartCols($('#cd'+i),s3.deficit.map(r=>({l:r[0],v:r[1],tip:'<b>'+r[0]+'</b><br>dry-season water deficit '+fmt(r[1],0)+' mm'})),{title:'Dry-season water deficit, mm (TerraClimate)'});
    chartCols($('#cr'+i),s3.rain_dry.map(r=>({l:r[0],v:r[1],tip:'<b>'+r[0]+'</b><br>June to October rain '+fmt(r[1],0)+' mm'})),{title:'Rain in the dry months (June-October), mm (TerraClimate)'});
    chartBars($('#cl'+i),s3.lc.filter(r=>r[1]>=0.5).map(r=>({label:r[0],value:r[1],tip:'<b>'+esc(r[0])+'</b><br>'+fmt(r[1],1)+'% of the KHG'})),{title:'Land cover, % of KHG (ESA WorldCover)',w:520,ml:130,lo:0})}}
const seen=new Set();
const io=new IntersectionObserver(es=>es.forEach(e=>{if(e.isIntersecting){const i=+e.target.dataset.i;if(!seen.has(i)){seen.add(i);initProfile(i)}}}),{rootMargin:'400px'});
$$('section.prof').forEach(s=>io.observe(s));
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--mode", choices=["operational", "validate"], default="operational", help="which run's ranking to report")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--out")
    a = ap.parse_args(argv)
    cfg = copy.deepcopy(P.DEFAULTS)
    P._merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    cfg = P._expand(cfg)
    cfg["inputs"].setdefault("rivers", "RBI_sungai.gpkg")
    out = a.out or str(Path(cfg["out"]) / "national_khg_profile.html")
    build(cfg, a.top, a.mode, out)


if __name__ == "__main__":
    main()
