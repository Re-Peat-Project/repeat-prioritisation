#!/usr/bin/env python3
"""Does fire change at the edge of licence areas on peat, and does the change depend on the position on the dome?

  python -m repeat_prioritisation.investigations.licence_edge --khg 14.02-04-05.01 [--khg ...] [--cell 200] [--dem auto]
  python -m repeat_prioritisation.investigations.licence_edge --khg-list re-peat/sites/selected_khg.csv        # batch
  python -m repeat_prioritisation.investigations.licence_edge --summarise                                      # combine finished KHG

Reads only the KHG work folder (`_khg/<code>_<name>/00_inputs`, `01_dem/inputs`), so it runs on any KHG whose inputs are clipped; a KHG
without licences or without a DEM still gets the part that does not need them. Peat cells (GFW extent) on a regular grid
(`--cell`, metres) carry: signed distance to the edge of the licence union (negative inside, positive outside, AEA metres), height above
the nearest river from the DTM (position on the dome, tertiles of the KHG's peat cells: foot, slope, crest), distance to the nearest canal,
and fire: VIIRS hotspots 2012-2025 (nominal and high confidence kept, low dropped; high reported on its own) and burned area 2015-2025.
Hotspots are assigned to the grid cell nearest to them. Fire is counted on peat and divided by peat area.

The test is the contrast at equal distance on the two sides of the licence boundary, inside each position class, by year. A step at the
edge is read as a difference in land management or fire control across the line; a smooth gradient is read as position. Neither is
read as responsibility. Fire also follows ignition (villages, farming, canals) and fire fighting, so distance to canal is kept as a
second stratum and the result is an association.

Outputs in `<khg>/04_prioritisation/licence_edge/`: cells.csv.gz (one row per peat cell), band_position.csv (fire per band and position),
band_year.csv, edge_contrast.csv, summary.json, figures/*.png and report.md.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
from pyproj import Transformer
from scipy.spatial import cKDTree

from repeat_common import khg as K
from repeat_prioritisation.national import profile as P

log = logging.getLogger("licence_edge")

AEA = P.AEA
BANDS = [(-1e9, -5000), (-5000, -2000), (-2000, -500), (-500, 0), (0, 500), (500, 2000), (2000, 5000), (5000, 1e9)]
BAND_LABEL = ["< -5 km", "-5 to -2 km", "-2 to -0.5 km", "-0.5 to 0 km", "0 to 0.5 km", "0.5 to 2 km", "2 to 5 km", "> 5 km"]
POS = ["foot", "slope", "crest"]
YEARS = list(range(2012, 2026))
BA_YEARS = list(range(2015, 2026))
DRY_YEARS = (2015, 2019, 2023)          # strong dry-season years in the record; reported as a group, not tuned


def to_aea(lon, lat):
    tf = Transformer.from_crs(4326, AEA, always_xy=True)
    return tf.transform(np.asarray(lon, float), np.asarray(lat, float))


def dem_candidates(folder: Path, which: str):
    """(name, path) of the DEMs that can give position on the dome, best first: LiDAR where the KHG has it, then DeltaDTM, then DEMNAS
    (raw clips). The first one that covers most peat cells is used."""
    man = folder / "01_dem" / "inputs" / "manifest.csv"
    if not man.exists():
        return []
    m = pd.read_csv(man).dropna(subset=["file"])
    out = []
    for o in (["lidar", "deltadtm", "demnas"] if which == "auto" else [which]):
        hit = m[m["product"].str.startswith(o)] if o == "lidar" else m[m["product"] == o]
        out += [(r.product, folder / "01_dem" / "inputs" / r.file) for r in hit.itertuples() if (folder / "01_dem" / "inputs" / r.file).exists()]
    return out


def sample_raster(path, x_aea, y_aea):
    """Raster values at AEA points, read through one window (nodata and outside -> NaN)."""
    with rasterio.open(path) as src:
        tf = Transformer.from_crs(AEA, src.crs, always_xy=True)
        x, y = tf.transform(x_aea, y_aea)
        win = rasterio.windows.from_bounds(x.min(), y.min(), x.max(), y.max(), src.transform).round_offsets().round_lengths()
        try:
            win = rasterio.windows.Window(win.col_off - 2, win.row_off - 2, win.width + 4, win.height + 4).intersection(
                rasterio.windows.Window(0, 0, src.width, src.height))
        except rasterio.errors.WindowError:
            return np.full(len(x_aea), np.nan)
        a = src.read(1, window=win).astype(float)
        tr = src.window_transform(win)
        if src.nodata is not None:
            a[a == src.nodata] = np.nan
        col = np.floor((x - tr.c) / tr.a).astype(int)
        row = np.floor((y - tr.f) / tr.e).astype(int)
        ok = (row >= 0) & (row < a.shape[0]) & (col >= 0) & (col < a.shape[1])
        v = np.full(len(x), np.nan)
        v[ok] = a[row[ok], col[ok]]
    return v


def line_vertices(path, mask_ll, step_m=100.0):
    """Points every ~step_m along the lines of a layer, AEA metres, as an (n, 2) array."""
    if not Path(path).exists():
        return np.zeros((0, 2))
    g = pyogrio.read_dataframe(path, mask=mask_ll)
    if not len(g):
        return np.zeros((0, 2))
    ga = shapely.transform(g.geometry.values, lambda c: np.column_stack(to_aea(c[:, 0], c[:, 1])))
    out = []
    for geom in ga:
        if geom is None or geom.is_empty:
            continue
        parts = geom.geoms if hasattr(geom, "geoms") else [geom]
        for ln in parts:
            n = max(int(ln.length // step_m), 1)
            out.append(shapely.get_coordinates(shapely.line_interpolate_point(ln, np.linspace(0, ln.length, n + 1))))
    return np.vstack(out) if out else np.zeros((0, 2))


def signed_edge_distance(x, y, lic_union):
    """Distance to the licence boundary in metres: negative inside the union, positive outside; NaN when there are no licences."""
    if lic_union is None or lic_union.is_empty:
        return np.full(len(x), np.nan)
    pts = shapely.points(x, y)
    lines = shapely.get_parts(shapely.boundary(lic_union))
    tree = shapely.STRtree(lines)
    _, d = tree.query_nearest(pts, return_distance=True, all_matches=False)
    inside = np.zeros(len(x), bool)
    inside[shapely.STRtree(shapely.get_parts(lic_union)).query(pts, predicate="within")[0]] = True
    return np.where(inside, -d, d)


LIC_SOURCE = "landstatus/ALL_Updade__IZIN_USAHA__PBPH_Perkebunan_HTRKM_Tambang__2025.gpkg"


def ensure_licences(inp: Path, khg_ll):
    """Clip the national licence layer to the KHG plus 5 km into 00_inputs/national when the KHG folder does not hold it yet, and
    list the clip in local_manifest.csv (same columns as the other clips)."""
    dst = inp / "national" / "izin_usaha_2025.gpkg"
    if dst.exists():
        return
    import hashlib
    src = Path(os.environ["REPEAT_DATA"]) / LIC_SOURCE
    ring = shapely.transform(shapely.transform(khg_ll, lambda c: np.column_stack(to_aea(c[:, 0], c[:, 1]))).buffer(5000),
                             lambda c: np.column_stack(Transformer.from_crs(AEA, 4326, always_xy=True).transform(c[:, 0], c[:, 1])))
    lic = pyogrio.read_dataframe(src, mask=ring)
    dst.parent.mkdir(parents=True, exist_ok=True)
    lic.to_file(dst, driver="GPKG")
    man = inp / "local_manifest.csv"
    row = pd.DataFrame([{"file": "national/izin_usaha_2025.gpkg", "source": LIC_SOURCE, "what": "business licences 2025 (IZIN_USAHA), clipped to the KHG plus 5 km (licence_edge)",
                         "count": len(lic), "bytes": dst.stat().st_size, "sha256": hashlib.sha256(dst.read_bytes()).hexdigest()}])
    pd.concat([pd.read_csv(man), row]).to_csv(man, index=False) if man.exists() else row.to_csv(man, index=False)
    log.info("clipped %d licences into %s", len(lic), dst)


def build_cells(code: str, cell: float, dem: str):
    f = K.folder(code)
    inp = f / "00_inputs"
    khg = gpd.read_file(inp / "khg.gpkg").to_crs(4326)
    g_ll = shapely.make_valid(khg.geometry.union_all())
    g_a = shapely.transform(g_ll, lambda c: np.column_stack(to_aea(c[:, 0], c[:, 1])))
    x0, y0, x1, y1 = g_a.bounds
    X, Y = np.meshgrid(np.arange(x0 + cell / 2, x1, cell), np.arange(y0 + cell / 2, y1, cell))
    X, Y = X.ravel(), Y.ravel()
    m = shapely.contains_xy(g_a, X, Y)
    X, Y = X[m], Y[m]
    inv = Transformer.from_crs(AEA, 4326, always_xy=True)
    lon, lat = inv.transform(X, Y)
    c = pd.DataFrame({"x": X, "y": Y, "lon": lon, "lat": lat})

    ensure_licences(inp, g_ll)
    pe = inp / "national" / "peat_extent_gfw_v20230315_z11.tif"
    ps = P.PeatSampler(pe)
    c["peat"] = ps.sample(ps.window(g_ll), lon, lat) == 1
    c = c[c.peat].reset_index(drop=True)
    X, Y = c.x.to_numpy(), c.y.to_numpy()
    log.info("%s: %d peat cells of %g m", code, len(c), cell)

    # licences: union in AEA; the clip holds licences up to 5 km outside the KHG
    lp = inp / "national" / "izin_usaha_2025.gpkg"
    lic_union, lic_n = None, 0
    if lp.exists():
        lic = pyogrio.read_dataframe(lp, columns=["PERUSAHAAN", "IZIN_USAHA"])
        lic = lic[lic.geometry.notna() & ~lic.geometry.is_empty]
        lic_n = len(lic)
        if lic_n:
            ga = shapely.transform(shapely.make_valid(lic.geometry.values), lambda q: np.column_stack(to_aea(q[:, 0], q[:, 1])))
            lic_union = shapely.union_all(ga, grid_size=1.0)       # snapped to 1 m: some licence polygons overlap with slivers
    c["edge_m"] = signed_edge_distance(X, Y, lic_union)

    # position on the dome: height above the median of the 20 nearest river points, DTM from the KHG folder
    dem_name, z = None, None
    for name, path in dem_candidates(f, dem):
        zz = sample_raster(path, X, Y)
        if np.isfinite(zz).mean() > 0.8:
            dem_name, dem_path, z = name, path, zz
            break
        log.info("%s: %s covers %.0f%% of the peat cells, next DEM", code, name, 100 * np.isfinite(zz).mean())
    c["har_m"] = np.nan
    if z is not None:
        rv = line_vertices(inp / "rivers.gpkg", g_ll.buffer(0.05))
        zr = sample_raster(dem_path, rv[:, 0], rv[:, 1]) if len(rv) else np.zeros(0)
        ok = np.isfinite(zr)
        if ok.sum() >= 5:
            tree = cKDTree(rv[ok])
            _, idx = tree.query(np.column_stack([X, Y]), k=min(20, int(ok.sum())))
            base = np.nanmedian(zr[ok][idx], axis=1) if idx.ndim > 1 else zr[ok][idx]
        else:                     # no river with a DTM value: height above the lowest 5% of the peat cells
            base = np.nanpercentile(z, 5)
        c["har_m"] = z - base
    ok = c.har_m.notna()
    c["position"] = ""
    if ok.sum() > 30:
        q1, q2 = np.nanpercentile(c.har_m[ok], [100 / 3, 200 / 3])
        c.loc[ok, "position"] = np.where(c.har_m[ok] <= q1, "foot", np.where(c.har_m[ok] <= q2, "slope", "crest"))

    cv = line_vertices(inp / "canals.gpkg", g_ll.buffer(0.05))
    c["canal_m"] = cKDTree(cv).query(np.column_stack([X, Y]))[0] if len(cv) else np.nan

    # fire
    hs = pyogrio.read_dataframe(inp / "national" / "hotspot_viirs_snpp_2012_2025.gpkg", columns=["year", "confidence"], mask=g_ll)
    hs = hs[hs.confidence.isin(["n", "h"])]
    hs = hs[ps.sample(ps.window(g_ll), hs.geometry.x.to_numpy(), hs.geometry.y.to_numpy()) == 1]     # on peat, at the hotspot itself
    hx, hy = to_aea(hs.geometry.x.to_numpy(), hs.geometry.y.to_numpy())
    tree = cKDTree(np.column_stack([X, Y]))
    d, idx = tree.query(np.column_stack([hx, hy]))
    keep = d <= cell * 0.71                      # the grid cell that holds the hotspot (half the cell diagonal)
    for y in YEARS:
        c[f"hs_{y}"] = 0
        c[f"hh_{y}"] = 0
    for y, conf, i in zip(hs.year[keep], hs.confidence[keep], idx[keep]):
        c.loc[i, f"hs_{y}"] += 1
        if conf == "h":
            c.loc[i, f"hh_{y}"] += 1
    bp = inp / "national" / "burnt_area_2015_2026_Indonesia.gpkg"
    b = pyogrio.read_dataframe(bp, mask=g_ll)
    pts = shapely.points(X, Y)
    for y in BA_YEARS:
        c[f"ba_{y}"] = False
        col = f"BA_{y}"
        if col in b.columns and len(b):
            polys = shapely.transform(shapely.make_valid(b.geometry[b[col].notna()].values), lambda q: np.column_stack(to_aea(q[:, 0], q[:, 1])))
            if len(polys):
                c.loc[shapely.STRtree(polys).query(pts, predicate="within")[0], f"ba_{y}"] = True
    meta = {"khg": code, "cell_m": cell, "peat_cells": int(len(c)), "licences": int(lic_n), "dem": dem_name,
            "khg_km2": float(g_a.area / 1e6), "peat_km2": float(len(c) * cell * cell / 1e6),
            "licence_peat_km2": float((c.edge_m < 0).sum() * cell * cell / 1e6) if lic_n else 0.0}
    return c, meta


def band_of(edge):
    out = np.full(len(edge), -1)
    for i, (a, b) in enumerate(BANDS):
        out[(edge > a) & (edge <= b)] = i
    out[~np.isfinite(edge)] = -1
    return out


def reading(lo, hi):
    """Reading of a rate ratio from its block interval: the interval excludes 1 on one side, or not."""
    return np.where(lo > 1, "outside higher", np.where(hi < 1, "inside higher", "no clear difference"))


def ci_rate(n, e, z=1.96):
    """Poisson rate n/e with a normal-on-sqrt interval; e is exposure."""
    r = n / e if e else np.nan
    lo = ((np.sqrt(n) - z / 2) ** 2 / e) if (e and n > 0) else (0.0 if e else np.nan)
    hi = ((np.sqrt(n + 1) + z / 2) ** 2 / e) if e else np.nan
    return r, lo, hi


def block_ci(inn, out, block_m=5000.0, n_boot=1000, seed=1):
    """95% interval of the out/in hotspot rate ratio, resampling spatial blocks of block_m (cells inside and outside the edge are
    drawn together by block), so clustered fire does not make the interval too narrow. Returns (lo, hi, blocks)."""
    def per_block(d, tag):
        k = (np.floor(d.x / block_m).astype(int).astype(str) + "_" + np.floor(d.y / block_m).astype(int).astype(str))
        return d.assign(blk=k).groupby("blk").agg(**{f"h_{tag}": ("hs_all", "sum"), f"n_{tag}": ("hs_all", "size")})
    t = per_block(inn, "i").join(per_block(out, "o"), how="outer").fillna(0)
    nb = len(t)
    if nb < 5:
        return (np.nan, np.nan, nb)
    A = t[["h_i", "n_i", "h_o", "n_o"]].to_numpy(float)
    rng = np.random.default_rng(seed)
    idx = rng.integers(0, nb, size=(n_boot, nb))
    S = A[idx].sum(axis=1)
    with np.errstate(divide="ignore", invalid="ignore"):
        rr = (S[:, 2] / S[:, 3]) / (S[:, 0] / S[:, 1])
    rr = rr[np.isfinite(rr)]
    return (float(np.percentile(rr, 2.5)), float(np.percentile(rr, 97.5)), nb) if len(rr) > 50 else (np.nan, np.nan, nb)


def tables(c: pd.DataFrame, cell: float):
    a_km2 = cell * cell / 1e6
    c = c.copy()
    c["band"] = band_of(c.edge_m.to_numpy())
    hs_cols, hh_cols = [f"hs_{y}" for y in YEARS], [f"hh_{y}" for y in YEARS]
    c["hs_all"], c["hh_all"] = c[hs_cols].sum(axis=1), c[hh_cols].sum(axis=1)
    c["hs_dry"] = c[[f"hs_{y}" for y in DRY_YEARS]].sum(axis=1)
    c["burned_any"] = c[[f"ba_{y}" for y in BA_YEARS]].any(axis=1)
    rows = []
    for pos in ["all"] + POS:
        sub = c if pos == "all" else c[c.position == pos]
        for i, lab in enumerate(BAND_LABEL):
            s = sub[sub.band == i]
            if not len(s):
                continue
            km2 = len(s) * a_km2
            r, lo, hi = ci_rate(s.hs_all.sum(), km2 * len(YEARS))
            rd, lod, hid = ci_rate(s.hs_dry.sum(), km2 * len(DRY_YEARS))
            rows.append({"position": pos, "band": lab, "band_i": i, "peat_km2": km2, "hotspots": int(s.hs_all.sum()), "high_hotspots": int(s.hh_all.sum()),
                         "hs_per_100km2_yr": 100 * r, "lo": 100 * lo, "hi": 100 * hi,
                         "hs_per_100km2_dry_yr": 100 * rd, "lo_dry": 100 * lod, "hi_dry": 100 * hid,
                         "burned_share_2015_25": float(s.burned_any.mean()), "median_canal_m": float(s.canal_m.median()),
                         "median_har_m": float(s.har_m.median()) if s.har_m.notna().any() else np.nan})
    bp = pd.DataFrame(rows)
    groups = {"inside, more than 0.5 km from the edge": (-1e9, -500), "inside, within 0.5 km of the edge": (-500, 0),
              "outside, within 0.5 km": (0, 500), "outside, 0.5 to 2 km": (500, 2000), "outside, 2 to 5 km": (2000, 5000)}
    yr = []
    for gname, (a, b) in groups.items():
        for pos in ["all"] + POS:
            s = c[(c.edge_m > a) & (c.edge_m <= b)]
            s = s if pos == "all" else s[s.position == pos]
            if not len(s):
                continue
            km2 = len(s) * a_km2
            for y in YEARS:
                yr.append({"group": gname, "position": pos, "year": y, "peat_km2": km2, "hotspots": int(s[f"hs_{y}"].sum()),
                           "high_hotspots": int(s[f"hh_{y}"].sum()), "hs_per_100km2": 100 * s[f"hs_{y}"].sum() / km2,
                           "burned_share": float(s[f"ba_{y}"].mean()) if y in BA_YEARS else np.nan})
    byr = pd.DataFrame(yr)
    # edge contrast: 0-2 km outside against 0-2 km inside, same position class, per cell stratum of canal distance
    ec = []
    for pos in ["all"] + POS:
        s0 = c if pos == "all" else c[c.position == pos]
        for cn, (ca, cb) in {"all": (0, 1e9), "canal < 1 km": (0, 1000), "canal >= 1 km": (1000, 1e9)}.items():
            s = s0[(s0.canal_m >= ca) & (s0.canal_m < cb)] if s0.canal_m.notna().any() else s0
            inn, out = s[(s.edge_m > -2000) & (s.edge_m <= 0)], s[(s.edge_m > 0) & (s.edge_m <= 2000)]
            if len(inn) < 20 or len(out) < 20:
                continue
            ki, ko = inn.hs_all.sum(), out.hs_all.sum()
            ei, eo = len(inn) * a_km2 * len(YEARS), len(out) * a_km2 * len(YEARS)
            rr = (ko / eo) / (ki / ei) if ki else np.nan
            se = np.sqrt(1 / ko + 1 / ki) if ko and ki else np.nan
            blo = block_ci(inn, out)
            ec.append({"position": pos, "canal": cn, "inside_km2": len(inn) * a_km2, "outside_km2": len(out) * a_km2, "hotspots_inside": int(ki),
                       "hotspots_outside": int(ko), "rate_ratio_out_over_in": rr, "blocks": int(blo[2]),
                       "lo_block": blo[0], "hi_block": blo[1],
                       "lo_poisson": rr * np.exp(-1.96 * se) if np.isfinite(se) else np.nan, "hi_poisson": rr * np.exp(1.96 * se) if np.isfinite(se) else np.nan})
    return bp, byr, pd.DataFrame(ec)


def figures(out: Path, bp, byr, title):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig_dir = out / "figures"
    fig_dir.mkdir(exist_ok=True)
    col = {"foot": "#1b9e77", "slope": "#d95f02", "crest": "#7570b3", "all": "#333333"}
    fig, ax = plt.subplots(figsize=(7.5, 4))
    for pos in ["all"] + POS:
        s = bp[bp.position == pos].sort_values("band_i")
        if len(s):
            ax.errorbar(s.band_i, s.hs_per_100km2_yr, yerr=[s.hs_per_100km2_yr - s.lo, s.hi - s.hs_per_100km2_yr], marker="o", ms=4, lw=1.5 if pos != "all" else 2.2,
                        color=col[pos], label=pos, capsize=2, ls="-" if pos != "all" else "--")
    ax.axvline(3.5, color="k", lw=0.8)
    ax.set_xticks(range(len(BAND_LABEL)), BAND_LABEL, rotation=30, ha="right")
    ax.set_ylabel("VIIRS hotspots per 100 km² of peat per year, 2012-2025")
    ax.set_xlabel("distance to licence edge (negative inside)")
    ax.set_title(title, fontsize=9)
    ax.legend(title="dome position", fontsize=8)
    fig.tight_layout()
    fig.savefig(fig_dir / "fire_by_edge_distance.png", dpi=150)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(7.5, 4))
    s = byr[byr.position == "all"]
    for i, (g, d) in enumerate(s.groupby("group", sort=False)):
        ax.plot(d.year, d.hs_per_100km2, marker="o", ms=3, label=g, color=plt.cm.viridis(i / 4.2))
    ax.set_ylabel("hotspots per 100 km² of peat")
    ax.legend(fontsize=7)
    ax.set_title(title, fontsize=9)
    fig.tight_layout()
    fig.savefig(fig_dir / "fire_by_year.png", dpi=150)
    plt.close(fig)


def report(out: Path, meta, bp, byr, ec):
    L = [f"# Fire at the licence edge: {meta['khg']}", "",
         f"Peat cells {meta['peat_cells']:,} of {meta['cell_m']:g} m ({meta['peat_km2']:,.0f} km² peat of {meta['khg_km2']:,.0f} km²); {meta['licences']} licence polygons; "
         f"{meta['licence_peat_km2']:,.0f} km² of the peat lies in a licence. DTM for dome position: {meta['dem'] or 'none'}. Written by "
         "`repeat_prioritisation.investigations.licence_edge`. Association by position, not responsibility.", ""]
    if not len(bp):
        L.append("No peat cells with a licence edge distance.")
    else:
        t = bp[bp.position == "all"][["band", "peat_km2", "hotspots", "high_hotspots", "hs_per_100km2_yr", "hs_per_100km2_dry_yr", "burned_share_2015_25", "median_canal_m", "median_har_m"]]
        L += ["## Fire by distance to the licence edge (all positions)", "", t.round(2).to_markdown(index=False), ""]
    if len(ec):
        L += ["## Edge contrast: 0-2 km outside over 0-2 km inside, hotspots per km² of peat", "", ec.round(2).to_markdown(index=False), "",
              "`lo_block`/`hi_block`: 95% interval from resampling 5 km blocks (fire clusters); `lo_poisson`/`hi_poisson` treat hotspots as independent and are too narrow. "
              "Rate ratio above 1: more fire per peat area just outside the edge than just inside, in the same position class and canal stratum.", ""]
    L += ["![](figures/fire_by_edge_distance.png)", "", "![](figures/fire_by_year.png)", ""]
    (out / "report.md").write_text("\n".join(L), encoding="utf-8")


def one(code, cell, dem, force=False):
    f = K.folder(code)
    out = f / "04_prioritisation" / "licence_edge"
    out.mkdir(parents=True, exist_ok=True)
    cells_p = out / "cells.csv.gz"
    if cells_p.exists() and not force:
        c = pd.read_csv(cells_p)
        c["position"] = c["position"].fillna("")
        meta = json.loads((out / "summary.json").read_text())
    else:
        c, meta = build_cells(code, cell, dem)
        c.to_csv(cells_p, index=False)
    bp, byr, ec = tables(c, meta["cell_m"])
    bp.to_csv(out / "band_position.csv", index=False)
    byr.to_csv(out / "band_year.csv", index=False)
    ec.to_csv(out / "edge_contrast.csv", index=False)
    meta["edge_contrast"] = ec.to_dict("records")
    (out / "summary.json").write_text(json.dumps(meta, indent=1, default=float), encoding="utf-8")
    if len(bp):
        figures(out, bp, byr, meta["khg"])
    report(out, meta, bp, byr, ec)
    return meta


def summarise():
    rows = []
    for d in sorted(K.root().glob("*/04_prioritisation/licence_edge/edge_contrast.csv")):
        if d.stat().st_size < 5:       # no licence on peat in this KHG: no contrast
            continue
        e = pd.read_csv(d)
        e.insert(0, "khg_folder", d.parents[2].name)
        rows.append(e)
    if rows:
        out = K.root() / "licence_edge_contrast.csv"
        allc = pd.concat(rows)
        allc.to_csv(out, index=False)
        log.info("wrote %s", out)
        hub_report(allc)


def hub_report(allc):
    """Cross-KHG table in re-peat/reports/investigations/licence_edge.md, written from licence_edge_contrast.csv."""
    a = allc[(allc.position == "all") & (allc.canal == "all")].copy()
    a["reading"] = reading(a.lo_block, a.hi_block)
    names = {r["khg_code"][4:]: r["name"] for r in K.registry()}
    a["KHG"] = a.khg_folder.str.split("_").str[0].map(names).fillna(a.khg_folder)
    t = a[["KHG", "inside_km2", "outside_km2", "hotspots_inside", "hotspots_outside", "rate_ratio_out_over_in", "lo_block", "hi_block", "reading"]]
    t.columns = ["KHG", "peat inside 0-2 km (km²)", "peat outside 0-2 km (km²)", "hotspots inside", "hotspots outside", "rate ratio", "lo", "hi", "reading"]
    pos = allc[(allc.canal == "all") & (allc.position != "all")].pivot_table(index="khg_folder", columns="position", values="rate_ratio_out_over_in")
    pos.index = [names.get(i.split("_")[0], i) for i in pos.index]
    n = a.reading.value_counts()
    L = ["# Fire at the licence edge, by dome position", "",
         "`python -m repeat_prioritisation.investigations.licence_edge --all-folders` (repeat-prioritisation). Per KHG: peat cells of 200 m, signed distance to the "
         "edge of the 2025 licence layer, height above the nearest river from the DTM split in thirds of the KHG's peat (foot, slope, crest), VIIRS hotspots "
         "2012-2025 (nominal and high confidence) on peat per km² of peat. Per-KHG reports and figures: `_khg/<khg>/04_prioritisation/licence_edge/`.", "",
         "## Hotspot rate 0-2 km outside the licence edge over 0-2 km inside", "", t.round(2).to_markdown(index=False), "",
         "lo and hi: 95% interval from resampling 5 km blocks. Ratio above 1: more fire per peat area just outside the edge. "
         f"Readings: {int(n.get('outside higher', 0))} KHG outside higher, {int(n.get('inside higher', 0))} inside higher, {int(n.get('no clear difference', 0))} no clear difference.", "",
         "## Rate ratio by dome position", "", pos.round(2).to_markdown(), "",
         "KHG with no licence on peat (Mempawah-Peniti, Balangan-Batangalai, Buru-Mappi) have no contrast. Position uses the best DTM that covers the KHG "
         "(`summary.json` names it); where no river has a DTM value it is height above the lowest 5% of the peat cells.", "",
         "## Limits", "",
         "- Association by position. Fire also follows ignition, canals and fire fighting; the canal strata are in each KHG's `edge_contrast.csv`.",
         "- The licence layer is the 2025 map, applied to fire since 2012.",
         "- Hotspots are satellite detections, not area burned; burned area 2015-2025 is in `band_position.csv`.",
         "- This is fire only. Wetness by zone is in `licence_edge_model.md` and `licence_edge_s1.md`; what the rules say is in `licence_rules.csv`.", ""]
    dst = Path(os.environ.get("REPEAT_HUB") or K.WORKSPACE / "re-peat") / "reports" / "investigations" / "licence_edge.md"
    dst.write_text("\n".join(L), encoding="utf-8")
    log.info("wrote %s", dst)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--khg", nargs="*", default=[], help="KHG codes (or names)")
    ap.add_argument("--khg-list", help="CSV with a khg_code column; the batch runs each")
    ap.add_argument("--cell", type=float, default=200.0)
    ap.add_argument("--dem", default="auto", help="auto, lidar, deltadtm or demnas (raw clips in 01_dem/inputs)")
    ap.add_argument("--force", action="store_true", help="rebuild cells.csv.gz")
    ap.add_argument("--all-folders", action="store_true", help="every KHG folder under _khg with the clipped national inputs (the licence clip is made when missing)")
    ap.add_argument("--summarise", action="store_true")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    codes = list(a.khg)
    if a.khg_list:
        codes += pd.read_csv(a.khg_list)["khg_code"].astype(str).str.replace("KHG.", "", regex=False).tolist()
    if a.all_folders:
        codes += [d.parents[2].name.split("_")[0] for d in sorted(K.root().glob("*/00_inputs/national/peat_extent_gfw_v20230315_z11.tif"))]
    for code in dict.fromkeys(codes):
        try:
            m = one(code, a.cell, a.dem, a.force)
            log.info("%s done: %s", code, {k: m[k] for k in ("peat_km2", "licences", "licence_peat_km2", "dem")})
        except Exception as e:      # noqa: batch runner: one KHG failing must not stop the others
            log.error("%s failed: %s", code, e, exc_info=len(codes) == 1)
    if a.summarise or codes:
        summarise()
    return 0


if __name__ == "__main__":
    sys.exit(main())
