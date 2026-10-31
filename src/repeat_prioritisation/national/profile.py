#!/usr/bin/env python3
"""National KHG profile and ranking from the local vector layers (no cloud fetch): all KHG, one row each.

  repeat-national-profile --config configs/examples/national_profile.yaml [--mode validate|operational]
                             [--only KHG.16.02.01 ...] [--out DIR]

Per KHG, from the files in REPEAT_DATA: burned area per year and repeat burns (burnt-area polygons), hotspots per
year with FRP and confidence (FIRMS VIIRS), canal density, existing hydrological structures, target villages, peat
depth coverage. Normalisation, urgency score, tertile classes, weight sensitivity and held-out validation are
common.scoring.score, the same engine as the other programs. Everything normalised by KHG area (the peat area is not
available yet). Writes profile.csv, yearly.csv, profile.gpkg, report.json to the output folder.

`--mode validate` scores on the baseline years and tests against the validation years; `--mode operational` moves
the baseline to the end of the validation years (main() extends it before the indicators are built) and has no held-out test.
"""
from __future__ import annotations

import argparse
import copy
import json
import logging
import os
import re
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import shapely
import shapely.ops
import yaml
from pyproj import Transformer
from rasterio.features import geometry_mask
from rasterio.windows import Window

from repeat_prioritisation.common import scoring as SC  # noqa: E402

log = logging.getLogger("prioritas.profile")

AEA = "+proj=aea +lat_1=-8 +lat_2=4 +lat_0=-2 +lon_0=118 +datum=WGS84 +units=m +no_defs"  # equal area for Indonesia

DEFAULTS = {
    "data": "${REPEAT_DATA}",
    "out": "${REPEAT_WORK}/national_profile",
    "registry": "${REPEAT_HUB}/sites/khg_registry.csv",
    "inputs": {
        "khg": "batas_khg_indonesia.gpkg",
        "burned": "burnt_area_2015_2026_Indonesia.gpkg",
        "hotspots": "hotspot_viirs_snpp_2012_2025.gpkg",
        "canals": "kanal_osgm_khg_existing_Indonesia.gpkg",
        "blocks": "infrastruktur_hidrologis_existing_BRGM_Indonesia.gpkg",
        "villages": "desa_target_pemulihan_ekosistem_gambut.gpkg",
        "dmpg": "dpg/dmpg_villages_sitmat.gpkg",   # DMPG villages of the SiTMAT portal (repeat_common.fetch_sitmat_layers, layer dmpg_villages); context, not scored
        "peat_depth": "kedalaman_gambut_bbsdlp.gpkg",
        "hotspots_now": "hotspots_modis_2026.gpkg",   # MODIS hotspots of the current year: KLH file to its last date, FIRMS NRT after it (investigations.hotspot_splice)
    },
    # current-year hotspots: one schema (month, level low / medium / high, frp, acq_date, source); the KLH months without a
    # date or FRP have them empty, so FRP is never summed across months
    "now": {"levels": ["medium", "high"], "year": 2026},
    "years": {"baseline": [2015, 2022], "validation": [2023, 2025]},
    "hotspots": {"confidence": ["n", "h"], "types": [0]},   # FIRMS VIIRS: l/n/h; type 0 = vegetation fire
    "tma": {"path": None, "kinds": ["concession"], "drop_flags": ["range", "spike"], "threshold_m": 0.4,
            "min_days": 30},   # SiTMAT processed folder; one season only, so reported per KHG, not scored
    "peat": {"extent": None, "global": None, "basis": "peat", "min_peat_km2": 25},   # GFW peat extent GeoTIFF; basis: rates per km2 of peat | of KHG
    "min_area_km2": 10,        # smaller KHG are profiled but not ranked: one hotspot is a huge density
    "indicators": {            # weights of the scored indicators; others are reported only
        "u_fire_freq": {"weight": 2.0},      # mean annual burned share of the KHG
        "u_burn_repeat": {"weight": 1.0},    # share burned two or more times in the baseline
        "u_hotspot": {"weight": 1.0},        # hotspots per km2 per year
        "u_frp": {"weight": 0.0},            # FRP per km2 per year: reported, not scored (rho 0.99 with u_hotspot)
        "u_canal_density": {"weight": 0.0},  # all canals together: reported; the three classes below are scored
        "u_canal_primary": {"weight": 0.5},   # canal km per km2 of KHG by class; the three weights add to 1, the old single canal weight
        "u_canal_secondary": {"weight": 0.3},
        "u_canal_tertiary": {"weight": 0.2},
        "i_peat_depth": {"weight": 0.0},     # coverage incomplete: reported, not scored
        "u_hotspot_now": {"weight": 1.0},    # hotspots this year (KLH, Jan-Sep) per km2 of peat; its own weight, set 0 to drop it
        "u_burned_now": {"weight": 0.0},     # burned share of the peat this year (BA_<year>): reported, not scored
    },
    "scoring": {"alpha_urgency": 0.6, "normalise_quantiles": [0.05, 0.95], "fixed_thresholds": None,
                "correlation_warn": 0.8, "min_units_per_indicator": 20, "sensitivity_runs": 300,
                "sensitivity_concentration": 20, "top_fraction": 0.2, "validation_burn_threshold": 0.05, "seed": 42,
                "normalise_scope": "all", "tidal_mode": "none", "national": True, "top_n": 25},
}
DEPTH_MID_CM = {"50-<100 cm": 75, "100-<200 cm": 150, "200-<300 cm": 250, "300-<500 cm": 400,
                "500-<700 cm": 600, ">700 cm": 800}


def _expand(obj):
    if isinstance(obj, dict):
        return {k: _expand(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_expand(v) for v in obj]
    if isinstance(obj, str) and "${" in obj:
        for m in re.findall(r"\$\{([A-Za-z_]\w*)\}", obj):
            if m not in os.environ:
                raise SystemExit(f"config uses ${{{m}}} but that environment variable is not set")
        return os.path.expandvars(obj)
    return obj


def _merge(base, upd):
    for k, v in (upd or {}).items():
        if isinstance(v, dict) and isinstance(base.get(k), dict):
            _merge(base[k], v)
        else:
            base[k] = v
    return base


def norm_name(s):
    return re.sub(r"\s+", " ", str(s).replace("’", "'")).strip().lower()


def load_khg(cfg, only=None):
    data = Path(cfg["data"])
    khg = pyogrio.read_dataframe(data / cfg["inputs"]["khg"])
    reg = pd.read_csv(cfg["registry"])
    khg["_k"], reg["_k"] = khg["NAMA_KHG"].map(norm_name), reg["name"].map(norm_name)
    khg = khg.merge(reg[["_k", "khg_code", "island", "province", "kabupaten", "area_ha_kepmen"]], on="_k", how="left")
    miss = khg["khg_code"].isna().sum()
    if miss:
        log.warning("%d KHG in the boundary file have no code in the registry: %s", miss, khg.loc[khg.khg_code.isna(), "NAMA_KHG"].tolist())
    khg = khg.rename(columns={"khg_code": "khg_id", "NAMA_KHG": "nama"}).drop(columns="_k")
    khg["geometry"] = shapely.make_valid(khg.geometry.values)
    if only:
        khg = khg[khg.khg_id.isin(only)]
    proj = khg.to_crs(AEA)
    khg["area_km2"] = proj.geometry.area.to_numpy() / 1e6
    khg["geom_aea"] = proj.geometry.values
    return khg.reset_index(drop=True)


_TF_AEA = Transformer.from_crs(4326, AEA, always_xy=True)


def _read_mask(path, geom, **kw):
    return pyogrio.read_dataframe(path, mask=geom, **kw)


class PeatSampler:
    """Peat (1), no peat (0) or tile not fetched (255) from the GFW peat-extent GeoTIFF (Web Mercator, see
    repeat_common.fetch_peat_extent). Reads one KHG window at a time."""

    def __init__(self, path):
        from pyproj import Transformer
        self.src = rasterio.open(path)
        self.tf = Transformer.from_crs(4326, self.src.crs, always_xy=True)

    def window(self, geom_ll):
        b = geom_ll.bounds
        x0, y0 = self.tf.transform(b[0], b[1])
        x1, y1 = self.tf.transform(b[2], b[3])
        w = rasterio.windows.from_bounds(x0, y0, x1, y1, self.src.transform).round_offsets().round_lengths()
        w = Window(w.col_off - 2, w.row_off - 2, w.width + 4, w.height + 4)
        try:
            w = w.intersection(Window(0, 0, self.src.width, self.src.height))
        except rasterio.errors.WindowError:
            return np.full((1, 1), 255, np.uint8), self.src.transform
        return self.src.read(1, window=w), self.src.window_transform(w)

    def sample(self, win, lon, lat):
        arr, tr = win
        x, y = self.tf.transform(np.asarray(lon, float), np.asarray(lat, float))
        col = np.floor((x - tr.c) / tr.a).astype(int)
        row = np.floor((y - tr.f) / tr.e).astype(int)
        ok = (row >= 0) & (row < arr.shape[0]) & (col >= 0) & (col < arr.shape[1])
        val = np.full(len(col), 255, np.uint8)
        val[ok] = arr[row[ok], col[ok]]
        return val

    def fraction(self, win, geom_ll):
        """Share of the KHG's cells that are peat, among the cells that were fetched; and the share fetched."""
        arr, tr = win
        g = shapely.ops.transform(self.tf.transform, geom_ll)
        inside = ~geometry_mask([g], out_shape=arr.shape, transform=tr, all_touched=False)
        if not inside.any():
            return np.nan, 0.0
        v = arr[inside]
        seen = v[v != 255]
        return (float((seen == 1).mean()) if len(seen) else np.nan), float(len(seen) / len(v))


def gpm_table(path, khg):
    """Peat share of each KHG from the 1 km Global Peatland Map 2.0 (1 or 2 = peat; the rest is none), an independent cross-check."""
    rows = []
    with rasterio.open(path) as src:
        for r in khg.itertuples():
            w = rasterio.windows.from_bounds(*r.geometry.bounds, transform=src.transform)
            c0, r0 = int(np.floor(w.col_off)), int(np.floor(w.row_off))
            win = Window(c0, r0, max(int(np.ceil(w.col_off + w.width)) - c0, 1), max(int(np.ceil(w.row_off + w.height)) - r0, 1))
            try:
                win = win.intersection(Window(0, 0, src.width, src.height))
            except rasterio.errors.WindowError:
                rows.append((r.khg_id, np.nan))
                continue
            arr = src.read(1, window=win)
            inside = ~geometry_mask([r.geometry], out_shape=arr.shape, transform=src.window_transform(win), all_touched=False)
            if not inside.any():   # a KHG smaller than a cell: the cell under its centre
                pt = r.geometry.representative_point()
                rr, cc = src.index(pt.x, pt.y)
                v = arr[min(max(int(rr - win.row_off), 0), arr.shape[0] - 1), min(max(int(cc - win.col_off), 0), arr.shape[1] - 1)]
                rows.append((r.khg_id, float(v in (1, 2))))
            else:
                rows.append((r.khg_id, float(np.isin(arr[inside], (1, 2)).mean())))
    return pd.DataFrame(rows, columns=["khg_id", "peat_frac_gpm1km"])


def peat_table(sampler, khg):
    rows = []
    for r in khg.itertuples():
        f, cov = sampler.fraction(sampler.window(r.geometry), r.geometry)
        rows.append((r.khg_id, f, cov))
    t = pd.DataFrame(rows, columns=["khg_id", "peat_frac", "peat_cover_gfw"])
    return t


def burned_by_year(path, khg, years, sampler=None):
    """Per KHG: burned km2 per year, and km2 burned n times within `years`. Polygons are flattened patches that
    carry the list of years they burned (BA_yyyy set when burned), so areas add up without double counting."""
    ycols = [f"BA_{y}" for y in range(2015, 2027)]
    rows, freq = [], []
    for r in khg.itertuples():
        g = _read_mask(path, r.geometry, columns=ycols)
        if g.empty:
            continue
        if sampler is not None:   # a patch counts as peat if its representative point falls on a peat cell
            rp = shapely.get_coordinates(shapely.point_on_surface(shapely.make_valid(g.geometry.values)))
            onpeat_all = sampler.sample(sampler.window(r.geometry), rp[:, 0], rp[:, 1]) == 1
        g = g.to_crs(AEA)
        geom = shapely.make_valid(g.geometry.values)
        inter = shapely.intersection(geom, r.geom_aea)
        a = shapely.area(inter) / 1e6
        keep = a > 0
        flags = g.loc[keep, ycols].notna().to_numpy()
        a = a[keep]
        onp = onpeat_all[keep] if sampler is not None else np.zeros(len(a), bool)
        for j, c in enumerate(ycols):
            if flags[:, j].any():
                rows.append((r.khg_id, int(c[3:]), float(a[flags[:, j]].sum()), float(a[flags[:, j] & onp].sum())))
        win = [j for j, c in enumerate(ycols) if years[0] <= int(c[3:]) <= years[1]]
        n = flags[:, win].sum(axis=1)
        freq.append((r.khg_id, float(a[n >= 1].sum()), float(a[n >= 2].sum()), float(a[n >= 3].sum()),
                     float(a[(n >= 1) & onp].sum()), float(a[(n >= 2) & onp].sum())))
    yearly = pd.DataFrame(rows, columns=["khg_id", "year", "burned_km2", "burned_peat_km2"])
    freq = pd.DataFrame(freq, columns=["khg_id", "burned_ge1_km2", "burned_ge2_km2", "burned_ge3_km2",
                                       "burned_ge1_peat_km2", "burned_ge2_peat_km2"])
    return yearly, freq


def hotspots_by_year(path, khg, hcfg, sampler=None):
    """Per KHG and year: detections kept (type, confidence filter), FRP sum, high-confidence count, all vegetation-fire
    detections. Point-in-polygon on the WGS84 boundary."""
    pts = pyogrio.read_dataframe(path, columns=["year", "confidence", "type", "frp"])
    log.info("hotspots read: %d points", len(pts))
    pts = pts[pts["type"].isin(hcfg["types"])]
    j = gpd.sjoin(pts, khg[["khg_id", "geometry"]], how="inner", predicate="within")
    j["conf"] = j["confidence"].astype(str).str.lower()
    j["keep"] = j["conf"].isin([c.lower() for c in hcfg["confidence"]])
    j["peat"] = False
    if sampler is not None:
        geoms = khg.set_index("khg_id").geometry
        px, py = j.geometry.x.to_numpy(), j.geometry.y.to_numpy()
        peat = np.zeros(len(j), bool)
        for kid, idx in j.groupby("khg_id").indices.items():
            peat[idx] = sampler.sample(sampler.window(geoms[kid]), px[idx], py[idx]) == 1
        j["peat"] = peat
    j["keep_peat"] = j["keep"] & j["peat"]
    g = j.groupby(["khg_id", "year"])
    out = pd.DataFrame({"n_all": g.size(),
                        "n_hotspot": g["keep"].sum(),
                        "n_high": g.apply(lambda d: (d["conf"] == "h").sum(), include_groups=False),
                        "frp_sum": g.apply(lambda d: d.loc[d["keep"], "frp"].sum(), include_groups=False),
                        "n_hotspot_peat": g["keep_peat"].sum(),
                        "frp_sum_peat": g.apply(lambda d: d.loc[d["keep_peat"], "frp"].sum(), include_groups=False)}).reset_index()
    return out


LEVEL = {"rendah": "low", "low": "low", "sedang": "medium", "medium": "medium", "tinggi": "high", "high": "high"}


def hotspots_now(path, khg, ncfg, sampler=None):
    """Current-year hotspots (KLH-curated MODIS, one layer per month) per KHG and month: kept (level filter), kept on peat,
    high-confidence on peat, and FRP where the month has it (4 of 9 months do, so FRP is never summed across months)."""
    pts = pyogrio.read_dataframe(path, layer="hotspots", columns=["month", "level", "frp", "acq_date"])
    pts["keep"] = pts["level"].isin(ncfg["levels"])
    j = gpd.sjoin(pts, khg[["khg_id", "geometry"]], how="inner", predicate="within")
    j["peat"] = False
    if sampler is not None:
        geoms = khg.set_index("khg_id").geometry
        px, py = j.geometry.x.to_numpy(), j.geometry.y.to_numpy()
        peat = np.zeros(len(j), bool)
        for kid, idx in j.groupby("khg_id").indices.items():
            peat[idx] = sampler.sample(sampler.window(geoms[kid]), px[idx], py[idx]) == 1
        j["peat"] = peat
    j["kp"] = j["keep"] & j["peat"]
    j["hp"] = j["kp"] & (j["level"] == "high")
    j["has_frp"] = j["frp"].notna()
    g = j.groupby(["khg_id", "month"])
    out = pd.DataFrame({"n_kept": g["keep"].sum(), "n_kept_peat": g["kp"].sum(), "n_high_peat": g["hp"].sum(),
                        "n_frp_peat": g.apply(lambda d: (d["kp"] & d["has_frp"]).sum(), include_groups=False),
                        "frp_sum_peat": g.apply(lambda d: d.loc[d["kp"] & d["has_frp"], "frp"].sum(), include_groups=False)}).reset_index()
    last = pd.to_datetime(pts["acq_date"], errors="coerce").max()
    return out, {"last_date": None if pd.isna(last) else str(last.date()), "n_points": int(len(pts)),
                 "n_kept": int(pts["keep"].sum()), "months": sorted(pts["month"].unique().tolist())}


CANAL_CLASS = {"1": "primary", "2": "secondary", "3": "tertiary"}   # KODE_KANAL: Kanal Primer, Sekunder, Tersier


def canal_length(path, khg):
    """Canal km inside each KHG, total and by class (primary, secondary, tertiary), and the number of segments."""
    rows = []
    for r in khg.itertuples():
        g = _read_mask(path, r.geometry, columns=["KODE_KANAL"])
        if g.empty:
            rows.append((r.khg_id, 0.0, 0, 0.0, 0.0, 0.0))
            continue
        g = g.to_crs(AEA)
        km = shapely.length(shapely.intersection(shapely.make_valid(g.geometry.values), r.geom_aea)) / 1000
        code = g["KODE_KANAL"].astype(str).to_numpy()
        rows.append((r.khg_id, float(km.sum()), len(g), *(float(km[code == k].sum()) for k in ("1", "2", "3"))))
    return pd.DataFrame(rows, columns=["khg_id", "canal_km", "canal_segments", "canal_km_primary", "canal_km_secondary", "canal_km_tertiary"])


def dmpg_stats(path, khg):
    """DMPG villages (SiTMAT layer `dmpg_villages`) per KHG: the number whose representative point lies inside (n_dmpg) and the
    village land inside the KHG in km2 (dmpg_km2, equal-area, polygons do not overlap each other)."""
    v = pyogrio.read_dataframe(path, layer="dmpg_villages", columns=[])
    v = v[v.geometry.notna()].copy()
    v["geometry"] = shapely.make_valid(v.geometry.values)
    n = gpd.sjoin(gpd.GeoDataFrame(geometry=v.representative_point(), crs=v.crs), khg[["khg_id", "geometry"]], how="inner", predicate="within")
    n = n.groupby("khg_id").size().rename("n_dmpg")
    tree, geoms = shapely.STRtree(v.geometry.values), v.geometry.values
    rows = []
    for r in khg.itertuples():
        hit = tree.query(r.geometry, predicate="intersects")
        if len(hit):
            inter = shapely.intersection(geoms[hit], shapely.make_valid(r.geometry))
            km2 = float(shapely.area(shapely.transform(inter, lambda c: np.column_stack(_TF_AEA.transform(c[:, 0], c[:, 1])))).sum() / 1e6)
            rows.append((r.khg_id, km2))
    a = pd.DataFrame(rows, columns=["khg_id", "dmpg_km2"])
    return n.reset_index().merge(a, on="khg_id", how="outer")


def count_inside(path, khg, name, rep="point", ids=None):
    g = pyogrio.read_dataframe(path, columns=[] if ids is None else ["OBJECTID"])
    g = g[g.geometry.notna()]
    if ids is not None:
        g = g[g["OBJECTID"].isin(ids)]
    if rep == "centroid":
        g = gpd.GeoDataFrame(geometry=g.representative_point(), crs=g.crs)
    j = gpd.sjoin(g, khg[["khg_id", "geometry"]], how="inner", predicate="within")
    return j.groupby("khg_id").size().rename(name).reset_index()


def peat_depth(path, khg):
    rows = []
    for r in khg.itertuples():
        g = _read_mask(path, r.geometry, columns=["KELAS_GBT"])
        if g.empty:
            continue
        g = g.to_crs(AEA)
        a = shapely.area(shapely.intersection(shapely.make_valid(g.geometry.values), r.geom_aea)) / 1e6
        mid = g["KELAS_GBT"].map(DEPTH_MID_CM).to_numpy(dtype=float)
        ok = (a > 0) & np.isfinite(mid)
        if ok.any():
            rows.append((r.khg_id, float(a[ok].sum()), float(np.average(mid[ok], weights=a[ok]))))
    return pd.DataFrame(rows, columns=["khg_id", "peat_depth_km2", "peat_depth_mean_cm"])


def tma_by_khg(tcfg, khg):
    """Per KHG: SiTMAT stations inside, and the share of days the water table was deeper than threshold_m (mean over
    stations with at least min_days valid readings). Same cleaning as repeat_common.tma: QC flags dropped, stations
    without a valid location dropped. The SiTMAT record is one season, so this is a snapshot, not a baseline."""
    folder = Path(tcfg["path"])
    d = pd.read_csv(folder / "daily_long.csv", usecols=["kind", "station_id", "date", "water_level_cm", "flag"],
                    dtype={"flag": "string"})
    d = d[d["kind"].isin(tcfg["kinds"]) & d["water_level_cm"].notna() & ~d["flag"].isin(tcfg["drop_flags"])]
    st = pd.read_csv(folder / "stations.csv", usecols=["kind", "station_id", "lon", "lat"])
    geo = pd.read_csv(folder / "stations_geo.csv", usecols=["kind", "station_id", "has_loc"])
    st = st.merge(geo, on=["kind", "station_id"], how="left")
    st = st[(st["has_loc"].fillna(1) == 1) & st.lon.between(94, 142) & st.lat.between(-12, 7) & (st.lon != st.lat)]
    d = d.merge(st[["kind", "station_id", "lon", "lat"]], on=["kind", "station_id"])
    d["deep"] = (-d["water_level_cm"] / 100.0 > tcfg["threshold_m"]).astype(float)
    s = d.groupby(["kind", "station_id", "lon", "lat"]).agg(days=("deep", "size"), deep=("deep", "mean"),
                                                            first=("date", "min"), last=("date", "max")).reset_index()
    s = s[s["days"] >= tcfg["min_days"]]
    pts = gpd.GeoDataFrame(s, geometry=gpd.points_from_xy(s.lon, s.lat), crs=4326)
    j = gpd.sjoin(pts, khg[["khg_id", "geometry"]], how="inner", predicate="within")
    out = j.groupby("khg_id").agg(n_tma_stations=("deep", "size"), tma_deep_share=("deep", "mean"),
                                  tma_period_start=("first", "min"), tma_period_end=("last", "max")).reset_index()
    return out


def build_profile(cfg, only=None, khg=None):
    """khg: polygons to profile instead of the national KHG (columns khg_id, geometry in EPSG:4326, area_km2, geom_aea),
    for example the sub-KHG units of one KHG (subkhg.national_layers), so both levels count fire and canals the same way."""
    data, inp = Path(cfg["data"]), cfg["inputs"]
    yb, yv = cfg["years"]["baseline"], cfg["years"]["validation"]
    khg = load_khg(cfg, only) if khg is None else khg
    log.info("%d KHG", len(khg))
    p = lambda k: data / inp[k]

    pcfg = cfg["peat"]
    sampler = PeatSampler(pcfg["extent"]) if pcfg.get("extent") and Path(pcfg["extent"]).exists() else None
    use_peat = sampler is not None and pcfg["basis"] == "peat"
    if pcfg.get("extent") and sampler is None:
        log.warning("peat extent %s not found: rates are per km2 of KHG", pcfg["extent"])
    yearly_b, freq = burned_by_year(p("burned"), khg, yb, sampler)
    hs = hotspots_by_year(p("hotspots"), khg, cfg["hotspots"], sampler)
    peatx = peat_table(sampler, khg) if sampler is not None else None
    if peatx is not None and pcfg.get("global") and Path(pcfg["global"]).exists():
        peatx = peatx.merge(gpm_table(pcfg["global"], khg), on="khg_id", how="left")
    now, now_meta = (hotspots_now(p("hotspots_now"), khg, cfg["now"], sampler)
                     if inp.get("hotspots_now") and p("hotspots_now").exists() else (None, None))
    canals = canal_length(p("canals"), khg)
    blocks = count_inside(p("blocks"), khg, "n_infra_ada")
    desa = count_inside(p("villages"), khg, "n_desa_target", rep="centroid")
    dmpg = dmpg_stats(p("dmpg"), khg) if inp.get("dmpg") and p("dmpg").exists() else None      # its own table: KHG inside a village have no target villages
    peat = peat_depth(p("peat_depth"), khg)
    tma = tma_by_khg(cfg["tma"], khg) if cfg["tma"].get("path") else None

    prof = khg.drop(columns=["geom_aea"]).copy()
    for t in (freq, canals, blocks, desa, dmpg, peat, tma, peatx):
        if t is not None:
            prof = prof.merge(t, on="khg_id", how="left")
    if tma is not None:
        prof["n_tma_stations"] = prof["n_tma_stations"].fillna(0)
    for c in ("burned_ge1_km2", "burned_ge2_km2", "burned_ge3_km2", "canal_km", "canal_segments", "canal_km_primary", "canal_km_secondary", "canal_km_tertiary", "n_infra_ada", "n_desa_target", "n_dmpg", "dmpg_km2"):
        if c in prof:
            prof[c] = prof[c].fillna(0)
    A = prof["area_km2"]
    if sampler is not None:
        prof["peat_km2"] = prof["area_km2"] * prof["peat_frac"]
    D = prof["peat_km2"].where(prof["peat_km2"] > 0) if use_peat else A       # denominator of the rates
    prof["basis"] = "peat" if use_peat else "area"
    nb = yb[1] - yb[0] + 1
    nv = yv[1] - yv[0] + 1

    piv = lambda t, col: t.pivot(index="khg_id", columns="year", values=col).reindex(prof.khg_id).fillna(0)
    by_all, hy_all, fy_all = piv(yearly_b, "burned_km2"), piv(hs, "n_hotspot"), piv(hs, "frp_sum")
    by, hy, fy = (piv(yearly_b, "burned_peat_km2"), piv(hs, "n_hotspot_peat"), piv(hs, "frp_sum_peat")) if use_peat else (by_all, hy_all, fy_all)
    span = lambda t, y0, y1: t[[y for y in t.columns if y0 <= y <= y1]]
    ge1, ge2 = ("burned_ge1_peat_km2", "burned_ge2_peat_km2") if use_peat else ("burned_ge1_km2", "burned_ge2_km2")
    prof["u_fire_freq"] = (span(by, *yb).sum(axis=1).to_numpy() / nb) / D
    prof["u_burn_repeat"] = prof[ge2] / D
    prof["burned_ever_frac"] = prof[ge1] / D
    prof["u_hotspot"] = span(hy, *yb).sum(axis=1).to_numpy() / nb / D
    prof["u_frp"] = span(fy, *yb).sum(axis=1).to_numpy() / nb / D
    # the same rates per km2 of KHG, all land, for comparison with the peat basis
    prof["u_fire_freq_area"] = (span(by_all, *yb).sum(axis=1).to_numpy() / nb) / A
    prof["u_burn_repeat_area"] = prof["burned_ge2_km2"] / A
    prof["u_hotspot_area"] = span(hy_all, *yb).sum(axis=1).to_numpy() / nb / A
    n_tot = span(hy, *yb).sum(axis=1).to_numpy()
    prof["frp_mean_mw"] = np.where(n_tot > 0, span(fy, *yb).sum(axis=1).to_numpy() / np.maximum(n_tot, 1), np.nan)
    hcols = ["n_hotspot", "n_high", "n_all"] + (["n_hotspot_peat"] if use_peat else [])
    hb = hs[hs.year.between(*yb)].groupby("khg_id")[hcols].sum()
    hb = hb.rename(columns={"n_hotspot": "hs_kept_baseline", "n_high": "hs_high_baseline", "n_all": "hs_all_baseline",
                            "n_hotspot_peat": "hs_peat_baseline"})
    prof = prof.merge(hb, on="khg_id", how="left")
    if use_peat:   # high-confidence share is among all kept detections of the KHG
        pass
    prof["hs_high_share"] = prof["hs_high_baseline"] / prof["hs_kept_baseline"].replace(0, np.nan)
    if now is not None:
        tot = now.groupby("khg_id")[["n_kept", "n_kept_peat", "n_high_peat", "n_frp_peat", "frp_sum_peat"]].sum().reindex(prof.khg_id).fillna(0)
        kept = tot["n_kept_peat"].to_numpy() if use_peat else tot["n_kept"].to_numpy()
        prof["hs_now_kept"] = tot["n_kept_peat"].to_numpy() if use_peat else tot["n_kept"].to_numpy()
        prof["u_hotspot_now"] = kept / D
        prof["u_hotspot_now_area"] = tot["n_kept"].to_numpy() / A
        prof["hs_now_high_share"] = np.where(kept > 0, tot["n_high_peat"].to_numpy() / np.maximum(kept, 1), np.nan)
        prof["frp_now_mean_mw"] = np.where(tot["n_frp_peat"].to_numpy() > 0, tot["frp_sum_peat"].to_numpy() / np.maximum(tot["n_frp_peat"].to_numpy(), 1), np.nan)
        ycur = cfg["now"]["year"]
        if ycur in by.columns:
            prof["u_burned_now"] = by[ycur].to_numpy() / D
    # no canal in the layer = not mapped (OSM-derived, patchy), not "no canals": leave it missing so it is not scored
    mapped = prof["canal_segments"] > 0
    prof["u_canal_density"] = (prof["canal_km"] / A).where(mapped)
    for cls in ("primary", "secondary", "tertiary"):
        prof[f"u_canal_{cls}"] = (prof[f"canal_km_{cls}"] / A).where(mapped)
    prof["i_peat_depth"] = prof["peat_depth_mean_cm"] / 100        # m, only where the peat map covers the KHG
    prof["peat_cover_frac"] = (prof["peat_depth_km2"] / A).clip(upper=1)
    prof["v_burned_frac"] = (span(by, *yv).sum(axis=1).to_numpy() / nv) / D
    prof["v_hotspot"] = span(hy, *yv).sum(axis=1).to_numpy() / nv / D
    prof["n_years_baseline"] = nb
    # data confidence of the profile of this KHG: canal layer present, enough fire signal to see a rate, size
    size_ok = (prof["peat_km2"].fillna(0) >= pcfg["min_peat_km2"]) if use_peat else (A >= 50)
    ok = [prof["canal_segments"] > 0, (prof["hs_kept_baseline"].fillna(0) >= 30) | (prof["burned_ge1_km2"] > 0), size_ok]
    prof["conf_score"] = sum(c.astype(int) for c in ok)
    prof["confidence"] = prof["conf_score"].map({3: "tinggi", 2: "sedang"}).fillna("rendah")

    yearly = pd.concat([yearly_b.melt(id_vars=["khg_id", "year"], value_vars=["burned_km2", "burned_peat_km2"], var_name="metric", value_name="value"),
                        hs.melt(id_vars=["khg_id", "year"], value_vars=["n_hotspot", "n_high", "frp_sum", "n_hotspot_peat", "frp_sum_peat"],
                                var_name="metric", value_name="value")], ignore_index=True)
    if now is not None:
        m = now.melt(id_vars=["khg_id", "month"], value_vars=["n_kept", "n_kept_peat"], var_name="metric", value_name="value")
        m["metric"] = "hs_now_" + m["metric"].str.replace("n_kept_peat", "peat").str.replace("n_kept", "all") + "_m" + m["month"].astype(str).str.zfill(2)
        m["year"] = cfg["now"]["year"]
        yearly = pd.concat([yearly, m[["khg_id", "year", "metric", "value"]]], ignore_index=True)
    prof.attrs["now_meta"] = now_meta
    return prof, yearly


def rank(prof, cfg, mode):
    cfg = copy.deepcopy(cfg)
    use_peat = "basis" in prof and (prof["basis"] == "peat").all()
    elig = (prof["area_km2"] >= cfg["min_area_km2"]) & ((prof["peat_km2"].fillna(0) >= cfg["peat"]["min_peat_km2"]) if use_peat else True)
    df = prof[elig].copy()
    sc_cfg = {"scoring": cfg["scoring"], "indicators": copy.deepcopy(cfg["indicators"])}
    if mode == "validate":   # the current year is after the held-out years: scoring on it would use the future
        for k in ("u_hotspot_now", "u_burned_now"):
            sc_cfg["indicators"][k] = {"weight": 0.0}
    if mode == "operational":
        for c in ("v_burned_frac", "v_hotspot"):
            df[c] = np.nan
    runs = int(sc_cfg["scoring"]["sensitivity_runs"])
    sc_cfg["scoring"]["sensitivity_runs"] = 0           # the engine's own sensitivity assumes risk x feasibility classes
    out, report = SC.score(df, sc_cfg)
    if runs:
        spec, _ = SC.resolve_weights(sc_cfg)
        sc = {**sc_cfg["scoring"], "sensitivity_runs": runs}
        norm = SC.normalise_scoped(df, spec, sc)
        out, report["sensitivity"] = SC.sensitivity(out, norm, spec, sc, p_col="p_fokus_tinggi",
                                                    high_fn=lambda r, f: r >= r.quantile(2 / 3))
    if use_peat:   # the same ranking with rates per km2 of KHG, to show what the peat basis changes
        d2 = df.copy()
        for c in ("u_fire_freq", "u_burn_repeat", "u_hotspot", "u_hotspot_now"):
            if c + "_area" in d2:
                d2[c] = d2[c + "_area"]
        cfg2 = {"scoring": {**sc_cfg["scoring"], "sensitivity_runs": 0}, "indicators": sc_cfg["indicators"]}
        o2, _ = SC.score(d2, cfg2)
        out["peringkat_area"] = out["khg_id"].map(o2.set_index("khg_id")["peringkat"])
    if "u_hotspot_now" in out:   # standalone ranking on this year's hotspots only (ties share the lower rank)
        out["peringkat_now"] = out["u_hotspot_now"].rank(ascending=False, method="min")           # by density (per km2 of peat)
        out["peringkat_now_n"] = out["hs_now_kept"].rank(ascending=False, method="min")           # by number of hotspots
        report["now"] = {"weight": sc_cfg["indicators"].get("u_hotspot_now", {}).get("weight"), **(prof.attrs.get("now_meta") or {})}
    report["n_ranked"], report["n_profiled"] = int(elig.sum()), int(len(prof))
    report["mode"] = mode
    # tertiles by rank, not by value: a third of the KHG have zero fire signal and tie at the bottom
    pos = out["skor_risiko"].rank(method="first", ascending=False)
    n = len(out)
    out["kelas"] = np.where(out["skor_risiko"] <= 0, SC.KHG_CLASSES[2],
                            np.where(pos <= n / 3, SC.KHG_CLASSES[0], np.where(pos <= 2 * n / 3, SC.KHG_CLASSES[1], SC.KHG_CLASSES[2])))
    report["class_counts"] = out["kelas"].value_counts().to_dict()
    small = prof[~elig].assign(kelas="Tidak diperingkat (KHG kecil)")
    return pd.concat([out, small], ignore_index=True), report


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config")
    ap.add_argument("--mode", choices=["validate", "operational"], default="validate")
    ap.add_argument("--only", nargs="*")
    ap.add_argument("--out")
    ap.add_argument("--print-default-config", action="store_true")
    a = ap.parse_args(argv)
    if a.print_default_config:
        print(yaml.safe_dump(DEFAULTS, sort_keys=False, allow_unicode=True))
        return
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(message)s", datefmt="%H:%M:%S")
    cfg = copy.deepcopy(DEFAULTS)
    if a.config:
        _merge(cfg, yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    cfg = _expand(cfg)
    if a.mode == "operational":   # the indicators themselves run to the end of the validation years
        cfg["years"]["baseline"] = [cfg["years"]["baseline"][0], cfg["years"]["validation"][1]]
    out_dir = Path(a.out or cfg["out"]) / a.mode
    out_dir.mkdir(parents=True, exist_ok=True)

    prof, yearly = build_profile(cfg, a.only)
    ranked, report = rank(prof, cfg, a.mode)
    ranked.drop(columns="geometry").to_csv(out_dir / "profile.csv", index=False, encoding="utf-8")
    yearly.to_csv(out_dir / "yearly.csv", index=False, encoding="utf-8")
    gpd.GeoDataFrame(ranked, geometry="geometry", crs=4326).to_file(out_dir / "profile.gpkg", driver="GPKG")
    report["config"] = {k: cfg[k] for k in ("years", "hotspots", "min_area_km2", "indicators", "scoring", "tma", "peat")}
    report["inputs"] = {k: str(Path(cfg["data"]) / v) for k, v in cfg["inputs"].items()}
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, default=str, ensure_ascii=False), encoding="utf-8")
    log.info("written to %s", out_dir)
    log.info("classes: %s", report.get("class_counts"))


if __name__ == "__main__":
    main()
