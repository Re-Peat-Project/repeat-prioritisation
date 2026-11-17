#!/usr/bin/env python3
"""Per-KHG inputs of the final prioritisation that no other step computes: water and road access, conservation share,
population exposure and villages on peat, and peat volume.

  repeat-national-final-inputs --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 3] [--force]

On the peat grid points of each KHG (same grid and KLH peat as `national.tenure`), with the layers in `final.inputs_layers`:
  water_dist_km       median distance from the peat points to the nearest large river (RBI_sungai holds only rivers drawn
                      with two banks, "Sungai Dua Garis", 2,707 nationally: the rivers that carry dry-season flow) or lake/reservoir
                      (RBI_wadukdanau), in km; capped at 110 km where none lies within one degree
  road_dist_km        median distance to the nearest road of the listed classes (RBI detailed roads; footpaths, railways and
                      runways left out); capped at 55 km where none lies within half a degree
  conservation_share  share of the peat points in conservation areas (Kawasan Hutan 2023: national parks, nature and wildlife
                      reserves, recreation parks, grand forest parks; the "cons" class of national.overlay)
  villages_peat       number of 2023 villages (KLH boundaries) holding at least one peat point
  pop_on_peat         people living on the peat: WorldPop 2020 1 km density at each peat point times the point's cell area
  pop_10km            people within `exposure_buffer_km` of the KHG boundary (KHG plus buffer, all cells whose centre falls
                      inside): a proxy for exposure to haze from peat fires
Distances are measured in World Mercator (EPSG:3395; under 1.3% scale error below 9 degrees latitude).
Once for all KHG, from KLH's PPEG analysis (attributes only):
  peat_volume_mm3     peat volume in million m3: area of each BBSDLP depth class on KLH peat times the class mid-depth
                      (0.75, 1.5, 2.5, 4, 6 and, for ">= 700 cm", 8 m, an assumption); blank depth class not counted
  open_share          share of KLH peat with open or degraded cover in KLH's land cover 2022 (PPEG PL_2022): swamp shrub
                      (Semak Belukar Rawa), shrub (Semak Belukar), open land (Lahan Terbuka), open swamp (Rawa) and savanna;
                      plantations, crops, settlements and forest are not counted; the input to the revegetation label
  forest_share        share of KLH peat under forest in PL_2022 (primary and secondary swamp, dryland and mangrove forest)
  lc_known_share      share of KLH peat with a PL_2022 value
Population, `--population` (amendment 2026-11-17, before any people result was used: the 1 km WorldPop 2020 grid was replaced
by IHME Populace 2025q3 at 40 m): zonal sums of the grid named in `final.inputs_layers.population` (any CRS; NaN and negative cells count as 0), over
KLH's peat polygons of the KHG (pop_on_peat; cells whose centre is on peat) and over the KHG plus `exposure_buffer_km`
(pop_10km); the KHG of <out>/whole_khg/ use the whole KHG as peat. Writes final_inputs/population.csv, which
repeat-national-final prefers over the point-sampled values.
Writes <out>/final_inputs/final_inputs.csv (one row per KHG) and final_inputs_checks.csv; per-KHG cache in final_inputs/cache/.
"""
from __future__ import annotations

import argparse
import json
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import rasterio
import rasterio.mask
import shapely

from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P

log = logging.getLogger("prioritas.final_inputs")
METRIC = "EPSG:3395"
DEPTH_MID = {"50 - <100 cm": .75, "100 - <200 cm": 1.5, "200 - <300 cm": 2.5, "300 - <500 cm": 4.0, "500 - <700 cm": 6.0, ">= 700 cm": 8.0}
PPEG = "ALL_Analysis_Integrasi_Tematik__PPEG_Indonesia__April_2026.gpkg"


def _nearest_km(pm, layer_m, cap_km):
    if layer_m is None or not len(layer_m):
        return np.full(len(pm), cap_km)
    nn = gpd.sjoin_nearest(pm[["geometry"]], layer_m[["geometry"]], how="left", distance_col="d")
    d = nn.groupby(level=0)["d"].min().reindex(pm.index).to_numpy() / 1000
    return np.minimum(np.nan_to_num(d, nan=cap_km), cap_km)


def one(cfg, kid, name, g):
    data = Path(cfg["data"])
    lay = cfg["final"]["inputs_layers"]
    g, lon, lat, pts, _, area_cell, cell = O.base_points(cfg, g)
    peat = pts[pts["peat"]].reset_index(drop=True)
    out = {"khg_id": kid, "khg": name, "peat_points": len(peat), "cell_m": cell}
    # people within the buffer: computed even without peat
    buf = gpd.GeoSeries([g], crs=4326).to_crs(METRIC).buffer(lay["exposure_buffer_km"] * 1000).to_crs(4326).iloc[0]
    pop_ok = (data / lay["population"]).exists() and rasterio.open(data / lay["population"]).crs.to_epsg() == 4326
    if pop_ok:        # otherwise (missing, or a projected grid such as Populace) filled by the --population pass (population.csv)
        with rasterio.open(data / lay["population"]) as src:
            arr, _ = rasterio.mask.mask(src, [shapely.geometry.mapping(buf)], crop=True, filled=True, nodata=0)
            a = arr[0].astype(float)
            a[a < 0] = 0
            out["pop_10km"] = float(a.sum())
            if len(peat):
                v = np.array([x[0] for x in src.sample(list(zip(peat.geometry.x, peat.geometry.y)))], dtype=float)
                v[(v < 0) | ~np.isfinite(v)] = 0
                cell_km2 = (src.res[0] * 111.32) * (src.res[1] * 111.32 * np.cos(np.radians(peat.geometry.y.to_numpy())))
                out["pop_on_peat"] = float((v / cell_km2 * area_cell).sum())
    if not len(peat):
        return out
    pm = peat.to_crs(METRIC)
    x0, y0, x1, y1 = g.bounds
    box1 = shapely.box(x0 - 1, y0 - 1, x1 + 1, y1 + 1)
    riv = pyogrio.read_dataframe(data / lay["rivers"], mask=box1, columns=[])
    lak = pyogrio.read_dataframe(data / lay["lakes"], mask=box1, columns=[])
    water = pd.concat([riv[["geometry"]], lak[["geometry"]]], ignore_index=True)
    water = gpd.GeoDataFrame(water, geometry="geometry", crs=4326).to_crs(METRIC) if len(water) else None
    out["water_dist_km"] = float(np.median(_nearest_km(pm, water, 110.0)))
    box5 = shapely.box(x0 - .5, y0 - .5, x1 + .5, y1 + .5)
    rd = pyogrio.read_dataframe(data / lay["roads"], mask=box5, columns=["NAMA_UNSUR"])
    rd = rd[rd.NAMA_UNSUR.isin(lay["road_classes"])]
    out["road_dist_km"] = float(np.median(_nearest_km(pm, rd.to_crs(METRIC) if len(rd) else None, 55.0)))
    kws, _ = O.read_forest_feg(cfg, g)
    if len(kws):
        j = gpd.sjoin(peat[["geometry"]], kws[kws.cls == "cons"][["geometry"]], how="inner", predicate="within")
        out["conservation_share"] = float(j.index.nunique() / len(peat))
    else:
        out["conservation_share"] = 0.0
    vil = pyogrio.read_dataframe(data / lay["villages"], mask=g, columns=["DESA_2023"])
    if len(vil):
        vil = vil.reset_index(names="vid")
        j = gpd.sjoin(peat[["geometry"]], vil[["vid", "geometry"]], how="inner", predicate="within")
        out["villages_peat"] = int(j.vid.nunique())
    else:
        out["villages_peat"] = 0
    return out


OPEN = {"Semak Belukar Rawa", "Semak Belukar", "Lahan Terbuka", "Rawa", "Savana/ Padang Rumput"}


def peat_volume(data, whole_khg=None):
    """Peat volume and land-cover shares per KHG from the PPEG attributes. whole_khg: KHG names whose whole area counts as peat."""
    d = pyogrio.read_dataframe(data / PPEG, columns=["NAMA_KHG", "LAHAN_GAMB", "KDLMN_GBT", "LUAS_HA", "PL_2022"], read_geometry=False)
    keep = d.LAHAN_GAMB.str.upper() == "LAHAN GAMBUT"
    if whole_khg:
        keep |= d.NAMA_KHG.map(lambda s: re.sub(r"\s+", " ", str(s)).strip()).isin(set(whole_khg))
    d = d[keep]
    d["mid_m"] = d.KDLMN_GBT.str.strip().map(DEPTH_MID)
    d["vol_mm3"] = d.LUAS_HA * 1e4 * d.mid_m / 1e6
    g = d.groupby("NAMA_KHG").agg(peat_volume_mm3=("vol_mm3", "sum"), depth_known_ha=("LUAS_HA", lambda s: s[d.loc[s.index, "mid_m"].notna()].sum()),
                                   peat_ha_ppeg=("LUAS_HA", "sum")).reset_index()
    g["depth_known_share"] = g.depth_known_ha / g.peat_ha_ppeg
    pl = d.PL_2022.fillna("").str.strip()
    d["open_ha"] = d.LUAS_HA.where(pl.isin(OPEN), 0)
    d["forest_ha"] = d.LUAS_HA.where(pl.str.startswith("Hutan") & ~pl.str.startswith("Hutan Tanaman"), 0)
    d["lc_ha"] = d.LUAS_HA.where(pl != "", 0)
    lc = d.groupby("NAMA_KHG")[["open_ha", "forest_ha", "lc_ha"]].sum()
    g = g.merge(lc.reset_index(), on="NAMA_KHG", how="left")
    for k in ("open", "forest"):
        g[f"{k}_share"] = g[f"{k}_ha"] / g.peat_ha_ppeg
    g["lc_known_share"] = g.lc_ha / g.peat_ha_ppeg
    return g.drop(columns=["lc_ha"])


def population(cfg, sel):
    data = Path(cfg["data"])
    lay = cfg["final"]["inputs_layers"]
    pe = gpd.read_file(data / "peat" / "ppeg_lahan_gambut_2026.gpkg")
    key = lambda s: re.sub(r"\s+", " ", str(s)).strip().casefold()
    pe = pe.assign(_k=pe.khg.map(key)).dissolve("_k")
    wf = Path(cfg["out"]) / "whole_khg" / "whole_khg.json"
    whole = set(json.loads(wf.read_text(encoding="utf-8"))["khg"]) if wf.exists() else set()
    rows = []
    with rasterio.open(data / lay["population"]) as src:
        def zsum(geom):     # geometry in EPSG:4326, reprojected to the grid's CRS
            g2 = gpd.GeoSeries([geom], crs=4326).to_crs(src.crs).iloc[0]
            try:
                arr, _ = rasterio.mask.mask(src, [shapely.geometry.mapping(g2)], crop=True, filled=True, nodata=0)
            except ValueError:            # no overlap with the grid
                return 0.0
            a = arr[0].astype("float64")
            a[(a < 0) | ~np.isfinite(a)] = 0
            if src.nodata is not None:
                a[arr[0] == src.nodata] = 0
            return float(a.sum())
        for i, r in enumerate(sel.itertuples(), 1):
            g = shapely.make_valid(r.geometry)
            buf = gpd.GeoSeries([g], crs=4326).to_crs(METRIC).buffer(lay["exposure_buffer_km"] * 1000).to_crs(4326).iloc[0]
            k = key(r.nama)
            peat = g if r.khg_id in whole else (shapely.make_valid(pe.loc[k, "geometry"]).intersection(g) if k in pe.index else None)
            rows.append({"khg_id": r.khg_id, "pop_on_peat": zsum(peat) if peat is not None and not peat.is_empty else 0.0,
                         "pop_10km": zsum(buf), "pop_source": Path(lay["population"]).name, "whole_khg": r.khg_id in whole})
            if i % 100 == 0:
                log.info("population %d/%d", i, len(sel))
    return pd.DataFrame(rows)


def cache_file(cfg, kid):
    return Path(cfg["out"]) / "final_inputs" / "cache" / (re.sub(r"[^\w.-]", "_", kid) + ".json")


def work(args):
    cfg, kid, name, geom = args
    row = one(cfg, kid, name, geom)
    f = cache_file(cfg, kid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(row, default=lambda v: v.item() if hasattr(v, "item") else float(v)), encoding="utf-8")
    return kid


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*")
    ap.add_argument("--workers", type=int, default=3)
    ap.add_argument("--force", action="store_true")
    ap.add_argument("--population", action="store_true", help="only the population zonal sums -> final_inputs/population.csv")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    sel = P.load_khg(cfg)
    if a.khg:
        sel = sel[sel.khg_id.isin(a.khg)]
    if a.population:
        p = population(cfg, sel)
        (Path(cfg["out"]) / "final_inputs").mkdir(parents=True, exist_ok=True)
        p.to_csv(Path(cfg["out"]) / "final_inputs" / "population.csv", index=False, float_format="%.10g")
        log.info("population: %d KHG, %.1f million on KLH peat, sum of KHG+buffer %.1f million", len(p), p.pop_on_peat.sum() / 1e6, p.pop_10km.sum() / 1e6)
        return
    todo = [(cfg, r.khg_id, r.nama, r.geometry) for r in sel.itertuples() if a.force or not cache_file(cfg, r.khg_id).exists()]
    log.info("%d KHG, %d to compute", len(sel), len(todo))
    if a.workers > 1 and len(todo) > 1:
        with ProcessPoolExecutor(a.workers) as ex:
            for i, kid in enumerate(ex.map(work, todo), 1):
                if i % 25 == 0 or i == len(todo):
                    log.info("%d/%d done", i, len(todo))
    else:
        for t in todo:
            work(t)
    rows = [json.loads(cache_file(cfg, k).read_text(encoding="utf-8")) for k in sel.khg_id]
    df = pd.DataFrame(rows)
    vol = peat_volume(Path(cfg["data"]))
    nm = lambda s: re.sub(r"\s+", " ", str(s)).strip().casefold()
    df = df.merge(vol.assign(_k=vol.NAMA_KHG.map(nm)).drop(columns="NAMA_KHG"), left_on=df.khg.map(nm), right_on="_k", how="left").drop(columns=["_k", "key_0"], errors="ignore")
    out = Path(cfg["out"]) / "final_inputs"
    df.round(5).to_csv(out / "final_inputs.csv", index=False)
    chk = pd.DataFrame({"check": ["KHG", "with peat points", "population of Indonesia in the grid (million)", "sum of pop_on_peat (million)",
                                  "KHG with a river or lake within 110 km", "KHG with a road within 55 km", "KHG with peat volume"],
                        "value": [len(df), int((df.peat_points > 0).sum()), None, round(df.pop_on_peat.sum() / 1e6, 2),
                                  int((df.water_dist_km < 110).sum()), int((df.road_dist_km < 55).sum()), int(df.peat_volume_mm3.notna().sum())]})
    chk.to_csv(out / "final_inputs_checks.csv", index=False)
    log.info("%d KHG -> %s", len(df), out)


if __name__ == "__main__":
    main()
