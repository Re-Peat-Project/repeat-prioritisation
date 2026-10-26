#!/usr/bin/env python3
"""Build the HTML page that explains sub-KHG delineation and prioritisation and shows a run's outputs on a map.

  repeat-subkhg-dashboard --subkhg-config ../re-peat/sites/14.02-04-05.01_kampar_gaung/subkhg.yaml \\
      --neraca-dir $REPEAT_KHG/14.02-04-05.01_kampar_gaung/03_neraca --out docs/process/subkhg_process.html

One self-contained file (no server, no internet): the process diagram with the numbers of the run, the delineation funnel,
a map of the sub-KHG coloured by any output or indicator (with canals, rivers, canal blocks and water-table stations as
overlays), and the ranking. Regenerate it after a run with the same command; every number on the page comes from the
output folders of that run.
"""
from __future__ import annotations

import argparse
import datetime
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd

from repeat_common import htmlkit as K
from repeat_prioritisation.common import pipeline
from repeat_prioritisation.subkhg.run import PRESET as SUBKHG_PRESET

CLASSES = ["Kebutuhan intervensi: tinggi", "Kebutuhan intervensi: sedang", "Kebutuhan intervensi: rendah",
           "Pengaruh pasang surut: pantau", "Dikecualikan (pengelolaan lahan)"]

# key, label, group, kind (class | rank | cont)
VARS = [
    ("kelas", "Need class", "Result", "class"),
    ("peringkat", "Final rank (1 = highest need)", "Result", "rank"),
    ("peringkat_need", "Rank by need score", "Result", "rank"),
    ("peringkat_ranksum", "Rank by rank-sum", "Result", "rank"),
    ("skor_need", "Need score (0-1)", "Result", "cont"),
    ("skor_ranksum_need", "Rank-sum score (0-1, high = more need)", "Result", "cont"),
    ("area_km2", "Area (km2)", "Geometry", "cont"),
    ("i_peat_depth", "Peat depth, mean (m)", "Stakes", "cont"),
    ("i_forest", "Tree cover share (WorldCover)", "Land cover", "cont"),
    ("u_ndmi", "NDMI, dry season", "Wetness", "cont"),
    ("u_ndvi", "NDVI, dry season", "Wetness", "cont"),
    ("u_hotspot", "Hotspots per km2 per year", "Fire", "cont"),
    ("u_fire_freq", "Share of years burned", "Fire", "cont"),
    ("u_canal_density", "Canal density (km per km2)", "Drainage", "cont"),
    ("f_reach", "Share within canal reach", "Drainage", "cont"),
    ("n_sekat_ada", "Existing canal blocks", "Drainage", "cont"),
    ("n_sekat_perlu", "Blocks needed by the spacing rule", "Drainage", "cont"),
    ("m_ipg", "IPG: existing / needed blocks", "Drainage", "cont"),
    ("f_water_dist", "Distance to dry-season water (m)", "Feasibility", "cont"),
    ("f_lift", "Height above that water (m)", "Feasibility", "cont"),
    ("u_tma", "Share of days with water table deeper than 0.4 m", "Water table (2026)", "cont"),
    ("n_tma_stations", "SiTMAT stations in the sub-KHG", "Water table (2026)", "cont"),
    ("u_wb_daily_mean", "Neraca air: P - E, mm/day (not usable)", "Neraca air", "cont"),
    ("u_storage_decline_pct", "Neraca air: storage decline % (not usable)", "Neraca air", "cont"),
    ("u_wt_days_gt40", "Neraca air: simulated days > 40 cm (not usable)", "Neraca air", "cont"),
]


def _floor_share(path) -> tuple[float, float] | None:
    """(share of valid pixels at the raster's floor value, the floor value) from a decimated read, as subkhg.check_inputs does."""
    import rasterio
    try:
        with rasterio.open(path) as s:
            step = max(1, int(max(s.height, s.width) / 2500))
            a = s.read(1, out_shape=(1, s.height // step, s.width // step)).astype("float64")
            ok = np.isfinite(a) & (a > -1e30) & (a < 1e30)
            if s.nodata is not None and np.isfinite(s.nodata):
                ok &= a != s.nodata
            v = a[ok]
        floor = float(np.percentile(v, 1))
        return float((np.abs(v - floor) < 0.1).mean()), floor
    except Exception:
        return None


def _n(x):
    return f"{int(x):,}"


def build(subkhg_config: str, neraca_dir: str | None, out: str) -> None:
    sc = pipeline.load_config(subkhg_config, SUBKHG_PRESET, "subkhg")
    od = Path(sc["out"])
    g = gpd.read_file(od / "unit_prioritas.gpkg").to_crs(4326)
    lap = json.load(open(od / "laporan.json", encoding="utf-8"))
    khg = gpd.read_file(sc["khg"]).to_crs(4326)
    kid = str(khg[sc["khg_id_field"]].iloc[0]) if sc["khg_id_field"] in khg.columns else "KHG"
    area_tot = float(g["area_km2"].sum())
    n_units = len(g)

    # ---- variables present in this run
    vars_ = []
    for key, label, group, kind in VARS:
        if key in g.columns and g[key].notna().any() and (kind != "cont" or g[key].nunique() > 1):
            vars_.append({"key": key, "label": label, "group": group, "kind": kind})
    cols = ["unit_id"] + [v["key"] for v in vars_ if v["key"] != "kelas"] + ["kelas", "cakupan_ranksum", "neraca_skill_ok", "balance_stable_ok"]
    cols = [c for c in dict.fromkeys(cols) if c in g.columns]
    units = K.pack_polygons(g, cols)

    # ---- overlays
    geo = {}
    cls_map = {"Kanal Tersier": 3, "Kanal Sekunder": 2, "Kanal Primer": 1}
    canals = gpd.read_file(sc["vectors"]["canals"]).to_crs(4326) if sc["vectors"].get("canals") else None
    f = (sc["units"].get("subkhg") or {}).get("canal_class_field") or sc["params"].get("ipg_canal_class_field")
    n_can = {}
    if canals is not None:
        geo["canals"] = K.pack_lines(canals, f, cls_map)
        if f in canals.columns:
            n_can = canals[f].astype(str).value_counts().to_dict()
    rivers = gpd.read_file(sc["vectors"]["rivers"]).to_crs(4326) if sc["vectors"].get("rivers") else None
    if rivers is not None:
        geo["rivers"] = K.pack_lines(rivers)
    blocks = gpd.read_file(sc["vectors"]["blocks"]).to_crs(4326) if sc["vectors"].get("blocks") else None
    if blocks is not None:
        geo["blocks"] = K.pack_points(blocks)
    geo["khg"] = K._rings(khg.geometry.union_all(), 0.0008)
    stations = []
    n_st = None
    sp = Path(neraca_dir) / "inputs" / "stations.csv" if neraca_dir else None
    if sp is not None and sp.exists():
        s = pd.read_csv(sp)
        peak = pd.read_csv(sp.parent / "stations_daily.csv").groupby("station_id")["depth_cm"].quantile(0.95)   # observed peak depth
        n_st = len(s)
        stations = [{"x": round(r.lon, 4), "y": round(r.lat, 4), "id": r.station_id, "obs": None if pd.isna(peak.get(r.station_id)) else round(peak[r.station_id], 1)}
                    for r in s.itertuples()]
    b = khg.total_bounds
    sweep_path = Path(sc["units"]["path"]).parent / "delineation_sweep.json"
    sweep = json.load(open(sweep_path, encoding="utf-8")) if sweep_path.exists() else None

    # ---- numbers for the diagram
    rep_path = Path(sc["units"]["path"]).parent / "delineation_report.json"
    rep = (json.load(open(rep_path, encoding="utf-8")) or [{}])[0] if rep_path.exists() else {}
    min_area = rep.get("min_area_km2") or 5.0
    merge = rep.get("merge", "adjacent")
    auto = str(rep.get("min_area_setting", "")).lower() == "auto"
    prim = int(n_can.get("Kanal Primer", 0))
    n_riv = len(rivers) if rivers is not None else 0
    n_blk = len(blocks) if blocks is not None else 0
    floor_units = peat_n = None
    fl = _floor_share(sc["rasters"]["peat_depth"]) if (sc.get("rasters") or {}).get("peat_depth") else None
    floor_txt = f"{100 * fl[0]:.0f}% of its valid pixels equal {fl[1]:.0f} cm" if fl and fl[0] > 0.05 else None
    if "i_peat_depth" in g.columns:
        v = g["i_peat_depth"].dropna()
        peat_n = len(v)
        floor_units = int((v < v.min() + 0.02).sum())
    slope_cap = None
    if "kemiringan_kanal" in g.columns and g["kemiringan_kanal"].notna().any():
        sl = g["kemiringan_kanal"].dropna()
        cap = float(sc["params"]["ipg_dA_m"]) / float(sc["params"]["ipg_js_max_m"])
        slope_cap = (int((sl < cap).sum()), len(sl))
    tma_units = int((g["n_tma_stations"] > 0).sum()) if "n_tma_stations" in g.columns else None
    forest_med = float(g["i_forest"].median()) if "i_forest" in g.columns else None
    agree = lap.get("ranking_agreement") or {}
    pairs = lap.get("correlated_pairs", [])
    flag = "balance_stable_ok" if "balance_stable_ok" in g.columns else "neraca_skill_ok"     # repeat_neraca.balance, or the older tables
    skill_ok = int(g[flag].iloc[0]) if flag in g.columns and g[flag].notna().any() else None
    yrs = sc["years"]["baseline"]
    base = f"{yrs[0]}-{yrs[1]}"
    res = sc["sources"]["ndmi"].get("res_m", 20)

    nodes = {
        "in_khg": dict(x=20, y=44, w=205, h=60, title="KHG boundary", lines=["BatasKHG shapefile", f"{area_tot:,.0f} km2"], kind="input"),
        "in_dtm": dict(x=20, y=120, w=205, h=60, title="DTM", lines=["12 m GeoTIFF, metres", "warped to the 30 m grid"], kind="input"),
        "in_vec": dict(x=20, y=196, w=205, h=60, title="Canals and rivers", lines=[f"{_n(len(canals)) if canals is not None else 0} canal + {n_riv} river segments", "canal class: KET_KANAL"], kind="input"),
        "in_loc": dict(x=20, y=300, w=205, h=60, title="Peat depth, canal blocks", lines=["peat raster (cm), 10 m", f"{_n(n_blk)} existing blocks"], kind="input"),
        "in_tma": dict(x=20, y=380, w=205, h=60, title="Water table, neraca air", lines=[f"SiTMAT stations{f' ({n_st} in KHG)' if n_st else ''}", "neraca air table (optional)"], kind="input"),
        "in_cloud": dict(x=20, y=540, w=205, h=64, title="Cloud layers", lines=["Sentinel-2, MODIS burned,", "FIRMS, WorldCover, JRC, TerraClimate"], kind="cloud"),
        "p_delin": dict(x=345, y=106, w=215, h=88, title="1 Delineate sub-KHG", lines=["burn canals, D8 flow, outlets,", "catchments, merge small pieces", f"result: {n_units} sub-KHG"], kind="proc"),
        "p_fetch": dict(x=345, y=520, w=215, h=84, title="2 Fetch cloud layers", lines=["30 m cache per KHG, once", f"Sentinel-2 at {res} m, baseline {base}", "re-runs read the cache"], kind="proc"),
        "p_ind": dict(x=655, y=300, w=215, h=96, title="3 Indicators per sub-KHG", lines=["zonal statistics at 30 m", "urgency, stakes, feasibility", f"means over {base}"], kind="proc"),
        "p_score": dict(x=950, y=176, w=190, h=88, title="4 Score", lines=["need score (0-1)", "rank-sum (8 indicators)", "both always computed"], kind="proc"),
        "p_class": dict(x=950, y=330, w=190, h=88, title="5 Classes and ranks", lines=["tertiles within the KHG", "checks: correlation,", "sensitivity, validation"], kind="proc"),
        "o_units": dict(x=1230, y=60, w=165, h=58, title="Sub-KHG polygons", lines=["subkhg_units.gpkg", ""], kind="out"),
        "o_rank": dict(x=1230, y=168, w=165, h=58, title="Ranked sub-KHG", lines=["unit_prioritas.gpkg", "and .csv"], kind="out"),
        "o_sekat": dict(x=1230, y=258, w=165, h=58, title="Block needs", lines=["kebutuhan_sekat.csv", ""], kind="out"),
        "o_rep": dict(x=1230, y=348, w=165, h=58, title="Checks, maps", lines=["laporan.json, PNG", ""], kind="out"),
        "o_md": dict(x=1230, y=438, w=165, h=58, title="Run report", lines=["sites/<khg>/reports/*.md", "this page"], kind="out"),
    }
    edges = [
        ("in_khg", "p_delin", "clips", {"dyt": -22}),
        ("in_dtm", "p_delin", "flow routing"),
        ("in_vec", "p_delin", "outlets: primary", {"dyt": 22, "ly": 12}),
        ("in_cloud", "p_fetch", "windows"),
        ("p_delin", "p_ind", f"{n_units} polygons", {"dyt": -26, "ly": 4}),
        ("p_fetch", "p_ind", "30 m layers", {"dyt": 26, "ly": 12}),
        ("in_loc", "p_ind", "stakes, IPG", {"dyt": -10}),
        ("in_tma", "p_ind", "water table now", {"dyt": 10}),
        ("p_ind", "p_score", "indicators", {"dyt": -10}),
        ("p_score", "p_class", "scores", {"from": "b", "to": "t"}),
        ("p_delin", "o_units", "boundaries", {"dyf": -28, "dyt": 0, "ly": -8}),
        ("p_class", "o_rank", "ranks", {"dyf": -18}),
        ("p_class", "o_sekat", "blocks", {"dyf": -4}),
        ("p_class", "o_rep", "checks", {"dyf": 12}),
        ("p_class", "o_md", "report", {"dyf": 24}),
    ]
    lanes = [(10, 225, "Inputs"), (330, 245, "Delineate, fetch"), (640, 245, "Indicators"), (935, 220, "Score, rank"), (1215, 185, "Outputs")]
    flow = K.flow_svg(nodes, edges, 1400, 650,
                      f"Inputs flow into delineation and cloud fetching, then into an indicator table per sub-KHG, then into the need score and the rank-sum, and out as ranked sub-KHG, block needs and reports for KHG {kid}",
                      lanes)

    pieces = rep.get("pieces_before_merge") or (sweep or {}).get("pieces")
    dn = {
        "a": dict(x=20, y=60, w=170, h=84, title="KHG + DTM", lines=["12 m DTM, 30 m grid", f"{area_tot:,.0f} km2"], kind="input"),
        "b": dict(x=275, y=60, w=170, h=84, title="Conditioned DTM", lines=["canals cut 3 m deep", f"{_n(len(canals)) if canals is not None else 0} canal segments"], kind="proc"),
        "c": dict(x=530, y=60, w=170, h=84, title="Flow directions", lines=["pits, flats filled", "D8 direction, accumulation"], kind="proc"),
        "d": dict(x=785, y=60, w=170, h=84, title="Catchments", lines=[f"outlets: {prim} primary canal", f"+ {n_riv} river segments", f"{pieces} pieces" if pieces else "one per reach and bank"], kind="proc"),
        "e": dict(x=1040, y=60, w=170, h=84, title=f"{n_units} sub-KHG", lines=[f">= {min_area:g} km2 each", "subkhg_units.gpkg"], kind="out"),
    }
    dedges = [("a", "b", "burn canals"), ("b", "c", "route water"), ("c", "d", "outlets"), ("d", "e", "merge small")]
    funnel = K.flow_svg(dn, dedges, 1230, 200, f"Delineation in five steps from the DTM and canals to {n_units} sub-KHG")

    details = {
        "in_khg": {"title": "KHG boundary", "body": [f"The KHG polygon, cut from the BatasKHG shapefile (EPSG:3395) into <code>khg.gpkg</code> by <code>subkhg.prepare_inputs</code>. {area_tot:,.0f} km2.",
                            "The shapefile's <code>Sub_KHG</code> column has one value for this KHG, so there is no existing sub-KHG layout to compare the delineation with."]},
        "in_dtm": {"title": "DTM", "body": ["12 m GeoTIFF in metres above sea level (EPSG:4326), warped to the 30 m analysis grid with bilinear resampling.",
                                          "Used three times: flow routing in the delineation, the height above the nearest dry-season water (<code>f_lift</code>) and the canal slope for the block spacing (metrik IPG)."]},
        "in_vec": {"title": "Canals and rivers", "body": [f"Canals from the BRGM canal file, classes in <code>KET_KANAL</code>: primary {_n(n_can.get('Kanal Primer', 0))}, secondary {_n(n_can.get('Kanal Sekunder', 0))}, tertiary {_n(n_can.get('Kanal Tersier', 0))} segments (clipped file, KHG plus 2 km). {n_riv} river segments from RBI.",
                                                    "The class decides what is an outlet: only primary canals and rivers are (<code>outlet_canal_classes: [Kanal Primer]</code>). All canals are burned into the DTM and count for canal density and reach."]},
        "in_loc": {"title": "Peat depth and canal blocks", "body": [f"Peat depth: raster in centimetres, converted with <code>peat_depth_scale: 0.01</code>. {floor_txt + ' (a floor); ' if floor_txt else ''}{floor_units} of {peat_n} sub-KHG have a mean at the lowest value." if floor_units is not None else "Peat depth raster.",
                                                               f"Existing canal blocks: {_n(n_blk)} points (BRGM file, <code>Jenis = Sekat Kanal</code>, <code>REALISASI</code>), compared with the blocks the spacing rule asks for."]},
        "in_tma": {"title": "Water table and neraca air", "body": [f"SiTMAT concession stations{f' ({n_st} inside the KHG)' if n_st else ''}: a current-state indicator for 2026-04-01 to 2026-10-15 (the record is one season). {tma_units} of {n_units} sub-KHG contain a station." if tma_units is not None else "SiTMAT stations.",
                                                         "The neraca air table (climatic balance per sub-KHG, repeat_neraca.balance) is merged through <code>extra_indicators</code>: <code>u_wb_mean</code> and <code>u_deficit_months</code> replace the TerraClimate columns; the rank-sum water slot reads <code>p_minus_et_mean_mm</code> (P - ET with KHG-mean rain); the need score gives them no weight. All are left empty where <code>balance_stable_ok</code> is 0 (the ET products disagree on the order of units, or it changes between years)." + (" In this run the flag is 0." if skill_ok == 0 else "")]},
        "in_cloud": {"title": "Cloud layers", "body": [f"Sentinel-2 L2A NDMI and NDVI (dry-season median, {res} m here), MODIS burned area, FIRMS VIIRS hotspots, ESA WorldCover, JRC surface water, TerraClimate.",
                                                        "Read per KHG window from STAC and Zarr, never downloaded whole. ERA5 rainfall is off in this run: its indicators have weight 0."]},
        "p_delin": {"title": "1 Delineate sub-KHG (repeat-delineation repo)", "body": [
            f"Canals and rivers are burned 3 m into the DTM. Pits, depressions and flats are filled; D8 flow direction and accumulation follow (pysheds).",
            f"Outlet channels are the primary canals and rivers (plus DEM streams of order >= k only if that is needed to reach the target count). Each cell is traced downstream to its outlet; a sub-KHG is the catchment of one outlet reach on one bank.",
            f"Of {pieces} catchment pieces, those smaller than {min_area:g} km2" + (" (<code>min_area_km2: auto</code>: the smallest value that gives at most 30 units)" if auto else "") + f" are merged, smallest first, into the neighbour they share the longest divide with ({merge} merge; outlet channels only if there is no divide neighbour). Result: {n_units} sub-KHG of {g.area_km2.min():.0f} to {g.area_km2.max():.0f} km2.",
            "Command: <code>python -m repeat_delineation --config ../re-peat/sites/14.02-04-05.01_kampar_gaung/delineate.yaml</code>"]},
        "p_fetch": {"title": "2 Fetch cloud layers (common/sources.py)", "body": [f"One 30 m grid per KHG; layers are written to <code>cache/{kid}/</code> and never refetched (the cache is keyed by file name).",
                                                                                    f"Baseline {base}. Command: <code>repeat-subkhg --config ... --fetch-only</code>."]},
        "p_ind": {"title": "3 Indicators per sub-KHG (common/indicators.py)", "body": [
            "Urgency: NDMI, burned share, hotspots, canal density, water-table days, block gap. Stakes: peat depth, protected share, settlements. Feasibility (reported, not ranked): canal reach, distance to water, lift, access.",
            f"Each is a zonal mean or median over the sub-KHG at 30 m, averaged over {base}. Missing layers leave a column empty and the weights adapt."]},
        "p_score": {"title": "4 Score (subkhg/prioritise.py)", "body": [
            "<b>Need score:</b> each indicator rescaled to 0-1 (5th to 95th percentile within the KHG), group scores as weighted means, <code>0.8 x urgency + 0.2 x stakes</code>. Rainfall and water-balance indicators have weight 0 because they are constant inside a KHG.",
            "<b>Rank-sum (the team's earlier method):</b> each of 8 indicators ranks the sub-KHG, rank 1 = worst condition, total = sum of ranks; the lowest total is the top priority.",
            f"They agree only moderately here: Spearman {agree.get('spearman', float('nan')):.2f}." if agree.get("spearman") is not None else "Both are written side by side."]},
        "p_class": {"title": "5 Classes, ranks, checks", "body": [
            "Classes are tertiles of the score within the KHG (tinggi, sedang, rendah); tidal and excluded-concession units get their own class. Ranks are 1 to n.",
            "Checks: Spearman between indicators (" + (", ".join(f"{p['a']}/{p['b']} {p['spearman']}" for p in pairs) or "no pair above 0.8") + "); weight sensitivity (300 runs, need score only); validation against held-out years (none set in this run)."]},
        "o_units": {"title": "Sub-KHG polygons", "body": ["<code>subkhg_units.gpkg</code>: <code>khg_id</code>, <code>unit_id</code>, geometry. Re-used by later runs as <code>units: {mode: vector}</code>."]},
        "o_rank": {"title": "Ranked sub-KHG", "body": ["<code>unit_prioritas.gpkg</code> and <code>.csv</code>: every indicator, group scores, <code>kelas</code>, <code>peringkat</code>, <code>peringkat_need</code>, <code>peringkat_ranksum</code>, <code>rk_*</code> single ranks and the sensitivity fields."]},
        "o_sekat": {"title": "Block needs", "body": ["<code>kebutuhan_sekat.csv</code>: blocks needed, existing and additional per KHG and class (a first cost estimate)."]},
        "o_rep": {"title": "Checks and maps", "body": ["<code>laporan.json</code> (weights, thresholds, class counts, correlated pairs, sensitivity, agreement of the two methods) and one map PNG per KHG."]},
        "o_md": {"title": "Run report", "body": ["<code>repeat-subkhg-report ...</code> writes the numbers of the run to markdown; <code>repeat-subkhg-dashboard ...</code> writes this page."]},
    }

    caveats = []
    if floor_units is not None and floor_txt:
        caveats.append(("bad", f"<b>Peat depth has a floor at {fl[1]:.0f} cm.</b> {floor_txt}; {floor_units} of {peat_n} sub-KHG have a mean at the floor, so thin peat is not resolved."))
    if slope_cap:
        caveats.append(("warn", f"<b>Block spacing is at its 2,000 m cap for {slope_cap[0]} of {slope_cap[1]} sub-KHG</b> (canal slope under {float(sc['params']['ipg_dA_m']) / float(sc['params']['ipg_js_max_m']):.4f}): blocks needed there is canal length divided by the cap, not a terrain result."))
    if forest_med is not None:
        caveats.append(("warn", f"<b>Tree cover share is high (median {forest_med:.2f})</b> because WorldCover counts plantations as tree cover, so it cannot separate natural forest from acacia."))
    if skill_ok == 0:
        caveats.append(("bad", "<b>Neraca air balance does not rank these sub-KHG</b>: the ET products disagree on the order of units, or it changes between years (balance_stable_ok = 0), so the balance columns are left empty."
                        if flag == "balance_stable_ok" else f"<b>Neraca air failed its skill check</b> on the {n_st} SiTMAT stations (no spatial skill), so its outputs are shown for reference only and have no weight in the need score."))
    if pairs:
        caveats.append(("warn", "<b>Overlapping indicators:</b> " + ", ".join(f"{p['a']} and {p['b']} (rho {p['spearman']})" for p in pairs) + "."))
    caveats.append(("warn", f"<b>Not validated.</b> No held-out outcome was set, the weights are defaults, Sentinel-2 is at {res} m, and the merge of small pieces is by longest shared divide, not by a hydrological hierarchy."))
    cav_html = "".join(f'<div class="note {c}">{t}</div>' for c, t in caveats)

    sections = f"""
<section id="process"><h2>The process</h2>
<p class="lede">Inputs on the left, the five steps in the middle, outputs on the right. Dashed boxes are read from the cloud. Click a box for what it does, its settings and the numbers of this run.</p>
<div class="card"><figure>{flow}<figcaption>How the run for KHG {kid} goes from inputs to ranked sub-KHG. Arrow labels name what moves along them.</figcaption></figure>
<div id="node-detail"><p>Click a box.</p></div>
<div class="legend-row"><span><i class="sw"></i>local file</span><span><i class="sw d"></i>read from the cloud</span><span><i class="sw p"></i>processing step</span><span><i class="sw o"></i>output</span></div></div></section>

<section id="delineation"><h2>Delineation</h2>
<p class="lede">Sub-KHG are the catchments of the outlet channels, one per reach and bank, so divides and outlet canals are the boundaries. Small pieces are merged into a neighbour.</p>
<div class="card"><figure>{funnel}<figcaption>From DTM and canals to {n_units} sub-KHG. Only primary canals and rivers are outlets; all {_n(len(canals)) if canals is not None else 0} canal segments are burned into the DTM.</figcaption></figure></div>
<div class="grid2" style="margin-top:14px"><div class="card chart" id="ch-sweep"></div><div class="card"><div id="sweep-note"></div></div></div></section>

<section id="map"><h2>Map of the outputs</h2>
<p class="lede">Colour the sub-KHG by any output or indicator. Scroll to zoom, drag to pan, double-click to reset, click a sub-KHG for its values.</p>
<div class="controls"><label>Colour by <select id="var"></select></label>
<label><input type="checkbox" id="ov-canals" checked> canals</label><label><input type="checkbox" id="ov-rivers" checked> rivers</label>
<label><input type="checkbox" id="ov-blocks"> existing blocks</label><label><input type="checkbox" id="ov-stations"> water-table stations</label>
<button type="button" id="reset">Reset view</button></div>
<div class="maprow"><div class="mapbox"><canvas class="map" id="map-canvas" role="img" aria-label="Map of the {n_units} sub-KHG coloured by the selected output"></canvas>
<div class="legend" id="legend"></div><div class="hint">no basemap: coordinates are WGS84</div></div>
<aside class="card side" id="unit-panel"><h3>Sub-KHG</h3><p style="color:var(--muted);margin:0">Click a sub-KHG on the map.</p></aside></div></section>

<section id="ranking"><h2>Ranking</h2>
<p class="lede">The need score and the rank-sum rank the same sub-KHG differently; both are in every output. Rank 1 is the highest priority.</p>
<div class="grid2"><div class="card chart" id="ch-ranks"></div><div class="card"><div class="tablewrap" id="top-table"></div></div></div>
<div class="grid2" style="margin-top:14px"><div class="card chart" id="ch-classes"></div><div class="card"><div class="kv" id="rank-facts"></div></div></div></section>

<section id="caveats"><h2>What to keep in mind</h2><p class="lede">Facts from this run that limit how far the numbers can be trusted.</p>{cav_html}</section>
"""
    data = {"units": units, "vars": vars_, "geo": geo, "stations": stations, "bounds": [float(b[0]), float(b[1]), float(b[2]), float(b[3])],
            "details": details, "sweep": sweep, "merge": merge, "classes": CLASSES, "n_units": n_units, "min_area": min_area,
            "agree": agree, "neraca_ok": skill_ok, "method": lap.get("method")}
    foot = ("Generated by <code>repeat-subkhg-dashboard --subkhg-config " + subkhg_config + (f" --neraca-dir {neraca_dir}" if neraca_dir else "")
            + f"</code> on {datetime.date.today()} from the output folders of the run. Steps, settings and reasons: <code>re-peat/sites/{Path(subkhg_config).parent.name}/README.md</code>.")
    facts = [("KHG", kid), ("Sub-KHG", str(n_units)), ("Area", f"{area_tot:,.0f} km2"), ("Baseline", base), ("Method in use", str(lap.get("method"))), ("Generated", str(datetime.date.today()))]
    html_ = K.page("Sub-KHG prioritisation", "How sub-KHG are delineated and ranked by need for intervention, with the outputs of one real run on a map.", facts,
                   [("process", "Process"), ("delineation", "Delineation"), ("map", "Map"), ("ranking", "Ranking"), ("caveats", "Caveats")],
                   sections, data, SCRIPT, foot)
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Path(out).write_text(html_, encoding="utf-8")
    print(f"written {out} ({len(html_) / 1e6:.1f} MB)")


SCRIPT = r"""
wireFlow(DATA.details);
const U=DATA.units,VARS=DATA.vars,GEO=DATA.geo;
const byId={};U.forEach(u=>byId[u.p.unit_id]=u);
// ---- delineation sweep
(function(){const el=$('#ch-sweep'),note=$('#sweep-note');
  if(DATA.sweep){const S=DATA.sweep,rows=S.min_area_km2.map((a,i)=>({label:'min area '+a+' km2',value:S.units_adjacent[i],tip:'<b>'+S.units_adjacent[i]+' sub-KHG</b> (adjacent merge)<br>minimum area '+a+' km2<br>earlier nearest-unit merge: '+S.units_nearest[i],fill:'var(--blue)'}));
    chartBars(el,rows,{title:'Sub-KHG count against the minimum area',ml:130,lo:0,refs:[{v:6,label:'aim 6'},{v:30,label:'aim 30'}]});
    const t=document.createElement('div');tableView(t,['minimum area (km2)','adjacent merge','nearest merge'],S.min_area_km2.map((a,i)=>[a,S.units_adjacent[i],S.units_nearest[i]]));el.appendChild(t);
    note.innerHTML='<p>'+S.pieces+' catchment pieces before merging. Merging into the hydrologically adjacent piece lowers the count smoothly; the earlier merge into the nearest unit collapsed it ('+[5,50,100].map(a=>{const i=S.min_area_km2.indexOf(a);return i<0?null:S.units_nearest[i]}).filter(x=>x!=null).join(', ')+' units at 5, 50, 100 km2).</p><p style="color:var(--muted)">In use: '+DATA.n_units+' sub-KHG at a minimum of '+DATA.min_area+' km2 ('+DATA.merge+' merge).</p>'}
  else{el.innerHTML='<p style="color:var(--muted);margin:0">No sweep was run for this delineation (<code>repeat_delineation --sweep</code>).</p>';note.parentElement.style.display='none';el.parentElement.style.gridColumn='1 / -1'}})();
// ---- map
const cv=$('#map-canvas'),map=new MapView(cv,DATA.bounds),legend=$('#legend'),sel=$('#var'),panel=$('#unit-panel');
const NC=U.length;let cur=VARS[0];
const groups={};VARS.forEach(v=>(groups[v.group]=groups[v.group]||[]).push(v));
Object.keys(groups).forEach(g=>{const og=document.createElement('optgroup');og.label=g;groups[g].forEach(v=>{const o=document.createElement('option');o.value=v.key;o.textContent=v.label;og.appendChild(o)});sel.appendChild(og)});
const range=k=>{const a=U.map(u=>u.p[k]).filter(v=>v!=null);return[Math.min(...a),Math.max(...a)]};
const classT={ 'Kebutuhan intervensi: tinggi':.95,'Kebutuhan intervensi: sedang':.55,'Kebutuhan intervensi: rendah':.2};
function unitFill(it){const v=it.p[cur.key];
  if(cur.kind==='class'){const t=classT[v];return t==null?css('--grid'):ramp(t)}
  if(v==null)return css('--grid');const r=cur._r||(cur._r=range(cur.key));let t=(v-r[0])/((r[1]-r[0])||1);if(cur.kind==='rank')t=1-t;return ramp(t)}
const unitsL=map.addLayer({id:'units',type:'poly',items:U,pickable:true,selectable:true,style:it=>({fill:unitFill(it),stroke:css('--surface'),lw:1})});
const khgL=map.addLayer({id:'khg',type:'poly',items:[{polys:GEO.khg,p:{}}],style:()=>({fill:null,stroke:css('--fg'),lw:1.2})});
const lineW={1:1.8,2:1.0,3:.5};
const canalL=GEO.canals?map.addLayer({id:'canals',type:'line',items:GEO.canals.map(c=>({pts:c[1],k:c[0]})),style:it=>({lw:lineW[it.k]||.5,stroke:it.k===3?css('--axis'):css('--faint')})}):null;
const riverL=GEO.rivers?map.addLayer({id:'rivers',type:'line',items:GEO.rivers.map(c=>({pts:c[1]})),style:()=>({lw:2,stroke:css('--blue')})}):null;
const blockL=GEO.blocks?map.addLayer({id:'blocks',type:'point',visible:false,items:GEO.blocks.map(p=>({x:p[0],y:p[1]})),style:()=>({r:2,fill:css('--orange'),stroke:css('--surface'),ring:.5})}):null;
const stL=DATA.stations.length?map.addLayer({id:'stations',type:'point',visible:false,pickable:true,items:DATA.stations,style:it=>({r:5,fill:it.obs==null?css('--grid'):rampO((it.obs-10)/110),stroke:css('--fg'),ring:1})}):null;
// khg outline above units, canals above that: reorder so units are below overlays
map.layers.splice(map.layers.indexOf(khgL),1);map.layers.push(khgL);
[['ov-canals',canalL],['ov-rivers',riverL],['ov-blocks',blockL],['ov-stations',stL]].forEach(([id,l])=>{const c=$('#'+id);if(!l){c.parentElement.style.display='none';return}c.checked=l.visible;c.addEventListener('change',()=>{l.visible=c.checked;map.draw()})});
function setLegend(){if(cur.kind==='class'){legendCat(legend,cur.label,DATA.classes.slice(0,3).map(c=>[ramp(classT[c]),c.replace('Kebutuhan intervensi: ','need ')]))}
  else{const r=range(cur.key);legendCont(legend,cur.label+(cur.kind==='rank'?' (dark = rank 1)':''),r[0],r[1],v=>fmt(v,2),cur.kind==='rank')}
  if(stL&&stL.visible){legend.innerHTML+='<div style="margin-top:6px">Stations: observed peak depth, ring = station</div>'}}
sel.addEventListener('change',()=>{cur=VARS.find(v=>v.key===sel.value);setLegend();map.draw()});
$('#reset').addEventListener('click',()=>{map.view={k:1,x:0,y:0};map.draw()});
window.addEventListener('themechange',()=>{setLegend();map.draw();drawCharts()});
matchMedia('(prefers-color-scheme:dark)').addEventListener('change',()=>{setLegend();map.draw();drawCharts()});
const val=(u,k)=>{const v=u.p[k];return v==null?'n/a':(typeof v==='string'?v.replace('Kebutuhan intervensi: ','need '):fmt(v,3))};
map.onhover=h=>{if(h.layer.id==='units'){const u=h.item;return '<b>'+u.p.unit_id+'</b><br><span>'+val(u,'kelas')+'</span><br>rank '+val(u,'peringkat')+' &middot; '+esc(cur.label)+': <b>'+val(u,cur.key)+'</b>'}
  if(h.layer.id==='stations'){return '<b>'+esc(h.item.id)+'</b><br>observed peak depth '+(h.item.obs==null?'n/a':h.item.obs+' cm')}return null};
map.onclick=h=>{if(!h||h.layer.id!=='units'){panel.innerHTML='<h3>Sub-KHG</h3><p style="color:var(--muted);margin:0">Click a sub-KHG on the map.</p>';return}
  const u=h.item;let rows='';let g0=null;
  VARS.forEach(v=>{if(v.group!==g0){rows+='<tr><td colspan="2" style="padding-top:8px;color:var(--faint);font-size:11px;text-transform:uppercase;letter-spacing:.05em">'+esc(v.group)+'</td></tr>';g0=v.group}
    rows+='<tr><td>'+esc(v.label)+'</td><td>'+val(u,v.key)+'</td></tr>'});
  panel.innerHTML='<h3>'+u.p.unit_id+'</h3><table>'+rows+'</table>'};
// ---- ranking charts
function drawCharts(){
  const pts=U.filter(u=>u.p.peringkat_need!=null&&u.p.peringkat_ranksum!=null).map(u=>({x:u.p.peringkat_need,y:u.p.peringkat_ranksum,tip:'<b>'+u.p.unit_id+'</b><br>rank by need score '+u.p.peringkat_need+'<br>rank by rank-sum '+u.p.peringkat_ranksum}));
  const n=U.length;chartScatter($('#ch-ranks'),pts,{title:'Two methods, two rankings (1 = highest priority)',xl:'rank by need score',yl:'rank by rank-sum',x0:0,x1:n+1,y0:0,y1:n+1,lines:[[0,0,n+1,n+1]],h:380});
  const t=document.createElement('div');tableView(t,['sub-KHG','rank by need score','rank by rank-sum'],pts.map(p=>[p.tip.match(/<b>(.*?)<\/b>/)[1],p.x,p.y]));$('#ch-ranks').appendChild(t);
  const cc={};U.forEach(u=>cc[u.p.kelas]=(cc[u.p.kelas]||0)+1);
  const rows=DATA.classes.filter(c=>cc[c]).map(c=>({label:c.replace('Kebutuhan intervensi: ','need ').replace('Pengaruh pasang surut: pantau','tidal').replace('Dikecualikan (pengelolaan lahan)','excluded'),value:cc[c],tip:cc[c]+' sub-KHG',fill:classT[c]!=null?ramp(classT[c]):'var(--axis)'}));
  chartBars($('#ch-classes'),rows,{title:'Sub-KHG per class',ml:90,lo:0});
  const t2=document.createElement('div');tableView(t2,['class','sub-KHG'],rows.map(r=>[r.label,r.value]));$('#ch-classes').appendChild(t2)}
drawCharts();
(function(){const top=U.slice().sort((a,b)=>a.p.peringkat-b.p.peringkat).slice(0,10);
  $('#top-table').innerHTML='<table class="data"><thead><tr><th>Top 10</th><th style="text-align:left">class</th><th>rank</th><th>need</th><th>rank-sum</th><th>km2</th></tr></thead><tbody>'+top.map(u=>'<tr><td>'+u.p.unit_id+'</td><td style="text-align:left">'+val(u,'kelas')+'</td><td>'+u.p.peringkat+'</td><td>'+u.p.peringkat_need+'</td><td>'+u.p.peringkat_ranksum+'</td><td>'+fmt(u.p.area_km2,0)+'</td></tr>').join('')+'</tbody></table>';
  const a=DATA.agree||{};const kv=$('#rank-facts');kv.innerHTML='<div>Method that sets the class</div><div>'+esc(DATA.method||'')+'</div><div>Agreement (Spearman)</div><div>'+(a.spearman==null?'n/a':fmt(a.spearman,2))+'</div>'
   +'<div>Neraca air</div><div>'+(DATA.neraca_ok===0?'failed its skill check, not scored':DATA.neraca_ok===1?'passed':'not merged')+'</div>'})();
setLegend();map.draw();
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--subkhg-config", required=True)
    ap.add_argument("--neraca-dir", help="the KHG's 03_neraca folder (stations from inputs/)")
    ap.add_argument("--out", default="docs/process/subkhg_process.html")
    a = ap.parse_args(argv)
    build(a.subkhg_config, a.neraca_dir, a.out)


if __name__ == "__main__":
    main()
