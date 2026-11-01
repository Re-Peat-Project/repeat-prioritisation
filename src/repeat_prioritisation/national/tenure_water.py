#!/usr/bin/env python3
"""Dry-season water-table depth of the groundwater model by land tenure.

  repeat-national-tenure-water --config configs/examples/national_profile.yaml [--khg KHG.16.02.01 ...] [--run lidar:cap_climate ...]

Reads the depth rasters of a `repeat-neraca-model` run (`<khg folder>/03_neraca/<dem>/runs/model/<run>/`: mean depth over the dry
season and days deeper than 40 cm, 100 or 200 m cells) and gives each model cell the tenure class of `national.tenure` (same
precedence and layers). Cells of managed land (the run holds them at a target level, `model_managed_target.tif`) are reported
apart from open land, because their depth is set by the scenario and says nothing about the land itself. Writes <out>/tenure/:
  tenure_water.csv  khg_id, dem, run, tenure, managed, cells, area_km2, mean_depth_cm, median_depth_cm, p90_depth_cm, days_deeper_40cm
Default runs: deltadtm:d22_climate_2026 and lidar:cap_climate (repeat the option to change). A KHG without the run is skipped.
The model is in development; its station scores are in each run's `station_scores.json`.
"""
from __future__ import annotations

import argparse
import logging
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import rasterio
import shapely
from pyproj import Transformer

from repeat_common import khg as K
from repeat_prioritisation.national import land as L
from repeat_prioritisation.national import overlay as O
from repeat_prioritisation.national import profile as P
from repeat_prioritisation.national import tenure as T

log = logging.getLogger("prioritas.tenure_water")
DEFAULT_RUNS = ["deltadtm:d22_climate_2026", "lidar:cap_climate"]


def one(cfg, kid, dem, run):
    rdir = K.folder(kid.replace("KHG.", "", 1)) / "03_neraca" / dem / "runs" / "model" / run
    if not (rdir / "model_season_mean_depth.tif").exists():
        return []
    with rasterio.open(rdir / "model_season_mean_depth.tif") as s:
        depth, tr, crs = s.read(1, masked=True), s.transform, s.crs
    with rasterio.open(rdir / "model_season_days_deeper_40cm.tif") as s:
        days = s.read(1, masked=True)
    managed = np.zeros(depth.shape, bool)
    if (rdir / "model_managed_target.tif").exists():
        with rasterio.open(rdir / "model_managed_target.tif") as s:
            managed = ~s.read(1, masked=True).mask
    rows_, cols_ = np.where(~np.ma.getmaskarray(depth))
    x, y = rasterio.transform.xy(tr, rows_, cols_)
    lon, lat = Transformer.from_crs(crs, 4326, always_xy=True).transform(np.asarray(x), np.asarray(y))
    khg = P.load_khg(cfg)
    g = shapely.make_valid(khg[khg.khg_id == kid].geometry.iloc[0])
    data, inp = Path(cfg["data"]), cfg["inputs"]
    kws, _ = O.read_forest_feg(cfg, g)
    lic = O._read(data / inp["licences"], g, ["IZIN_USAHA"])
    lic["cls"] = lic["IZIN_USAHA"].map(O.LIC_VALUE)
    pts = gpd.GeoDataFrame(index=np.arange(len(lon)), geometry=gpd.points_from_xy(lon, lat), crs=4326)
    df = T.classify(pts, lic, kws, None)[["tenure"]].assign(depth=depth[rows_, cols_].data, days=days.astype(float).filled(np.nan)[rows_, cols_], managed=managed[rows_, cols_])
    cell_km2 = abs(tr.a * tr.e) / 1e6
    out = []
    for (ten, man), g_ in df.groupby(["tenure", "managed"]):
        out.append({"khg_id": kid, "dem": dem, "run": run, "tenure": ten, "managed": bool(man), "cells": len(g_), "area_km2": len(g_) * cell_km2,
                    "mean_depth_cm": g_.depth.mean(), "median_depth_cm": g_.depth.median(), "p90_depth_cm": g_.depth.quantile(0.9), "days_deeper_40cm": g_.days.mean()})
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--config", required=True)
    ap.add_argument("--khg", nargs="*")
    ap.add_argument("--run", action="append", help="dem:run, repeatable")
    a = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    cfg = L.load_cfg(a.config)
    ids = a.khg or list(P.load_khg(cfg).khg_id)   # a KHG with no folder or run is skipped
    rows = []
    for kid in ids:
        for spec in a.run or DEFAULT_RUNS:
            dem, run = spec.split(":")
            try:
                r = one(cfg, kid, dem, run)
            except (FileNotFoundError, KeyError, ValueError) as e:     # no folder or model run for this KHG
                log.info("%s %s skipped: %s", kid, spec, e)
                continue
            if r:
                log.info("%s %s: %d classes", kid, spec, len(r))
                rows += r
    out = Path(cfg["out"]) / "tenure"
    out.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).round(3).to_csv(out / "tenure_water.csv", index=False)
    log.info("%d rows -> %s", len(rows), out)


if __name__ == "__main__":
    main()
