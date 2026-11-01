#!/usr/bin/env python3
"""Hotspots and burned peat by land tenure, per KHG and year.

  repeat-national-tenure --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--workers 4] [--force]

Every point of a KHG (grid points for area, VIIRS hotspots for fire) gets one tenure class, by precedence:
  licence      inside a business licence (oil palm, forest concession PBPH, plantation forest PPHTR, mining); sub = licence type
  forest       forest area (kawasan hutan) with no licence; sub = conservation, protection, production, convertible production
  other_land   everything else (other land use, water, not mapped)
and a flag for DMPG village land (orthogonal: a DMPG village can hold land of any tenure class). Licence polygons overlap, so a
point with several licence types takes the first of LIC_RANK. PPHKM (community forest permits) are not licences here: that land
stays in its forest area class.

Areas are grid point counts times the cell area (same grid and peat sampling as `national.overlay`). Hotspots are VIIRS SNPP
2012-2026 on peat, vegetation-fire type 0 where the file has a type, medium (n) and high (h) confidence kept apart. Results of
each KHG are cached in <out>/tenure/cache/<khg_id>.json, so an interrupted run resumes. Writes, in <out>/tenure/:
  tenure_area.csv      khg_id, khg, tenure, sub, dmpg, area_km2, peat_km2, burned_peat_km2 (burned 2015-2025)
  tenure_hotspots.csv  khg_id, tenure, sub, dmpg, year, conf, ytd, n (hotspots on peat; ytd = on or before the last day of 2026 data,
                       so every year can be compared over the same calendar window)
  tenure_meta.json     window end (month-day) shared by all years, last 2026 date
  tenure_checks.csv    per KHG: class areas against the KHG grid area, hotspots by class against the hotspots on peat inside
"""
from __future__ import annotations

import argparse
import functools
import json
import logging
import re
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import pyogrio
import shapely

from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P

log = logging.getLogger("prioritas.tenure")
LIC_RANK = ["sawit", "tambang", "pphtr", "pbph"]
FOREST_SUB = {"cons": "conservation", "hl": "protection", "prod": "production", "hpk": "convertible"}
VIIRS = ["hotspot_viirs_snpp_2012_2025.gpkg", "hotspot_viirs_snpp_sp_2026.gpkg", "hotspot_viirs_snpp_nrt_2026.gpkg"]


def classify(pts, lic, kws, dpg):
    """tenure, sub and dmpg of each point (GeoDataFrame in lon/lat); layers are GeoDataFrames in lon/lat."""
    n = len(pts)
    tenure, sub = np.full(n, "other_land", object), np.full(n, "other", object)
    if len(kws) and n:
        j = gpd.sjoin(pts[["geometry"]], kws[["cls", "geometry"]], how="inner", predicate="within")
        order = {c: i for i, c in enumerate(O.KWS_ORDER)}
        j = j.assign(r=j["cls"].map(order)).sort_values("r")
        j = j[~j.index.duplicated(keep="first")]
        pos = pts.index.get_indexer(j.index)
        for pos_i, c in zip(pos, j["cls"]):
            if c in FOREST_SUB:
                tenure[pos_i], sub[pos_i] = "forest", FOREST_SUB[c]
    if len(lic) and n:
        j = gpd.sjoin(pts[["geometry"]], lic[["cls", "geometry"]], how="inner", predicate="within")
        j = j[j["cls"].isin(LIC_RANK)]
        j = j.assign(r=j["cls"].map({c: i for i, c in enumerate(LIC_RANK)})).sort_values("r")
        j = j[~j.index.duplicated(keep="first")]
        pos = pts.index.get_indexer(j.index)
        tenure[pos], sub[pos] = "licence", j["cls"].to_numpy()
    d = np.zeros(n, bool)
    if dpg is not None and len(dpg) and n:
        d[pts.index.get_indexer(gpd.sjoin(pts[["geometry"]], dpg[["geometry"]], how="inner", predicate="within").index.unique())] = True
    return pd.DataFrame({"tenure": tenure, "sub": sub, "dmpg": d}, index=pts.index)


@functools.lru_cache(maxsize=None)
def last_day(data):
    """Last acquisition date of the 2026 files (all of them, not one KHG), so every KHG uses the same window."""
    days = [pd.to_datetime(pyogrio.read_dataframe(data / f, columns=["acq_date"], read_geometry=False)["acq_date"]).max() for f in VIIRS if "2026" in f and (data / f).exists()]
    return max(days) if days else pd.Timestamp("2026-12-31")


def viirs(cfg, g):
    """VIIRS hotspots inside g, 2012-2026, with year, confidence and an on-peat flag."""
    data, parts = Path(cfg["data"]), []
    for f in VIIRS:
        if not (data / f).exists():
            continue
        cols = [c for c in ("acq_date", "confidence", "type") if c in pyogrio.read_info(data / f)["fields"]]
        h = pyogrio.read_dataframe(data / f, mask=g, columns=cols)
        if "type" in h:
            h = h[h["type"] == 0]
        parts.append(h[["acq_date", "confidence", "geometry"]])
    if not parts:
        return gpd.GeoDataFrame({"year": [], "conf": [], "ytd": []}, geometry=[], crs=4326)
    h = pd.concat(parts, ignore_index=True)
    h = h[h["confidence"].isin(["n", "h"]) & shapely.contains_xy(g, h.geometry.x.to_numpy(), h.geometry.y.to_numpy())]
    d = pd.to_datetime(h["acq_date"])
    cut = last_day(data)
    h = h.assign(year=d.dt.year, conf=h["confidence"].map({"n": "medium", "h": "high"}), ytd=(d.dt.month * 100 + d.dt.day) <= cut.month * 100 + cut.day)
    pe = O.peat_path(cfg)
    if pe and len(h):
        ps = P.PeatSampler(pe)
        h = h[ps.sample(ps.window(g), h.geometry.x.to_numpy(), h.geometry.y.to_numpy()) == 1]
    return h[["year", "conf", "ytd", "geometry"]].reset_index(drop=True)


def one(cfg, kid, name, g):
    data, inp = Path(cfg["data"]), cfg["inputs"]
    g, lon, lat, pts, _, area_cell, cell = O.base_points(cfg, g)
    kws, _ = O.read_forest_feg(cfg, g)
    lic = O._read(data / inp["licences"], g, ["IZIN_USAHA"])
    lic["cls"] = lic["IZIN_USAHA"].map(O.LIC_VALUE)
    dpg = O.read_dmpg(data / inp["dmpg"], g) if inp.get("dmpg") and (data / inp["dmpg"]).exists() else None
    pc = classify(pts, lic, kws, dpg).assign(peat=pts["peat"].to_numpy(), burned=pts["burned"].to_numpy())
    area = (pc.assign(n=1, peat_n=pc["peat"].astype(int), burn_n=(pc["peat"] & pc["burned"]).astype(int))
              .groupby(["tenure", "sub", "dmpg"], as_index=False)[["n", "peat_n", "burn_n"]].sum())
    area = pd.DataFrame({"tenure": area["tenure"], "sub": area["sub"], "dmpg": area["dmpg"], "area_km2": area["n"] * area_cell,
                         "peat_km2": area["peat_n"] * area_cell, "burned_peat_km2": area["burn_n"] * area_cell})
    h = viirs(cfg, g)
    hc = classify(h, lic, kws, dpg).assign(year=h["year"].to_numpy(), conf=h["conf"].to_numpy(), ytd=h["ytd"].to_numpy()) if len(h) else pd.DataFrame(columns=["tenure", "sub", "dmpg", "year", "conf", "ytd"])
    hot = hc.groupby(["tenure", "sub", "dmpg", "year", "conf", "ytd"], as_index=False).size().rename(columns={"size": "n"})
    meta = {"khg_km2_grid": len(pts) * area_cell, "cell_m": cell, "hs_peat_inside": int(len(h))}
    for t in (area, hot):
        t.insert(0, "khg_id", kid)
    area.insert(1, "khg", name)
    return area.to_dict("records"), hot.to_dict("records"), meta


def cache_file(cfg, kid):
    return Path(cfg["out"]) / "tenure" / "cache" / (re.sub(r"[^\w.-]", "_", kid) + ".json")


def work(args):
    cfg, kid, name, geom = args
    area, hot, meta = one(cfg, kid, name, geom)
    f = cache_file(cfg, kid)
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps({"area": area, "hot": hot, "meta": meta}, default=lambda v: v.item() if hasattr(v, "item") else float(v)), encoding="utf-8")
    return kid


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*", help="khg_id to compute (default: all)")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--force", action="store_true", help="recompute KHG that are already cached")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    sel = P.load_khg(cfg)
    if a.khg:
        sel = sel[sel.khg_id.isin(a.khg)]
    todo = [(cfg, r.khg_id, r.nama, r.geometry) for r in sel.itertuples() if a.force or not cache_file(cfg, r.khg_id).exists()]
    log.info("%d KHG, %d to compute", len(sel), len(todo))
    if a.workers > 1 and len(todo) > 1:
        with ProcessPoolExecutor(a.workers) as ex:
            for kid in ex.map(work, todo):
                log.info("done %s", kid)
    else:
        for t in todo:
            log.info("%s %s", t[1], t[2])
            work(t)
    area, hot, chk = [], [], []
    for kid in sel.khg_id:
        d = json.loads(cache_file(cfg, kid).read_text(encoding="utf-8"))
        area += d["area"]
        hot += d["hot"]
        m = d["meta"]
        chk.append({"khg_id": kid, "khg_km2_grid": m["khg_km2_grid"], "area_gap": sum(r["area_km2"] for r in d["area"]) - m["khg_km2_grid"],
                    "hs_peat_inside": m["hs_peat_inside"], "hs_gap": sum(r["n"] for r in d["hot"]) - m["hs_peat_inside"]})
    out = Path(cfg["out"]) / "tenure"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(area).round(4).to_csv(out / "tenure_area.csv", index=False)
    pd.DataFrame(hot).to_csv(out / "tenure_hotspots.csv", index=False)
    pd.DataFrame(chk).round(4).to_csv(out / "tenure_checks.csv", index=False)
    (out / "tenure_meta.json").write_text(json.dumps({"window_end": last_day(Path(cfg["data"])).strftime("%m-%d"), "last_2026": last_day(Path(cfg["data"])).strftime("%Y-%m-%d"), "types": "VIIRS SNPP, vegetation fire (type 0) where recorded, medium and high confidence, on peat"}), encoding="utf-8")
    log.info("%d KHG -> %s", len(sel), out)


if __name__ == "__main__":
    main()
