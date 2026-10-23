#!/usr/bin/env python3
"""Fire near an airport and the KHG around it: one self-contained HTML report.

  python -m investigations.airport --config configs/investigations/banjarbaru.yaml

Puts the runway against the KHG boundary (KLHK FEG 1:50,000 layer, which carries KHG set after SK.129/2017), the peat under it
(FEG peat soil, the GFW composite extent and the 1 km Global Peatland Map), the fire record (FIRMS VIIRS 2012 to 2025, KLH 2026
hotspots, burned area 2015 to 2026) and the airport's own weather reports (METAR: visibility, smoke, wind). Each hotspot and
burned patch is split three ways: inside the KHG on peat soil, inside the KHG on mineral soil, outside the KHG. Inputs are named
in the config; the fetchers are in repeat_common (fetch_klhk_peat, fetch_peat_extent --extra, fetch_metar).
Template and script: investigations/assets/. D3 and MapLibre come from national/assets; the basemap loads from the internet.
"""
from __future__ import annotations

import argparse
import base64
import io
import json
import sys
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
import yaml
from PIL import Image
from rasterio.features import geometry_mask
from rasterio.mask import mask as rmask
from rasterio.warp import Resampling, calculate_default_transform, reproject

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from national import profile as P  # noqa: E402

ASSETS = Path(__file__).resolve().parent / "assets"
NAT = ROOT / "national" / "assets"
UTM = 32750          # WGS 84 / UTM 50S: metres for distances and areas around Banjarbaru
WITA = 8             # local time, UTC+8: days are local days
SECT = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
ZONES = ["peat", "mineral", "outside"]


def r4(x):
    return round(float(x), 4)


def rings(geom, tol=0.0):
    g = geom.simplify(tol, preserve_topology=True) if tol else geom
    polys = list(g.geoms) if g.geom_type == "MultiPolygon" else [g] if g.geom_type == "Polygon" else \
        [p for p in getattr(g, "geoms", []) if p.geom_type == "Polygon"]
    return [[[[r4(x), r4(y)] for x, y in r.coords] for r in [p.exterior, *p.interiors]] for p in polys if not p.is_empty]


def fc(rows):
    """[(geometry, props)] -> GeoJSON FeatureCollection with rounded coordinates."""
    feats = []
    for g, p in rows:
        if g is None or g.is_empty:
            continue
        if g.geom_type in ("Polygon", "MultiPolygon", "GeometryCollection"):
            geom = {"type": "MultiPolygon", "coordinates": rings(g)}
        elif g.geom_type == "Point":
            geom = {"type": "Point", "coordinates": [r4(g.x), r4(g.y)]}
        else:
            parts = list(g.geoms) if g.geom_type.startswith("Multi") else [g]
            geom = {"type": "MultiLineString", "coordinates": [[[r4(x), r4(y)] for x, y in l.coords] for l in parts]}
        feats.append({"type": "Feature", "geometry": geom, "properties": p})
    return {"type": "FeatureCollection", "features": feats}


def bearing_sector(dx, dy):
    b = (np.degrees(np.arctan2(dx, dy)) + 360) % 360
    return ((b + 22.5) // 45).astype(int) % 8


def classify(pts, khg_u, peat_u, gfw, runway_u, centre_u):
    """Zone (peat / mineral / outside), GFW peat flag, distance to the runway (km) and bearing sector from the runway centre."""
    u = pts.to_crs(UTM)
    inside = u.within(khg_u)
    onpeat = u.within(peat_u)
    dx, dy = u.geometry.x - centre_u.x, u.geometry.y - centre_u.y
    pts = pts.assign(zone=np.where(inside & onpeat, "peat", np.where(inside, "mineral", "outside")),
                     d_km=u.distance(runway_u).to_numpy() / 1000, sector=bearing_sector(dx, dy),
                     brg=((np.degrees(np.arctan2(dx, dy)) + 360) % 360).to_numpy())
    win = gfw.window(pts.union_all().envelope.buffer(0.01))
    pts["gfw"] = gfw.sample(win, pts.geometry.x.to_numpy(), pts.geometry.y.to_numpy()) == 1
    pts["zone_gfw"] = np.where(inside & pts["gfw"], "peat", np.where(inside, "mineral", "outside"))   # same split on the GFW peat map
    return pts


def ring_of(d, rk):
    edges = [0, *rk]
    out = np.full(len(d), None, object)
    for a, b in zip(edges[:-1], edges[1:]):
        out[(d > a) & (d <= b)] = f"{a}-{b}"
    return out


def gfw_png(path, extent):
    """GFW peat cells inside the map extent as a transparent PNG in EPSG:4326 (MapLibre image source)."""
    with rasterio.open(path) as src:
        geom = [shapely.geometry.mapping(shapely.box(*extent))]
        from rasterio.warp import transform_geom
        a, tr = rmask(src, [transform_geom(4326, src.crs, geom[0])], crop=True, filled=True, nodata=255)
        a = a[0]
        dt, w, h = calculate_default_transform(src.crs, 4326, a.shape[1], a.shape[0],
                                               *rasterio.transform.array_bounds(a.shape[0], a.shape[1], tr))
        dst = np.full((h, w), 255, np.uint8)
        reproject(a, dst, src_transform=tr, src_crs=src.crs, dst_transform=dt, dst_crs=4326, resampling=Resampling.nearest,
                  src_nodata=255, dst_nodata=255)
    rgba = np.zeros((h, w, 4), np.uint8)
    rgba[dst == 1] = (165, 134, 96, 255)            # --peat
    buf = io.BytesIO()
    Image.fromarray(rgba, "RGBA").save(buf, "PNG", optimize=True)
    west, south, east, north = rasterio.transform.array_bounds(h, w, dt)
    return {"url": "data:image/png;base64," + base64.b64encode(buf.getvalue()).decode(),
            "coords": [[r4(west), r4(north)], [r4(east), r4(north)], [r4(east), r4(south)], [r4(west), r4(south)]]}


def gpm_share(path, geom_ll):
    """Share of 1 km cells inside the polygon that are peat (1 dominated, 2 in a mosaic; 255 is none, not missing data)."""
    with rasterio.open(path) as src:
        a, tr = rmask(src, [shapely.geometry.mapping(geom_ll)], crop=True, filled=True, nodata=255)
        inside = ~geometry_mask([geom_ll], out_shape=a.shape[1:], transform=tr)
    v = a[0][inside]
    return float(np.isin(v, (1, 2)).mean()) if len(v) else float("nan")


def gfw_share(path, geom_ll):
    with rasterio.open(path) as src:
        from rasterio.warp import transform_geom
        a, _ = rmask(src, [transform_geom(4326, src.crs, shapely.geometry.mapping(geom_ll))], crop=True, filled=False)
    v = a[0].compressed()
    v = v[v != 255]
    return float((v == 1).mean()) if len(v) else float("nan")


def gfw_nearest_km(path, line_u, within_km=30):
    """Distance from a line (UTM 50S) to the nearest GFW peat cell centre, searched within `within_km`."""
    from pyproj import Transformer
    from rasterio.warp import transform_geom
    zone = gpd.GeoSeries([line_u.buffer(within_km * 1000)], crs=UTM).to_crs(4326).iloc[0]
    with rasterio.open(path) as src:
        a, tr = rmask(src, [transform_geom(4326, src.crs, shapely.geometry.mapping(zone))], crop=True, filled=True, nodata=255)
        rows, cols = np.nonzero(a[0] == 1)
        xs, ys = rasterio.transform.xy(tr, rows, cols)
        x, y = Transformer.from_crs(src.crs, UTM, always_xy=True).transform(np.asarray(xs), np.asarray(ys))
    return float(shapely.distance(shapely.points(x, y), line_u).min() / 1000) if len(x) else None


def build(cfg):
    D = Path(cfg["data"])
    rk = cfg["rings_km"]
    ext = cfg["extent"]
    k = cfg["khg"]
    runway = shapely.LineString(cfg["airport"]["runway"])
    rw_u = gpd.GeoSeries([runway], crs=4326).to_crs(UTM).iloc[0]
    ctr_u = rw_u.interpolate(0.5, normalized=True)
    ring_geoms = {r: gpd.GeoSeries([rw_u.buffer(r * 1000)], crs=UTM).to_crs(4326).iloc[0] for r in rk}

    # --- KHG and peat ---------------------------------------------------------------------------------------------
    khg_all = gpd.read_file(D / k["layer"], layer="khg")
    khg = khg_all[khg_all["kode_khg"] == k["code"]]
    if khg.empty:
        raise SystemExit(f"{k['code']} not in {k['layer']}")
    khg_ll = shapely.make_valid(khg.union_all())
    khg_u = gpd.GeoSeries([khg_ll], crs=4326).to_crs(UTM).iloc[0]
    feg = gpd.read_file(D / k["layer"], layer="feg_50k")
    feg = feg[feg["kode_khg"] == k["code"]].copy()
    feg_u = feg.to_crs(UTM)
    feg["ha"] = feg_u.area / 1e4
    feg["d_km"] = feg_u.distance(rw_u) / 1000
    peat = feg[feg["tnh_gambut"].str.lower().str.contains("tanah gambut", na=False)]
    peat_u = shapely.make_valid(peat.to_crs(UTM).union_all()) if len(peat) else shapely.Polygon()
    old = gpd.read_file(D / k["old_basis"], bbox=(ext[0] - 1, ext[1] - 1, ext[2] + 1, ext[3] + 1)).to_crs(UTM)
    old_near = old.assign(d_km=old.distance(rw_u) / 1000).sort_values("d_km")

    gfw_path = Path(cfg["data"]) / "peat_extent_gfw_v20230315_z11.tif"
    gpm_path = Path(cfg["data"]) / "peat_extent_gpm2022_1km.tif"
    gfw = P.PeatSampler(gfw_path)
    peat_by_thick = feg.groupby("peat_thick")["ha"].sum().round(1).to_dict()
    ring_peat = []
    for r in rk:
        rg = ring_geoms[r]
        rg_u = gpd.GeoSeries([rg], crs=4326).to_crs(UTM).iloc[0]
        ring_peat.append({"km": r, "area_ha": round(rg_u.area / 1e4), "feg_peat_ha": round(rg_u.intersection(peat_u).area / 1e4),
                          "khg_ha": round(rg_u.intersection(khg_u).area / 1e4), "khg_mineral_ha": round(rg_u.intersection(khg_u).difference(peat_u).area / 1e4),
                          "outside_ha": round(rg_u.difference(khg_u).area / 1e4),
                          "gfw_share": round(gfw_share(gfw_path, rg), 3), "gpm_share": round(gpm_share(gpm_path, rg), 3)})
        gp = round(gfw_share(gfw_path, rg.intersection(khg_ll)) * ring_peat[-1]["khg_ha"])
        ring_peat[-1].update(gfw_peat_ha=gp, gfw_nonpeat_ha=ring_peat[-1]["khg_ha"] - gp)
    brgm = gpd.read_file(D / "infrastruktur_hidrologis_existing_BRGM_Indonesia.gpkg", bbox=tuple(ext)).to_crs(4326)
    brgm_u = brgm.to_crs(UTM)
    brgm = brgm.assign(inside=brgm_u.within(khg_u).to_numpy(), d_km=(brgm_u.distance(rw_u) / 1000).to_numpy())
    named = brgm[brgm["KHG"].astype(str).str.contains("Maluka", case=False)]
    nowpts = gpd.read_file(D / P.DEFAULTS["inputs"]["hotspots_now"], bbox=tuple(ext))
    kab_in = nowpts[nowpts.to_crs(UTM).within(khg_u)]["KABKO_2023"].value_counts().to_dict()

    facts = {
        "khg_ha": round(khg_u.area / 1e4, 1), "khg_ha_sk": k["area_ha_sk"],
        "feg_n": int(len(feg)), "feg_peat_ha": round(float(peat["ha"].sum()), 1),
        "feg_mineral_ha": round(float(feg["ha"].sum() - peat["ha"].sum()), 1),
        "feg_lindung_ha": round(float(feg.loc[feg["feg_50k"].str.contains("Lindung", na=False), "ha"].sum()), 1),
        "peat_by_thick": peat_by_thick,
        "gfw_share_khg": round(gfw_share(gfw_path, khg_ll), 3), "gpm_share_khg": round(gpm_share(gpm_path, khg_ll), 3),
        "runway_m": round(rw_u.length), "runway_in_khg_m": round(rw_u.intersection(khg_u).length),
        "runway_to_peat_km": round(float(peat.to_crs(UTM).distance(rw_u).min() / 1000), 2) if len(peat) else None,
        "old_nearest": {"name": str(old_near.iloc[0]["NAMA_KHG"]), "d_km": round(float(old_near.iloc[0]["d_km"]), 1)} if len(old_near) else None,
        "old_has_code": bool((khg_all["kode_khg"] == k["code"]).any()),
        "brgm_named": int(len(named)), "brgm_named_inside": int(named["inside"].sum()),
        "brgm_named_desa": sorted(named["DESA_2023"].dropna().unique().tolist()),
        "kab_in_khg": {str(a): int(b) for a, b in kab_in.items() if a},
        "rings": ring_peat,
        "gfw_peat_ha_khg": round(gfw_share(gfw_path, khg_ll) * khg_u.area / 1e4),
        "runway_to_gfw_km": round(gfw_nearest_km(gfw_path, rw_u), 2),
        "coverage_sk": k.get("coverage", []),
        "kab_ok": bool(set(a for a in kab_in if a) <= set(k.get("coverage", []))),
        "brgm_named_detail": sorted({f"{j} {int(t) if pd.notna(t) else ''}".strip() for j, t in zip(named["Jenis"], named["Tahun"])}),
        "feg2017_nearest_km": round(float(gpd.read_file(D / "FEG__Indonesia__2017__Rev_Tipologi.gpkg", bbox=(ext[0] - 1, ext[1] - 1, ext[2] + 1, ext[3] + 1))
                                          .to_crs(UTM).distance(rw_u).min() / 1000), 1),
        "metar_file": cfg["metar"],
    }

    # --- hotspots ---------------------------------------------------------------------------------------------------
    hc = cfg["hotspots"]
    reg_km = cfg["regional_km"]
    c = rw_u.centroid
    reg_bb = tuple(gpd.GeoSeries([c.buffer(reg_km * 1000).envelope], crs=UTM).to_crs(4326).total_bounds)
    v = gpd.read_file(D / P.DEFAULTS["inputs"]["hotspots"], bbox=reg_bb,
                      columns=["acq_date", "acq_time", "confidence", "type", "frp", "year"])
    v = v[v["type"].isin(hc["types"]) & v["confidence"].astype(str).str.lower().isin(hc["confidence"])].copy()
    t = pd.to_datetime(v["acq_date"].astype(str)) + pd.to_timedelta(v["acq_time"].astype(int) // 100, "h") + \
        pd.to_timedelta(v["acq_time"].astype(int) % 100, "min")
    v["day"] = (t + pd.Timedelta(hours=WITA)).dt.normalize()
    v = classify(v, khg_u, peat_u, gfw, rw_u, ctr_u)
    v = v[v["d_km"] <= reg_km]
    v["ring"] = ring_of(v["d_km"].to_numpy(), rk)

    n = gpd.read_file(D / P.DEFAULTS["inputs"]["hotspots_now"], bbox=reg_bb)
    n = n[n.geometry.notna() & ~n.geometry.is_empty].copy()
    lvl = n["C_LEVEL"].fillna(n["Kepercayaa"]).astype("string").str.lower().map(P.LEVEL)
    n = n[lvl.isin(cfg["now"]["levels"])].copy()
    pop = n["PopupInfo"].astype(str).str.extract(r"Tanggal\s*:\s*(\d{1,2} \w{3} \d{4})")[0]
    n["day"] = pd.to_datetime(n["ACQ_DATE"]).dt.normalize().fillna(pd.to_datetime(pop, format="%d %b %Y", errors="coerce"))
    n["month"] = n["layer"].str[:2].astype(int)
    n = classify(n, khg_u, peat_u, gfw, rw_u, ctr_u)
    n = n[n["d_km"] <= reg_km]
    n["ring"] = ring_of(n["d_km"].to_numpy(), rk)
    far = rk[-1]

    def zone_table(df, key, zcol="zone"):
        near = df[df["d_km"] <= far]
        tab = near.groupby([key, "ring", zcol]).size().unstack(["ring", zcol], fill_value=0)
        return [{key: int(i), **{f"{a}|{b}": int(tab.loc[i, (a, b)]) if (a, b) in tab.columns else 0
                                 for a in [f"{x}-{y}" for x, y in zip([0, *rk[:-1]], rk)] for b in ("peat", "mineral", "outside")},
                 "gfw": int(near[(near[key] == i) & near["gfw"]].shape[0])} for i in tab.index]

    hot = {"viirs_year": zone_table(v, "year"), "now_month": zone_table(n, "month"),
           "viirs_year_gfw": zone_table(v, "year", "zone_gfw"), "now_month_gfw": zone_table(n, "month", "zone_gfw"),
           "viirs_month": v[v["d_km"] <= rk[1]].groupby(v["day"].dt.month).size().reindex(range(1, 13), fill_value=0).tolist(),
           "sector_viirs": v[v["d_km"] <= rk[1]].groupby("sector").size().reindex(range(8), fill_value=0).tolist(),
           "sector_now": n[n["d_km"] <= rk[1]].groupby("sector").size().reindex(range(8), fill_value=0).tolist(),
           "nearest_now": None if n.empty else {"d_km": round(float(n["d_km"].min()), 2),
                                                "day": str(n.loc[n["d_km"].idxmin(), "day"].date()) if pd.notna(n.loc[n["d_km"].idxmin(), "day"]) else None},
           "now_last": str(n["day"].max().date()) if n["day"].notna().any() else None}

    # --- burned area ------------------------------------------------------------------------------------------------
    ycols = [f"BA_{y}" for y in range(2015, 2027)]
    ba = gpd.read_file(D / P.DEFAULTS["inputs"]["burned"], bbox=tuple(ext), columns=ycols)
    ba = ba[ba.geometry.notna()]
    ba_u = ba.to_crs(UTM)
    geom = shapely.make_valid(ba_u.geometry.values)
    far_u = rw_u.buffer(far * 1000)
    burned, ba_map = [], []
    peat_ll = gpd.GeoSeries([peat_u], crs=UTM).to_crs(4326).iloc[0]
    ext_box = shapely.box(*ext)
    rp = shapely.get_coordinates(shapely.point_on_surface(shapely.make_valid(ba.geometry.values)))
    on_gfw = gfw.sample(gfw.window(shapely.box(*ext)), rp[:, 0], rp[:, 1]) == 1   # a patch is on peat if its representative point is
    for col in ycols:
        sel = ba[col].notna().to_numpy()
        if not sel.any():
            burned.append({"year": int(col[3:]), **{f"r{r}": 0 for r in rk}, "khg_peat": 0, "khg_mineral": 0, "outside_khg_r": 0,
                           "khg_gfw_peat": 0, "khg_gfw_nonpeat": 0})
            continue
        g = shapely.union_all(geom[sel])
        row = {"year": int(col[3:])}
        for r in rk:
            row[f"r{r}"] = round(g.intersection(rw_u.buffer(r * 1000)).area / 1e4)
        gk = g.intersection(khg_u)
        row["khg_peat"] = round(gk.intersection(peat_u).area / 1e4)
        row["khg_mineral"] = round(gk.area / 1e4 - row["khg_peat"])
        row["outside_khg_r"] = round(g.intersection(far_u).difference(khg_u).area / 1e4)
        gp = shapely.union_all(geom[sel & on_gfw]).intersection(khg_u) if (sel & on_gfw).any() else shapely.Polygon()
        row["khg_gfw_peat"] = round(gp.area / 1e4)
        row["khg_gfw_nonpeat"] = round(gk.area / 1e4 - row["khg_gfw_peat"])
        burned.append(row)
        gl = gpd.GeoSeries([g], crs=UTM).to_crs(4326).iloc[0].intersection(ext_box).simplify(0.0004, preserve_topology=True)
        ba_map.append((gl, {"year": int(col[3:])}))

    # --- METAR ------------------------------------------------------------------------------------------------------
    m = pd.read_csv(D / cfg["metar"], low_memory=False)
    m["t"] = pd.to_datetime(m["valid"]) + pd.Timedelta(hours=WITA)
    m["day"] = m["t"].dt.normalize()
    m["vis_km"] = pd.to_numeric(m["vsby"], errors="coerce") * 1.609344
    wx = m["wxcodes"].fillna("").astype(str)
    m["smoke"] = wx.str.contains("|".join(cfg["smoke_codes"]))
    m["haze"] = wx.str.contains("HZ")
    m["drct"] = pd.to_numeric(m["drct"], errors="coerce")
    m["sknt"] = pd.to_numeric(m["sknt"], errors="coerce")
    day = m.groupby("day").agg(obs=("t", "size"), vis_min=("vis_km", "min"), smoke_obs=("smoke", "sum"), haze_obs=("haze", "sum"))
    near_day = v[v["d_km"] <= far].groupby("day").size()
    reg_day = v[v["d_km"] > far].groupby("day").size()
    nn_day = n[n["d_km"] <= far].groupby("day").size()
    nr_day = n[n["d_km"] > far].groupby("day").size()
    day["hs_near"] = near_day.reindex(day.index).fillna(0).astype(int)
    day["hs_reg"] = reg_day.reindex(day.index).fillna(0).astype(int)
    is26 = day.index.year == 2026
    day.loc[is26, "hs_near"] = nn_day.reindex(day.index[is26]).fillna(0).astype(int).to_numpy()
    day.loc[is26, "hs_reg"] = nr_day.reindex(day.index[is26]).fillna(0).astype(int).to_numpy()
    day["smoke_day"] = day["smoke_obs"] > 0
    day["low_smoke"] = day["smoke_day"] & (day["vis_min"] < cfg["low_vis_km"])
    lag = lambda s: (s | s.shift(1, freq="D").reindex(s.index).fillna(False))
    nd = lag(day["hs_near"] > 0)
    rd = lag(day["hs_reg"] > 0)
    covered = (day.index.year < 2026) | (day.index <= n["day"].max())   # VIIRS archive to 2025, KLH 2026 to its last date
    day["src"] = np.where(~day["smoke_day"], "", np.where(~covered, "nodata", np.where(nd & rd, "both", np.where(nd, "near",
                          np.where(rd, "regional", "none")))))
    # upwind check: a smoke report with wind counts when a hotspot <= far km lay within 45 degrees of the direction the wind came
    # from, the same or the previous day; calm reports have no direction
    hs = pd.concat([v.loc[(v["d_km"] <= far) & (v["day"].dt.year < 2026), ["day", "brg"]], n.loc[n["d_km"] <= far, ["day", "brg"]]])
    by_day = {d: g["brg"].to_numpy() for d, g in hs.groupby("day")}
    sm_rows = m[m["smoke"]]
    up = []
    for d, drct, kt in zip(sm_rows["day"], sm_rows["drct"], sm_rows["sknt"]):
        if not (kt > 0) or pd.isna(drct):
            up.append(np.nan)
            continue
        b = np.concatenate([by_day.get(d, []), by_day.get(d - pd.Timedelta(days=1), [])])
        up.append(float(len(b) > 0 and (np.abs((b - drct + 180) % 360 - 180) <= 45).any()))
    sm_rows = sm_rows.assign(up=up)
    g_up = sm_rows.groupby("day")["up"]
    day["smoke_upwind"] = g_up.max().reindex(day.index).fillna(0) > 0
    day["smoke_calm_only"] = day["smoke_day"] & g_up.apply(lambda s: s.isna().all()).reindex(day.index).fillna(False).astype(bool)
    # fixed hours: the UTC hours reported on at least half of the report days of every year, first report of each hour only
    m["h_utc"] = pd.to_datetime(m["valid"]).dt.hour
    share = m.groupby([m["t"].dt.year, "h_utc"])["day"].nunique().unstack(fill_value=0).div(m.groupby(m["t"].dt.year)["day"].nunique(), axis=0)
    fixed = [int(h) for h in share.columns if share[h].min() >= 0.5]
    mf = m[m["h_utc"].isin(fixed)].sort_values("t")
    first = mf.groupby(mf["t"].dt.floor("h")).head(1)
    day["smoke_fixed"] = first.groupby("day")["smoke"].any().reindex(day.index).fillna(False).astype(bool)
    yr = day.groupby(day.index.year).agg(obs=("obs", "sum"), days=("obs", "size"), smoke_days=("smoke_day", "sum"),
                                         low_smoke_days=("low_smoke", "sum"), haze_days=("haze_obs", lambda s: int((s > 0).sum())),
                                         smoke_days_fixed=("smoke_fixed", "sum"), smoke_upwind=("smoke_upwind", "sum"),
                                         smoke_calm_only=("smoke_calm_only", "sum"),
                                         hs_near=("hs_near", "sum"), hs_reg=("hs_reg", "sum"))
    src = day[day["smoke_day"]].groupby([day[day["smoke_day"]].index.year, "src"]).size().unstack(fill_value=0)
    years = [{"year": int(y), **{c: int(r[c]) for c in yr.columns},
              **{f"src_{s}": int(src.loc[y, s]) if y in src.index and s in src.columns else 0 for s in ("near", "both", "regional", "none", "nodata")}}
             for y, r in yr.iterrows()]
    sm = m[m["smoke"] & m["drct"].notna()]
    calm = int(((m["smoke"]) & (m["sknt"].fillna(0) == 0)).sum())
    wind_smoke = sm[sm["sknt"] > 0].groupby(bearing_sector(np.sin(np.radians(sm.loc[sm["sknt"] > 0, "drct"])),
                                                           np.cos(np.radians(sm.loc[sm["sknt"] > 0, "drct"])))).size()
    season = m[m["t"].dt.month.isin(cfg["season_months"]) & (m["sknt"] > 0) & m["drct"].notna()]
    wind_season = season.groupby(bearing_sector(np.sin(np.radians(season["drct"])), np.cos(np.radians(season["drct"])))).size()
    ev = {}
    for y in cfg["event_years"]:
        d = day[(day.index.year == y) & day.index.month.isin(cfg["season_months"])]
        ev[str(y)] = [[str(i.date()), None if pd.isna(r.vis_min) else round(float(r.vis_min), 2), int(r.smoke_obs), int(r.hs_near), int(r.hs_reg)]
                      for i, r in d.iterrows()]
    smoke_hour = m[m["smoke"]].groupby(m["t"].dt.hour).size().reindex(range(24), fill_value=0).tolist()
    obs_hour = m.groupby(m["t"].dt.hour).size().reindex(range(24), fill_value=0).tolist()
    smoke_month = m[m["smoke"]].groupby(m["t"].dt.month)["day"].nunique().reindex(range(1, 13), fill_value=0).tolist()
    metar = {"years": years, "events": ev, "wind_smoke": wind_smoke.reindex(range(8), fill_value=0).astype(int).tolist(),
             "wind_season": wind_season.reindex(range(8), fill_value=0).astype(int).tolist(), "calm_smoke": calm,
             "smoke_month_days": smoke_month, "smoke_hour": smoke_hour, "obs_hour": obs_hour, "first": str(m["t"].min().date()), "last": str(m["t"].max().date()),
             "n": int(len(m)), "smoke_obs": int(m["smoke"].sum()), "fixed_hours_utc": fixed,
             "reports_per_day": {int(y): round(float(c), 1) for y, c in (m.groupby(m["t"].dt.year).size() / m.groupby(m["t"].dt.year)["day"].nunique()).items()}}

    # --- map layers ---------------------------------------------------------------------------------------------------
    ext_u = gpd.GeoSeries([ext_box], crs=4326).to_crs(UTM).iloc[0]
    old_map = [(gpd.GeoSeries([r.geometry], crs=UTM).to_crs(4326).iloc[0].intersection(ext_box).simplify(0.0003),
                {"name": r.NAMA_KHG}) for r in old.itertuples() if r.geometry.intersects(ext_u)]
    feg_map = [(r.geometry.intersection(ext_box).simplify(0.0002), {"peat": "gambut" in str(r.tnh_gambut).lower() and "non" not in str(r.tnh_gambut).lower(),
                                                                       "thick": r.peat_thick, "fn": r.feg_50k, "ha": round(r.ha, 1)})
               for r in feg.itertuples()]
    vin = v[v.geometry.within(ext_box)]
    nin = n[n.geometry.within(ext_box)]
    layers = {
        "khg": fc([(khg_ll.simplify(0.0002), {"code": k["code"], "name": k["name"]})]),
        "old": fc(old_map),
        "feg": fc(feg_map),
        "runway": fc([(runway, {"name": cfg["airport"]["name"]})]),
        "rings": fc([(ring_geoms[r].boundary, {"km": r}) for r in rk]),
        "burned": fc(ba_map),
        # points as rows [lon, lat, year or month, zone (FEG), local date, zone (GFW)]: GeoJSON is built in the page
        "viirs": [[r4(g.x), r4(g.y), int(y), ZONES.index(z), str(dd.date()), ZONES.index(z2)]
                  for g, y, z, dd, z2 in zip(vin.geometry, vin["year"], vin["zone"], vin["day"], vin["zone_gfw"])],
        "now": [[r4(g.x), r4(g.y), int(mm), ZONES.index(z), None if pd.isna(dd) else str(dd.date()), ZONES.index(z2)]
                for g, mm, z, dd, z2 in zip(nin.geometry, nin["month"], nin["zone"], nin["day"], nin["zone_gfw"])],
        "brgm": fc([(r.geometry, {"jenis": r.Jenis, "tahun": None if pd.isna(r.Tahun) else int(r.Tahun), "khg": r.KHG, "desa": r.DESA_2023})
                    for r in brgm.itertuples() if r.geometry is not None and r.geometry.within(ext_box)]),
    }
    return {"cfg": {k2: cfg[k2] for k2 in ("airport", "khg", "rings_km", "extent", "regional_km", "season_months", "low_vis_km",
                                          "event_years", "smoke_codes", "hotspots", "now")},
            "facts": facts, "hot": hot, "burned": burned, "metar": metar, "layers": layers,
            "gfw_png": gfw_png(gfw_path, ext)}


def assemble(data, out_path):
    tpl = (ASSETS / "airport.html").read_text(encoding="utf-8")
    data = {**data, "style": json.loads((NAT / "basemap-positron.json").read_text(encoding="utf-8"))}
    html = (tpl.replace("/*D3*/", (NAT / "d3.v7.9.0.min.js").read_text(encoding="utf-8"))
            .replace("/*ML*/", (NAT / "maplibre-gl.v5.24.0.js").read_text(encoding="utf-8"))
            .replace("/*MLCSS*/", (NAT / "maplibre-gl.v5.24.0.css").read_text(encoding="utf-8"))
            .replace("/*JS*/", (ASSETS / "airport.js").read_text(encoding="utf-8"))
            .replace("/*DATA*/", "const DATA=" + json.dumps(data, separators=(",", ":"), ensure_ascii=False).replace("</", "<\\/") + ";"))
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    Path(out_path).write_text(html, encoding="utf-8")
    print(f"{out_path}: {len(html) / 1e6:.1f} MB")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--out")
    ap.add_argument("--reassemble", action="store_true", help="reuse the data of the last build and only rebuild the page")
    a = ap.parse_args(argv)
    cfg = P._expand(yaml.safe_load(Path(a.config).read_text(encoding="utf-8")))
    out = Path(a.out or cfg["out"])
    cache = out.with_suffix(".json")
    if a.reassemble and cache.exists():
        data = json.loads(cache.read_text(encoding="utf-8"))
    else:
        data = build(cfg)
        out.parent.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False, default=str), encoding="utf-8")
    assemble(data, out)


if __name__ == "__main__":
    main()
